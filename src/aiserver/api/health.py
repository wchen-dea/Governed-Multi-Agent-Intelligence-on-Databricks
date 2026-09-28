"""Health and readiness endpoints."""

from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter()


def _payload(request: Request) -> dict[str, object]:
    ui_dist = getattr(request.app.state, "ui_dist_dir", Path(""))
    return {
        "status": "ok",
        "message": "Service is running. Use /invocations for agent requests.",
        "ui_dist": str(ui_dist),
    }


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return _payload(request)


@router.get("/api/health")
@router.get("/api/v1/health")
def public_health(request: Request) -> dict[str, object]:
    return _payload(request)


@router.get("/ready")
@router.get("/api/ready")
@router.get("/api/v1/ready")
def readiness(request: Request) -> dict[str, object]:
    container = getattr(request.app.state, "container", None)
    if container is None:
        return {"status": "not_ready"}
    return {"status": "ready"}
