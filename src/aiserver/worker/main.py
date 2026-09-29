"""Run durable delegation processing outside the Databricks App web process."""

import argparse
import asyncio
import os
import signal
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiserver.application.delegation.worker import AgentTaskWorker
from aiserver.application.orchestration.agent import (
    OrchestratorDependencies,
    build_lakebase_delegation_executors,
)
from aiserver.application.ports.audit import MessageBus
from aiserver.application.ports.tasks import AgentTaskBus
from aiserver.application.runtime.identity import (
    RequestIdentityContext,
    build_request_identity_context,
)
from aiserver.config.settings import (
    AppSettings,
    get_settings,
)
from aiserver.contracts.delegation import DelegationTask
from aiserver.contracts.subagents import SUBAGENTS, SubagentConfig
from aiserver.infrastructure.databricks.lakebase import connect_lakebase
from aiserver.infrastructure.messaging.bus import default_message_bus
from aiserver.infrastructure.observability.tracing import update_trace_metadata
from aiserver.infrastructure.persistence.tasks import default_agent_task_bus

Executor = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class WorkerDependencies:
    """Dependencies required by the standalone delegation worker."""

    settings: AppSettings
    subagents: list[SubagentConfig]
    task_bus: AgentTaskBus
    message_bus: MessageBus
    orchestrator: OrchestratorDependencies


def build_worker_dependencies(settings: AppSettings | None = None) -> WorkerDependencies:
    """Compose worker-only dependencies without constructing the web runtime."""
    resolved_settings = settings or get_settings()
    if resolved_settings.agent_task_backend.strip().lower() != "uc_table":
        raise ValueError("Standalone delegation worker requires AGENT_TASK_BACKEND=uc_table")
    message_bus = default_message_bus(resolved_settings)
    orchestrator = OrchestratorDependencies(
        message_bus=message_bus,
        trace_metadata_updater=update_trace_metadata,
        lakebase_connection_factory=connect_lakebase,
    )
    return WorkerDependencies(
        settings=resolved_settings,
        subagents=list(SUBAGENTS),
        task_bus=default_agent_task_bus(resolved_settings),
        message_bus=message_bus,
        orchestrator=orchestrator,
    )


class DelegationWorkerProcess:
    """Build and run one cancellation-safe durable worker process."""

    def __init__(
        self,
        dependencies: WorkerDependencies,
        *,
        worker_id: str,
        identity_context_provider: Callable[
            [], RequestIdentityContext
        ] = build_request_identity_context,
    ) -> None:
        self._deps = dependencies
        self._worker_id = worker_id
        self._identity_context_provider = identity_context_provider

    async def _build_worker(self) -> AgentTaskWorker:
        executors = build_lakebase_delegation_executors(
            self._deps.subagents,
            self._identity_context_provider(),
            deps=self._deps.orchestrator,
        )
        if self._deps.settings.approval_delegation_enabled:

            async def execute_post_approval_planning(
                payload: dict[str, object],
            ) -> dict[str, object]:
                return {
                    "result": "approved_planning_task_recorded",
                    "approval_request_id": payload.get("approval_request_id"),
                    "planning_only": True,
                    "dispatch_authorized": False,
                }

            executors[self._deps.settings.approval_delegation_target_agent] = (
                execute_post_approval_planning
            )

        async def execute(task: DelegationTask) -> dict[str, Any]:
            executor = executors.get(task.target_agent)
            if executor is None:
                raise ValueError("delegation_target_unavailable")
            return await executor(task.payload)

        return AgentTaskWorker(
            worker_id=self._worker_id,
            task_bus=self._deps.task_bus,
            subagents=self._deps.subagents,
            executor=execute,
            message_bus=self._deps.message_bus,
        )

    async def run(self, stop_event: asyncio.Event, *, once: bool = False) -> int:
        """Process one task or poll continuously until cancellation."""
        worker = await self._build_worker()
        if once:
            return await worker.run_once()
        await worker.run_forever(
            stop_event,
            self._deps.settings.agent_task_worker_poll_seconds,
        )
        return 0

    async def run_batch(self, stop_event: asyncio.Event) -> int:
        """Run a bounded batch and return non-zero when task execution fails."""
        del stop_event
        worker = await self._build_worker()
        result = await worker.run_batch(
            max_tasks=self._deps.settings.agent_task_worker_max_tasks,
            idle_timeout_seconds=self._deps.settings.agent_task_worker_idle_timeout_seconds,
            poll_seconds=self._deps.settings.agent_task_worker_poll_seconds,
        )
        return 1 if result.failed else 0

    def close(self) -> None:
        """Flush a closeable worker message bus."""
        close = getattr(self._deps.message_bus, "close", None)
        if callable(close):
            close()


def _settings_from_args(args: argparse.Namespace) -> AppSettings:
    settings = get_settings()
    updates = {
        key: value
        for key, value in {
            "agent_task_backend": args.task_backend,
            "agent_task_warehouse_id": args.warehouse_id,
            "agent_task_catalog": args.catalog,
            "agent_task_schema": args.schema,
            "agent_task_worker_poll_seconds": args.poll_seconds,
            "agent_task_worker_max_tasks": args.max_tasks,
            "agent_task_worker_idle_timeout_seconds": args.idle_timeout_seconds,
        }.items()
        if value is not None
    }
    return settings.model_copy(update=updates)


async def _run(args: argparse.Namespace) -> int:
    dependencies = build_worker_dependencies(_settings_from_args(args))
    worker_id = args.worker_id or os.environ.get(
        "DATABRICKS_JOB_RUN_ID",
        f"delegation-worker:{os.getpid()}",
    )
    process = DelegationWorkerProcess(dependencies, worker_id=worker_id)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_number, stop_event.set)
        except NotImplementedError:
            pass
    try:
        if args.once:
            return await process.run(stop_event, once=True)
        return await process.run_batch(stop_event)
    finally:
        process.close()


def main() -> int:
    """CLI entrypoint for the continuous Lakeflow Job task."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id")
    parser.add_argument("--task-backend")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--catalog")
    parser.add_argument("--schema")
    parser.add_argument("--poll-seconds", type=float)
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--idle-timeout-seconds", type=float)
    return asyncio.run(_run(parser.parse_args()))
