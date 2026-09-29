"""Production entrypoint and default composition for the web application."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from mlflow.genai.agent_server import setup_mlflow_git_based_version_tracking

from aiserver.api import invocations
from aiserver.api.health import router as health_router
from aiserver.api.web import (
    WebAppDependencies,
    WebApplication,
    create_web_application,
)
from aiserver.application.approvals.service import (
    ApprovalService,
    delegation_status_payload,
)
from aiserver.bootstrap.container import (
    AppDependencyContainer,
    get_app_dependency_container,
)
from aiserver.bootstrap.web_lifecycle import WebProcessLifecycle
from aiserver.config.settings import AppSettings, get_settings
from aiserver.contracts.subagents import SUBAGENTS
from aiserver.infrastructure.observability.logging import configure_logging
from aiserver.infrastructure.persistence.approvals import default_approval_repository
from aiserver.infrastructure.runtime.mlflow import MlflowAgentRuntime

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent.parent / ".env", override=True)
configure_logging(get_settings())

if not os.getenv("MLFLOW_EXPERIMENT_ID", "").strip():
    os.environ.pop("MLFLOW_EXPERIMENT_ID", None)

UI_DIST_DIR = Path(
    os.environ.get("AIWEB_DIST_DIR", str(Path(__file__).resolve().parent.parent / "static"))
)


def build_web_dependencies(
    *,
    container: AppDependencyContainer | None = None,
    settings: AppSettings | None = None,
    ui_dist_dir: Path | None = None,
    approval_service: ApprovalService | None = None,
    runtime: MlflowAgentRuntime | None = None,
    lifecycle: WebProcessLifecycle | None = None,
) -> WebAppDependencies:
    """Compose default web dependencies with injectable test seams."""
    resolved_container = container or get_app_dependency_container()
    resolved_settings = settings or get_settings()
    resolved_approval_service = approval_service or ApprovalService(
        repository=default_approval_repository(),
        task_bus=resolved_container.delegation_task_bus,
        message_bus=resolved_container.message_bus,
        settings=resolved_settings,
        subagents=SUBAGENTS,
    )
    resolved_runtime = runtime or MlflowAgentRuntime(
        invoke_handler=invocations.invoke_handler,
        stream_handler=invocations.stream_handler,
    )
    resolved_lifecycle = lifecycle or WebProcessLifecycle(resolved_container)
    return WebAppDependencies(
        container=resolved_container,
        approval_service=resolved_approval_service,
        runtime=resolved_runtime,
        ui_dist_dir=ui_dist_dir or UI_DIST_DIR,
        lifecycle=resolved_lifecycle,
    )


def create_app(**dependency_overrides: object) -> FastAPI:
    """Create an independent FastAPI application for tests or alternate hosts."""
    dependencies = build_web_dependencies(**dependency_overrides)
    return create_web_application(dependencies).app


def _create_default_web_application() -> WebApplication:
    return create_web_application(build_web_dependencies())


_web_application = _create_default_web_application()
agent_server = _web_application.agent_server
app = _web_application.app

# Compatibility exports for callers that imported these helpers from server.py.
health = health_router.routes[0].endpoint
_delegation_status_payload = delegation_status_payload


try:
    setup_mlflow_git_based_version_tracking()
except Exception as exc:
    logging.getLogger(__name__).warning(
        "Skipping MLflow git-based version tracking during local startup: %s", exc
    )


def _resolve_port() -> int | None:
    """Resolve the platform bind port while respecting explicit CLI arguments."""
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


def main() -> None:
    """Run the AgentServer application on the platform-provided port."""
    port = _resolve_port()
    if port is not None:
        sys.argv += ["--port", str(port)]
    workers = _resolve_workers()
    if workers is not None:
        sys.argv += ["--workers", str(workers)]
    agent_server.run(app_import_string="aiserver.api.server:app")
