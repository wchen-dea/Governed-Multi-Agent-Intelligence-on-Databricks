"""Dependency-driven construction of the MLflow/FastAPI web application."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mlflow.genai.agent_server import AgentServer

from aiserver.api.approvals import router as approval_router
from aiserver.api.health import router as health_router
from aiserver.api.public import router as public_api_router
from aiserver.api.public import v1_router as public_api_v1_router
from aiserver.application.approvals.service import ApprovalService
from aiserver.bootstrap.container import AppDependencyContainer
from aiserver.infrastructure.runtime.mlflow import MlflowAgentRuntime


class ApplicationLifecycle(Protocol):
    """Start and stop application-scoped delivery collaborators."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class WebAppDependencies:
    """Collaborators and resources required by the web delivery process."""

    container: AppDependencyContainer
    approval_service: ApprovalService
    runtime: MlflowAgentRuntime
    ui_dist_dir: Path
    lifecycle: ApplicationLifecycle


@dataclass(frozen=True)
class WebApplication:
    """Return both the AgentServer runner and its FastAPI application."""

    agent_server: AgentServer
    app: FastAPI


def create_web_application(
    dependencies: WebAppDependencies,
    *,
    agent_server_factory: Callable[..., AgentServer] = AgentServer,
) -> WebApplication:
    """Construct one independently testable web application instance."""
    agent_server = agent_server_factory("ResponsesAgent", enable_chat_proxy=True)
    app = agent_server.app
    app.include_router(public_api_router)
    app.include_router(public_api_v1_router)
    app.include_router(approval_router)
    app.include_router(health_router)
    app.state.container = dependencies.container
    app.state.approval_service = dependencies.approval_service
    app.state.runtime = dependencies.runtime
    app.state.ui_dist_dir = dependencies.ui_dist_dir
    app.state.worker_lifecycle = dependencies.lifecycle

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Callable[..., Any]):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    agent_server_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with agent_server_lifespan(app):
            try:
                await dependencies.lifecycle.start()
                yield
            finally:
                await dependencies.lifecycle.stop()
                dependencies.lifecycle.close()

    app.router.lifespan_context = lifespan
    _register_ui_routes(app, dependencies.ui_dist_dir)
    return WebApplication(agent_server=agent_server, app=app)


def create_web_app(
    dependencies: WebAppDependencies,
    *,
    agent_server_factory: Callable[..., AgentServer] = AgentServer,
) -> FastAPI:
    """Construct and return the FastAPI application compatibility surface."""
    return create_web_application(
        dependencies,
        agent_server_factory=agent_server_factory,
    ).app


def _register_ui_routes(app: FastAPI, ui_dist_dir: Path) -> None:
    assets_dir = ui_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="ui-assets")

    @app.get("/")
    def index():
        index_path = ui_dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {
            "status": "ok",
            "message": "Service is running. Use /invocations for agent requests.",
        }

    @app.get("/{path:path}")
    def spa_fallback(path: str):
        candidate = (ui_dist_dir / path).resolve()
        if candidate.is_relative_to(ui_dist_dir.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        index_path = ui_dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Not found")
