"""Server bootstrap for the MLflow AgentServer runtime."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

from aiserver.api.dependencies import get_app_dependency_container
from aiserver.domain.subagent_config import SUBAGENTS
from aiserver.services.agent_task_worker import AgentTaskWorker
from aiserver.services.orchestrator_service import build_lakebase_delegation_executors
from aiserver.shared.logging_config import configure_logging
from aiserver.shared.runtime_utils import build_request_identity_context
from aiserver.shared.settings import get_settings

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env", override=True)
configure_logging(get_settings())

if not os.getenv("MLFLOW_EXPERIMENT_ID", "").strip():
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)

# Ensure @invoke/@stream handlers are registered.
import aiserver.api.handlers  # noqa: E402, F401

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
app = agent_server.app
_worker_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task[None] | None = None
_agent_server_lifespan = app.router.lifespan_context


@app.get("/")
def root():
    """Return a simple service status payload for root path probes."""
    return {
        "status": "ok",
        "message": "Service is running. Use /health for readiness or /invocations for agent requests.",
    }


def _delegation_status_payload(record) -> dict[str, object]:
    """Return user-safe delegation status without exposing task input payloads."""
    result = record.result
    return {
        "task_id": record.task.task_id,
        "correlation_id": record.task.correlation_id,
        "source_agent": record.task.source_agent,
        "target_agent": record.task.target_agent,
        "intent": record.task.intent,
        "status": record.status,
        "attempt": record.task.attempt,
        "max_attempts": record.task.max_attempts,
        "failure_code": record.failure_code or (result.error_code if result else None),
        "completed": result is not None,
    }


@app.get("/delegations/{task_id}")
async def get_delegation_status(task_id: str) -> dict[str, object]:
    """Return the lifecycle state of an accepted delegation task."""
    record = await get_app_dependency_container().delegation_task_bus.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Delegation task not found")
    return _delegation_status_payload(record)


async def _start_delegation_worker() -> None:
    """Start the opt-in worker that processes durable delegation tasks."""
    global _worker_stop_event, _worker_task
    settings = get_settings()
    if not settings.agent_task_worker_enabled:
        return
    container = get_app_dependency_container()
    executors = build_lakebase_delegation_executors(SUBAGENTS, build_request_identity_context())

    async def execute(task):
        executor = executors.get(task.target_agent)
        if executor is None:
            raise ValueError("delegation_target_unavailable")
        return await executor(task.payload)

    _worker_stop_event = asyncio.Event()
    worker = AgentTaskWorker(
        worker_id=f"app-worker:{os.getpid()}",
        task_bus=container.delegation_task_bus,
        subagents=SUBAGENTS,
        executor=execute,
        message_bus=container.handlers.message_bus,
    )
    _worker_task = asyncio.create_task(
        worker.run_forever(_worker_stop_event, settings.agent_task_worker_poll_seconds)
    )


async def _stop_delegation_worker() -> None:
    """Stop the delegation worker cleanly during backend shutdown."""
    global _worker_stop_event, _worker_task
    if _worker_stop_event is not None:
        _worker_stop_event.set()
    if _worker_task is not None:
        await _worker_task
    _worker_stop_event = None
    _worker_task = None


@asynccontextmanager
async def _lifespan(_: object) -> AsyncIterator[None]:
    """Preserve AgentServer lifecycle behavior while managing delegation work."""
    async with _agent_server_lifespan(app):
        await _start_delegation_worker()
        try:
            yield
        finally:
            await _stop_delegation_worker()


app.router.lifespan_context = _lifespan


try:
    setup_mlflow_git_based_version_tracking()
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Skipping MLflow git-based version tracking during local startup: %s", exc
    )


def main():
    """Run the AgentServer application."""
    agent_server.run(app_import_string="aiserver.api.server:app")
