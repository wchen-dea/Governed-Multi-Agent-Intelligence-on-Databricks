"""Stable application-facing API routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from aiserver.application.runtime.identity import FORWARDED_ACCESS_TOKEN_HEADER
from aiserver.contracts.public_api import ChatRequest
from aiserver.infrastructure.runtime.request_identity import (
    forwarded_access_token_context,
)

router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/api/v1")


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


async def _chat_events(request: Request, payload: ChatRequest) -> AsyncIterator[str]:
    runtime = request.app.state.runtime
    try:
        with forwarded_access_token_context(
            request.headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
        ):
            async for event in runtime.stream(payload):
                if await request.is_disconnected():
                    return
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
@v1_router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    """Execute a public chat request using SSE by default."""
    runtime = request.app.state.runtime
    request_id = getattr(request.state, "request_id", "")
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Request-ID": request_id,
    }
    if payload.stream:
        return StreamingResponse(
            _chat_events(request, payload),
            media_type="text/event-stream",
            headers=headers,
        )
    with forwarded_access_token_context(
        request.headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
    ):
        response = await runtime.invoke(payload)
    return JSONResponse(response, headers=headers)
