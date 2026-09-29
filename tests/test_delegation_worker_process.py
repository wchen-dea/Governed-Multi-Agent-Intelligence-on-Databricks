"""Tests for the standalone durable delegation-worker process."""

import asyncio

import pytest

from aiserver.application.orchestration.agent import OrchestratorDependencies
from aiserver.config.settings import AppSettings, validate_durable_runtime_configuration
from aiserver.contracts.delegation import DelegationTask
from aiserver.contracts.subagents import SubagentConfig
from aiserver.infrastructure.persistence.tasks import InMemoryAgentTaskBus
from aiserver.worker import main as worker_module
from aiserver.worker.main import (
    DelegationWorkerProcess,
    WorkerDependencies,
    build_worker_dependencies,
)


class RecordingBus:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.closed = False

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        del payload
        self.events.append(event_type)

    def close(self) -> None:
        self.closed = True


def _target() -> SubagentConfig:
    return SubagentConfig(
        name="lakebase_ods_agent",
        kind="lakebase",
        project_id="ore",
        branch_id="production",
        database="operations",
        pg_host="lakebase.example.com",
        endpoint_id="primary",
        description="appointment data",
        accepts_delegations_from=("operations_coordinator",),
        allowed_task_intents=("appointment_summary",),
    )


def test_worker_dependencies_reject_process_local_task_backend():
    with pytest.raises(ValueError, match="requires AGENT_TASK_BACKEND=uc_table"):
        build_worker_dependencies(AppSettings(agent_task_backend="memory"))


def test_worker_process_executes_one_durable_task_and_closes_bus(monkeypatch):
    async def run() -> None:
        task_bus = InMemoryAgentTaskBus()
        message_bus = RecordingBus()
        target = _target()
        task = DelegationTask(
            source_agent="operations_coordinator",
            target_agent=target.name,
            intent="appointment_summary",
            payload={"date": "latest"},
            correlation_id="corr-1",
            idempotency_key="idem-1",
        )
        await task_bus.submit(task)

        async def execute(payload):
            return {"result": payload["date"]}

        monkeypatch.setattr(
            worker_module,
            "build_lakebase_delegation_executors",
            lambda subagents, identity, deps: {target.name: execute},
        )
        dependencies = WorkerDependencies(
            settings=AppSettings(
                agent_task_backend="uc_table",
                approval_delegation_enabled=False,
            ),
            subagents=[target],
            task_bus=task_bus,
            message_bus=message_bus,
            orchestrator=OrchestratorDependencies(message_bus=message_bus),
        )
        process = DelegationWorkerProcess(
            dependencies,
            worker_id="worker-run-1",
            identity_context_provider=lambda: object(),
        )

        assert await process.run(asyncio.Event(), once=True) == 1
        process.close()

        record = await task_bus.get(task.task_id)
        assert record is not None
        assert record.status == "succeeded"
        assert record.result is not None
        assert record.result.output == {"result": "latest"}
        assert message_bus.events == [
            "delegation.task.claimed",
            "delegation.task.completed",
        ]
        assert message_bus.closed is True

    asyncio.run(run())


def test_production_requires_durable_correctness_backends():
    with pytest.raises(ValueError, match="Durable backends are required"):
        validate_durable_runtime_configuration(AppSettings(deployment_environment="production"))


def test_local_runtime_allows_in_memory_backends():
    validate_durable_runtime_configuration(AppSettings(deployment_environment="local"))
