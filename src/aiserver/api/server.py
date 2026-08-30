"""Server bootstrap for the MLflow AgentServer runtime."""

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

from aiserver.api.models import ApprovalDecisionInput
from aiserver.application.delegation.policy import evaluate_delegation_policy
from aiserver.application.delegation.worker import AgentTaskWorker
from aiserver.application.orchestration.agent import (
    build_lakebase_delegation_executors,
)
from aiserver.application.ports.audit import ApprovalRepository
from aiserver.application.runtime.identity import build_request_identity_context
from aiserver.bootstrap.container import get_app_dependency_container
from aiserver.config.settings import get_settings
from aiserver.contracts.delegation import DelegationTask
from aiserver.contracts.responses import ApprovalDecisionRecord, ApprovalDecisionRequest
from aiserver.contracts.subagents import SUBAGENTS
from aiserver.infrastructure.observability.logging import configure_logging
from aiserver.infrastructure.persistence.approvals import default_approval_repository

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env", override=True)
configure_logging(get_settings())

if not os.getenv("MLFLOW_EXPERIMENT_ID", "").strip():
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)

# Ensure @invoke/@stream handlers are registered.
import aiserver.api.invocations  # noqa: E402, F401

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
app = agent_server.app
_worker_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task[None] | None = None
_agent_server_lifespan = app.router.lifespan_context

# Built React UI assets, bundled inside this package's wheel (see
# prepare_app_source.py). Override with AIWEB_DIST_DIR for local iteration
# against a dist/ built outside the installed package.
UI_DIST_DIR = Path(
    os.environ.get("AIWEB_DIST_DIR", str(Path(__file__).resolve().parent.parent / "static"))
)


@app.get("/health")
def health():
    """Return a simple service status payload for readiness probes."""
    return {
        "status": "ok",
        "message": "Service is running. Use /invocations for agent requests.",
        "ui_dist": str(UI_DIST_DIR),
    }


_APPROVAL_REPOSITORY: ApprovalRepository = default_approval_repository()


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


def _approval_payload(record: ApprovalDecisionRecord) -> dict[str, object]:
    """Return the public approval response payload."""
    return {
        "request_id": record.request_id,
        "agent_name": record.agent_name,
        "store_id": record.store_id,
        "approver": record.approver,
        "decision": record.decision,
        "reason": record.reason,
        "notes": record.notes,
        "status": record.status,
    }


def _post_approval_task(record: ApprovalDecisionRecord) -> DelegationTask:
    """Build the durable planning task created after manager approval."""
    settings = get_settings()
    return DelegationTask(
        source_agent=settings.approval_delegation_source_agent,
        target_agent=settings.approval_delegation_target_agent,
        intent=settings.approval_delegation_intent,
        payload={
            "approval_request_id": record.request_id,
            "agent_name": record.agent_name,
            "store_id": record.store_id,
            "approver": record.approver,
            "approval_reason": record.reason,
            "approval_notes": record.notes,
            "planning_only": True,
            "dispatch_authorized": False,
        },
        correlation_id=record.request_id,
        idempotency_key=(
            f"approval:{record.request_id}:{settings.approval_delegation_target_agent}:"
            f"{settings.approval_delegation_intent}"
        ),
        data_classification="confidential",
        auth_mode="app",
    )


async def _submit_post_approval_task(
    record: ApprovalDecisionRecord,
) -> dict[str, object] | None:
    """Create a durable planning-only delegation task after approval."""
    settings = get_settings()
    if record.decision != "approved" or not settings.approval_delegation_enabled:
        return None

    task = _post_approval_task(record)
    decision = evaluate_delegation_policy(task, SUBAGENTS)
    if not decision.allowed:
        get_app_dependency_container().handlers.message_bus.publish(
            "approval.delegation.rejected",
            {
                "request_id": record.request_id,
                "target_agent": task.target_agent,
                "intent": task.intent,
                "reason_code": decision.reason_code,
            },
        )
        raise HTTPException(
            status_code=409,
            detail=f"Approved follow-up task rejected by delegation policy: {decision.reason_code}",
        )

    task_record = await get_app_dependency_container().delegation_task_bus.submit(task)
    payload = _delegation_status_payload(task_record)
    get_app_dependency_container().handlers.message_bus.publish(
        "approval.delegation.created",
        payload,
    )
    return payload


