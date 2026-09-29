"""MLflow Agent Server delivery adapter for governed execution."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

import mlflow
from agents import set_default_openai_api, set_default_openai_client
from agents.exceptions import UserError
from agents.tracing import add_trace_processor, set_trace_processors
from deepeval.openai_agents import DeepEvalTracingProcessor
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from aiserver.application.exceptions import GovernedExecutionError
from aiserver.application.runtime.identity import get_session_id
from aiserver.bootstrap.container import get_app_dependency_container
from aiserver.contracts.execution import ExecutionMessage, GovernedExecutionRequest
from aiserver.contracts.subagents import SUBAGENTS
from aiserver.infrastructure.runtime.request_identity import get_forwarded_access_token

logger = logging.getLogger(__name__)
_container = get_app_dependency_container()
_execution_service = _container.execution_service

set_default_openai_client(_container.app_client)
set_default_openai_api("responses")
set_trace_processors([])
add_trace_processor(DeepEvalTracingProcessor())
cast(Any, mlflow).openai.autolog()

if not SUBAGENTS:
    logger.warning("No subagents configured. The orchestrator will run without routing tools.")


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    """Translate an MLflow request to the governed invoke use case."""
    try:
        result = await _execution_service.invoke(_execution_request(request))
    except GovernedExecutionError as exc:
        raise UserError(str(exc)) from exc
    return ResponsesAgentResponse(output=cast(Any, list(result.output_items)))


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Translate governed stream events to MLflow Responses API events."""
    try:
        async for event in _execution_service.stream(_execution_request(request)):
            if event.kind == "runtime":
                runtime_event = event.payload.get("event")
                if isinstance(runtime_event, dict):
                    yield cast(Any, runtime_event)
                else:
                    logger.warning("Ignoring runtime stream event without a dictionary payload")
            elif event.kind == "progress":
                yield cast(
                    Any,
                    {
                        "type": "response.progress",
                        "stage": event.payload.get("stage", ""),
                    },
                )
            elif event.kind == "governance":
                yield cast(
                    Any,
                    {
                        "type": "response.governance",
                        "response_envelope": event.payload.get("response_envelope", {}),
                    },
                )
            elif event.kind == "text_delta":
                yield cast(
                    Any,
                    {
                        "type": "response.output_text.delta",
                        "item_id": event.payload.get("item_id", "item_application"),
                        "delta": event.payload.get("delta", ""),
                    },
                )
            else:
                logger.warning(
                    "Ignoring unsupported execution stream event kind: %s",
                    event.kind,
                )
    except GovernedExecutionError as exc:
        raise UserError(str(exc)) from exc


def _execution_request(request: ResponsesAgentRequest) -> GovernedExecutionRequest:
    custom_inputs = dict(request.custom_inputs) if isinstance(request.custom_inputs, dict) else {}
    persona = custom_inputs.pop("persona", None)
    persona = persona.strip().lower() or None if isinstance(persona, str) else None
    messages: list[ExecutionMessage] = []
    for item in request.input:
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if not isinstance(data, dict):
            continue
        role = data.get("role")
        if role not in {"user", "assistant", "system", "developer", "tool"}:
            continue
        content = data.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        text = str(content).strip()
        if text:
            messages.append(ExecutionMessage(role=role, content=text))

    conversation_id = None
    if request.context and request.context.conversation_id:
        conversation_id = request.context.conversation_id
    else:
        session_id = custom_inputs.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            conversation_id = session_id.strip()
    execution_request = GovernedExecutionRequest(
        messages=tuple(messages),
        conversation_id=conversation_id,
        persona=persona,
        metadata=custom_inputs,
    )
    if conversation_id:
        return execution_request
    resolved_session_id = get_session_id(
        execution_request,
        get_forwarded_access_token(),
    )
    return GovernedExecutionRequest(
        messages=execution_request.messages,
        conversation_id=resolved_session_id,
        persona=execution_request.persona,
        metadata=execution_request.metadata,
    )
