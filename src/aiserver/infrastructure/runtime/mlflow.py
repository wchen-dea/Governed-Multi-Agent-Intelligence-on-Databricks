"""MLflow Agent Server adapter for the application runtime port."""

from collections.abc import AsyncIterator
from typing import Any

from mlflow.types.responses import ResponsesAgentRequest

from aiserver.contracts.public_api import ChatRequest


def _runtime_request(request: ChatRequest) -> ResponsesAgentRequest:
    """Translate the public request into the MLflow Responses API shape."""
    custom_inputs = {"persona": request.persona} if request.persona else None
    return ResponsesAgentRequest(
        input=[message.model_dump() for message in request.messages],
        custom_inputs=custom_inputs,
        context={"conversation_id": request.conversation_id},
    )


def _event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump()
    if isinstance(event, dict):
        return event
    return {"type": str(getattr(event, "type", "unknown"))}


class MlflowAgentRuntime:
    """Delegate execution to the existing MLflow-registered handlers."""

    async def invoke(self, request: ChatRequest) -> dict[str, Any]:
        from aiserver.api.invocations import invoke_handler

        response = await invoke_handler(_runtime_request(request))
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        from aiserver.api.invocations import stream_handler

        async for event in stream_handler(_runtime_request(request)):
            raw = _event_dict(event)
            event_type = raw.get("type")
            if event_type == "response.output_text.delta":
                delta = raw.get("delta")
                if isinstance(delta, str) and delta:
                    yield {"type": "text_delta", "delta": delta}
            elif event_type == "response.governance":
                yield {"type": "metadata", "metadata": raw.get("response_envelope", {})}
            elif event_type not in {"response.progress", "response.output_item.added"}:
                # Preserve useful runtime metadata without exposing runtime event names.
                if event_type:
                    yield {"type": "metadata", "metadata": raw}
        yield {"type": "completed"}