@app.post("/approval-decisions")
async def submit_approval_decision(payload: ApprovalDecisionInput) -> dict[str, object]:
    """Record a manager decision for a pending approval workflow."""
    request = ApprovalDecisionRequest(
        request_id=payload.request_id,
        agent_name=payload.agent_name,
        store_id=payload.store_id,
        approver=payload.approver,
        decision=payload.decision,
        reason=payload.reason,
        notes=payload.notes,
    )

    record = ApprovalDecisionRecord(
        request_id=request.request_id,
        agent_name=request.agent_name,
        store_id=request.store_id,
        approver=request.approver,
        decision=request.decision,
        reason=request.reason,
        notes=request.notes,
        status=request.decision,
    )
    _APPROVAL_REPOSITORY.save(record)
    delegation = await _submit_post_approval_task(record)
    return {
        "status": "ok",
        "approval": _approval_payload(record),
        "delegation": delegation,
    }


@app.get("/approval-decisions/{request_id}")
async def get_approval_decision(request_id: str) -> dict[str, object]:
    """Return a persisted approval decision by request ID."""
    record = _APPROVAL_REPOSITORY.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval decision not found")
    return {
        "status": "ok",
        "approval": _approval_payload(record),
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
    executors = build_lakebase_delegation_executors(
        SUBAGENTS,
        build_request_identity_context(),
        deps=container.orchestrator,
    )
    settings = get_settings()
    if settings.approval_delegation_enabled:
        async def execute_post_approval_planning(payload: dict[str, object]) -> dict[str, object]:
            return {
                "result": "approved_planning_task_recorded",
                "approval_request_id": payload.get("approval_request_id"),
                "planning_only": True,
                "dispatch_authorized": False,
            }

        executors[settings.approval_delegation_target_agent] = execute_post_approval_planning

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


def _close_message_bus() -> None:
    """Flush closeable lifecycle event adapters during graceful shutdown."""
    message_bus = get_app_dependency_container().handlers.message_bus
    close = getattr(message_bus, "close", None)
    if callable(close):
        close()


@asynccontextmanager
async def _lifespan(_: object) -> AsyncIterator[None]:
    """Preserve AgentServer lifecycle behavior while managing delegation work."""
    async with _agent_server_lifespan(app):
        await _start_delegation_worker()
        try:
            yield
        finally:
            await _stop_delegation_worker()
            _close_message_bus()


app.router.lifespan_context = _lifespan

# Serve the built React UI (assets + SPA fallback) in-process. Registered
# after every API route above so it never shadows /invocations, /delegations,
# or MLflow AgentServer's own routes — Starlette matches routes in
# registration order.
_ui_assets_dir = UI_DIST_DIR / "assets"
if _ui_assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=_ui_assets_dir), name="ui-assets")


@app.get("/")
def index():
    index_path = UI_DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "status": "ok",
        "message": "Service is running. Use /invocations for agent requests.",
    }


@app.get("/{path:path}")
def spa_fallback(path: str):
    # Resolve and confirm containment before serving, since "path" is
    # attacker-controlled and may contain traversal segments (e.g. "../../etc/passwd").
    candidate = (UI_DIST_DIR / path).resolve()
    if candidate.is_relative_to(UI_DIST_DIR.resolve()) and candidate.is_file():
        return FileResponse(candidate)
    index_path = UI_DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")


try:
    setup_mlflow_git_based_version_tracking()
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Skipping MLflow git-based version tracking during local startup: %s", exc
    )


def _resolve_port() -> int | None:
    """Resolve the bind port Databricks Apps (or a local override) expects.

    Priority: an explicit --port already on argv (leave AgentServer's own
    parsing alone), then DATABRICKS_APP_PORT/PORT/CHAT_APP_PORT, else None to
    keep AgentServer's built-in default (8000).
    """
    if "--port" in sys.argv:
        return None
    for env_var in ("DATABRICKS_APP_PORT", "PORT", "CHAT_APP_PORT"):
        raw = os.environ.get(env_var)
        if raw:
            try:
                return int(raw)
            except ValueError:
                continue
    return None


def _resolve_workers() -> int | None:
    if "--workers" in sys.argv:
        return None
    for env_var in ("BACKEND_UVICORN_WORKERS", "WEB_CONCURRENCY"):
        raw = os.environ.get(env_var)
        if raw:
            try:
                return max(int(raw), 1)
            except ValueError:
                continue
    return None


def main():
    """Run the AgentServer application, binding to the platform-provided port."""
    port = _resolve_port()
    if port is not None:
        sys.argv += ["--port", str(port)]
    workers = _resolve_workers()
    if workers is not None:
        sys.argv += ["--workers", str(workers)]
    agent_server.run(app_import_string="aiserver.api.server:app")
