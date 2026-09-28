"""Stable application-facing API routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from aiserver.contracts.public_api import ChatRequest
from aiserver.infrastructure.runtime.mlflow import MlflowAgentRuntime

router = APIRouter(prefix="/api")
_runtime = MlflowAgentRuntime()


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


async def _chat_events(request: ChatRequest) -> AsyncIterator[str]:
    try:
        async for event in _runtime.stream(request):
            yield _sse(event)
    except Exception:
        yield _sse(
            {
                "type": "error",
                "error": {
                    "code": "runtime_error",
                    "message": "The agent runtime could not complete the request.",
                },
            }
        )


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    """Execute a public chat request using SSE by default."""
    del request
    if payload.stream:
        return StreamingResponse(
            _chat_events(payload),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return JSONResponse(await _runtime.invoke(payload))