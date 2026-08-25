#!/usr/bin/env python3
"""Serve built React UI assets and proxy invoke requests to the backend."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

DEFAULT_DIST_DIR = Path(__file__).resolve().parents[1] / "reactui" / "dist"
REACT_UI_DIST_DIR = Path(os.environ.get("REACT_UI_DIST_DIR", str(DEFAULT_DIST_DIR))).resolve()
BACKEND_PROXY_URL = os.environ.get("FRONTEND_BACKEND_PROXY", "http://localhost:8000/invocations")

REQUEST_HEADER_SKIP = {"host", "content-length", "connection", "accept-encoding"}
RESPONSE_HEADER_ALLOW = {"content-type", "cache-control", "x-request-id", "date"}


def _validate_dist() -> None:
    if not REACT_UI_DIST_DIR.exists():
        raise RuntimeError(
            f"React UI dist not found at {REACT_UI_DIST_DIR}. Run `uv run runtime-build-source` first."
        )


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    _validate_dist()
    yield


app = FastAPI(title="React UI Proxy Server", lifespan=_lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "ui_dist": str(REACT_UI_DIST_DIR),
        "backend_proxy": BACKEND_PROXY_URL,
    }


@app.post("/invocations")
async def proxy_invocations(request: Request) -> StreamingResponse:
    payload = await request.body()

    # Inject session_id for memory persistence when not present in the request.
    try:
        body = json.loads(payload)
        if isinstance(body, dict):
            custom_inputs = body.get("custom_inputs") or {}
            if not custom_inputs.get("session_id") and not (body.get("context") or {}).get("conversation_id"):
                fwd_token = request.headers.get("x-forwarded-access-token", "")
                session_seed = fwd_token[:32] if fwd_token else request.client.host
                custom_inputs["session_id"] = hashlib.sha256(session_seed.encode()).hexdigest()[:24]
                body["custom_inputs"] = custom_inputs
                print(f"[frontend] Injected session_id={custom_inputs['session_id']}")
            payload = json.dumps(body).encode()
    except (json.JSONDecodeError, TypeError) as exc:
        print(f"[frontend] session_id injection skipped: {exc}")

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in REQUEST_HEADER_SKIP
    }

    client = httpx.AsyncClient(timeout=None)
    try:
        backend_response = await client.send(
            client.build_request(
                "POST",
                BACKEND_PROXY_URL,
                content=payload,
                headers=headers,
            ),
            stream=True,
        )
    except Exception as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Backend proxy request failed: {exc}") from exc

    response_headers = {
        key: value
        for key, value in backend_response.headers.items()
        if key.lower() in RESPONSE_HEADER_ALLOW
    }

    async def _stream() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in backend_response.aiter_bytes():
                yield chunk
        finally:
            await backend_response.aclose()
            await client.aclose()

    return StreamingResponse(
        _stream(),
        status_code=backend_response.status_code,
        headers=response_headers,
        media_type=backend_response.headers.get("content-type"),
    )


@app.get("/delegations/{task_id}")
async def proxy_delegation_status(task_id: str, request: Request):
    """Proxy durable delegation status requests to the backend AgentServer."""
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in REQUEST_HEADER_SKIP
    }
    backend_url = BACKEND_PROXY_URL.rsplit("/", 1)[0] + f"/delegations/{task_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(backend_url, headers=headers)
    if not response.is_success:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


assets_dir = REACT_UI_DIST_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(REACT_UI_DIST_DIR / "index.html")


@app.get("/{path:path}")
def spa_fallback(path: str) -> FileResponse:
    candidate = REACT_UI_DIST_DIR / path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(REACT_UI_DIST_DIR / "index.html")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run React UI static server with /invocations proxy"
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("CHAT_APP_PORT", "3000")))
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of Uvicorn worker processes (default: 1)",
    )
    args = parser.parse_args()

    if args.workers > 1:
        uvicorn.run(
            "scripts.react_ui_server:app", host="0.0.0.0", port=args.port, workers=args.workers
        )
        return

    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
