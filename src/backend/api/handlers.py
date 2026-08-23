"""Orchestrate multi-agent request routing handlers."""

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, AsyncGenerator, cast

import mlflow
from agents import Runner, set_default_openai_api, set_default_openai_client
from agents.exceptions import UserError
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from backend.api.dependencies import get_handler_dependencies
from backend.domain.subagent_config import SUBAGENTS, SubagentConfig
from backend.shared.request_utils import extract_mcp_errors, to_messages
from backend.shared.settings import get_settings
from backend.shared.runtime_utils import process_agent_stream_events
from backend.services.guardrails_service import truncate_response_text
from backend.domain.execution_contracts import ResponseEnvelope
from backend.services.route_planner import build_route_plan

SETTINGS = get_settings()
HANDLER_DEPS = get_handler_dependencies()


def _build_openai_client() -> AsyncDatabricksOpenAI:
    """Build Databricks OpenAI client with optional runtime overrides.

    The defaults keep existing behavior. Operators can opt in to alternate
    routing (for example Unity AI Gateway) by setting `DATABRICKS_OPENAI_BASE_URL`.
    """
    kwargs: dict[str, Any] = {}
    if SETTINGS.openai_base_url.strip():
        kwargs["base_url"] = SETTINGS.openai_base_url.strip()
    if SETTINGS.openai_timeout_seconds > 0:
        kwargs["timeout"] = SETTINGS.openai_timeout_seconds
    return AsyncDatabricksOpenAI(**kwargs)


_client = _build_openai_client()
set_default_openai_client(_client)
set_default_openai_api("responses")
set_trace_processors([])
cast(Any, mlflow).openai.autolog()
logger = logging.getLogger(__name__)
if not SUBAGENTS:
    logger.warning("No subagents configured. The orchestrator will run without routing tools.")


@dataclass(frozen=True)
class RequestStage:
    """Represent prepared request inputs for pipeline execution."""

    request: ResponsesAgentRequest
    runtime_auth: Any
    messages: list[Any]


@dataclass(frozen=True)
class ConnectedStage:
    """Represent connected tooling and agent state for request execution."""

    runtime_auth: Any
    unavailable: list[str]
    agent: Any


@dataclass(frozen=True)
class InvokeFinalizedStage:
    """Represent finalized invoke output and metadata after guardrails."""

    output_items: list[dict[str, Any]]
    unavailable: list[str]
    envelope: ResponseEnvelope


@dataclass(frozen=True)
class StreamExecutedStage:
    """Represent buffered stream output with precomputed guardrail inputs."""

    event_count: int
    buffered_events: list[Any]
    streamed_text_parts: list[str]
    used_subagents: list[SubagentConfig]
    has_tool_activity: bool


@dataclass(frozen=True)
class StreamFinalizedStage:
    """Represent finalized stream output and guardrail decision."""

    event_count: int
    buffered_events: list[Any]
    source_suffix: str
    unavailable: list[str]
    guardrail_blocked: bool
    guardrail_reasons: tuple[str, ...]
    envelope: ResponseEnvelope


def _prepare_request_stage(request: ResponsesAgentRequest) -> RequestStage:
    """Build request-scoped auth context and normalized messages.

    Args:
        request: Incoming Responses API request.

    Returns:
        Prepared request stage with runtime auth context and messages.
    """
    input_guardrail = HANDLER_DEPS.input_guardrails_evaluator(
        request.input,
        max_input_chars=SETTINGS.max_input_chars,
    )
    if input_guardrail.blocked:
        HANDLER_DEPS.message_bus.publish(
            "request.guardrail.blocked",
            {
                "phase": "input",
                "reasons": list(input_guardrail.reasons),
                "character_count": input_guardrail.character_count,
            },
        )
        raise UserError("Request blocked by input guardrails: " + ", ".join(input_guardrail.reasons))

    runtime_auth = HANDLER_DEPS.runtime_auth_builder(request, SUBAGENTS, _client)
    messages = to_messages(request.input)
    return RequestStage(request=request, runtime_auth=runtime_auth, messages=messages)


async def _connect_request_stage(
    stack: AsyncExitStack,
    prepared: RequestStage,
) -> ConnectedStage:
    """Connect MCP servers and build the orchestrator agent.

    Args:
        stack: Async context stack used for MCP server lifecycle.
        prepared: Prepared request stage.

    Returns:
        Connected stage with orchestrator agent and unavailable details.
    """
    question = ""
    for message in reversed(prepared.messages):
        data = message.model_dump() if hasattr(message, "model_dump") else message
        if isinstance(data, dict) and data.get("role") == "user":
            question = str(data.get("content", ""))
            break
    route_plan, route_candidates = build_route_plan(
        question,
        prepared.runtime_auth.policy_allowed_subagents,
    )
    candidate_names = {candidate.name for candidate in route_candidates}
    planned_mcp_servers = [
        server
        for server in prepared.runtime_auth.mcp_servers
        if str(getattr(server, "name", "")).split(":", 1)[-1] in candidate_names
    ]
    if (
        not planned_mcp_servers
        and prepared.runtime_auth.mcp_servers
        and route_plan.reason == "ambiguous_fallback"
    ):
        planned_mcp_servers = prepared.runtime_auth.mcp_servers
    servers, unavailable_health = await HANDLER_DEPS.mcp_connector(
        stack, planned_mcp_servers
    )
    unavailable = prepared.runtime_auth.unavailable_auth + unavailable_health
    candidate_tools = [
        tool
        for tool in prepared.runtime_auth.subagent_tools
        if getattr(tool, "__name__", "").removeprefix("query_") in candidate_names
    ]
    if not candidate_tools and prepared.runtime_auth.subagent_tools:
        candidate_tools = prepared.runtime_auth.subagent_tools
    agent = HANDLER_DEPS.orchestrator_factory(
        SETTINGS.orchestrator_model,
        route_candidates,
        servers,
        candidate_tools,
        unavailable,
    )
    HANDLER_DEPS.message_bus.publish(
        "routing.plan.selected",
        {
            "candidates": list(route_plan.candidates),
            "reason": route_plan.reason,
            "confidence": route_plan.confidence,
            "requires_evidence": route_plan.requires_evidence,
        },
    )
    return ConnectedStage(
        runtime_auth=prepared.runtime_auth,
        unavailable=unavailable,
        agent=agent,
    )


_TRANSIENT_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.0


def _is_transient(exc: BaseException) -> bool:
    """Return True for connection errors worth retrying."""
    name = type(exc).__name__
    return "APIConnectionError" in name or "ConnectionError" in name


async def _execute_invoke_stage(
    connected: ConnectedStage,
    messages: list[Any],
) -> Any:
    """Run the orchestrator agent for invoke with retry on transient errors."""
    last_exc: BaseException | None = None
    for attempt in range(_TRANSIENT_RETRIES + 1):
        try:
            return await Runner.run(connected.agent, messages)
        except Exception as exc:
            if not _is_transient(exc) or attempt >= _TRANSIENT_RETRIES:
                raise
            last_exc = exc
            logger.warning("Transient error on invoke attempt %d, retrying: %s", attempt + 1, exc)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_exc  # unreachable but satisfies type checker


def _finalize_invoke_stage(
    result: Any,
    connected: ConnectedStage,
) -> InvokeFinalizedStage:
    """Apply governed source formatting and guardrails to invoke output.

    Args:
        result: Runner output from agent execution.
        connected: Connected invoke stage with runtime auth context.

    Returns:
        Finalized invoke stage containing output items and unavailable details.

    Raises:
        UserError: If response is blocked by guardrails.
    """
    response_text = _response_text_from_items(result.new_items)
    output_items = cast(Any, [item.to_input_item() for item in result.new_items])
    guardrail_subagents = _guardrail_scope_subagents(
        output_items,
        connected.runtime_auth.policy_allowed_subagents,
    )
    source_suffix = _governed_source_suffix_with_fallback(
        output_items,
        guardrail_subagents,
    )
    if source_suffix and source_suffix not in response_text:
        response_text += source_suffix
        output_items = _append_source_to_output_items(output_items, source_suffix)
    response_text, truncated = truncate_response_text(
        response_text,
        max_response_chars=SETTINGS.max_response_chars,
    )
    if truncated:
        output_items = _truncate_output_items(
            output_items,
            max_response_chars=SETTINGS.max_response_chars,
        )
    guardrail = HANDLER_DEPS.guardrails_evaluator(
        response_text,
        guardrail_subagents,
    )
    if guardrail.blocked:
        HANDLER_DEPS.message_bus.publish(
            "response.guardrail.blocked",
            {
                "reasons": list(guardrail.reasons),
                "truncated": truncated,
            },
        )
        raise UserError(
            "Response blocked by guardrails: " + ", ".join(guardrail.reasons)
        )
    HANDLER_DEPS.message_bus.publish(
        "response.guardrail.passed",
        {
            "reasons": list(guardrail.reasons),
            "truncated": truncated,
        },
    )
    return InvokeFinalizedStage(
        output_items=output_items,
        unavailable=connected.unavailable,
        envelope=ResponseEnvelope(
            status="truncated" if truncated else "succeeded",
            answer_chars=len(response_text),
            truncated=truncated,
            guardrail_reasons=guardrail.reasons,
            source_metadata=(source_suffix,) if source_suffix else (),
        ),
    )


async def _execute_stream_stage(
    connected: ConnectedStage,
    messages: list[Any],
) -> StreamExecutedStage:
    """Run streamed orchestration with retry on transient errors."""
    last_exc: BaseException | None = None
    for attempt in range(_TRANSIENT_RETRIES + 1):
        try:
            return await _execute_stream_stage_inner(connected, messages)
        except Exception as exc:
            if not _is_transient(exc) or attempt >= _TRANSIENT_RETRIES:
                raise
            last_exc = exc
            logger.warning("Transient error on stream attempt %d, retrying: %s", attempt + 1, exc)
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_exc  # unreachable


async def _execute_stream_stage_inner(
    connected: ConnectedStage,
    messages: list[Any],
) -> StreamExecutedStage:
    """Run streamed orchestration and precompute finalization inputs."""
    result = Runner.run_streamed(connected.agent, input=messages)
    event_count = 0
    buffered_events: list[Any] = []
    streamed_text_parts: list[str] = []
    used_subagents: list[SubagentConfig] = []
    seen_subagents: set[str] = set()
    has_tool_activity = False
    allowed_subagents = connected.runtime_auth.policy_allowed_subagents

    async for event in process_agent_stream_events(result.stream_events()):
        event_count += 1
        buffered_events.append(event)
        text = _text_from_stream_event(event)
        if text:
            streamed_text_parts.append(text)

        if not isinstance(event, dict):
            continue

        if _payload_has_tool_activity(event):
            has_tool_activity = True

        for candidate in _candidate_tool_names(event):
            subagent = _resolve_subagent(candidate, allowed_subagents)
            if subagent is None or subagent.name in seen_subagents:
                continue
            seen_subagents.add(subagent.name)
            used_subagents.append(subagent)

    return StreamExecutedStage(
        event_count=event_count,
        buffered_events=buffered_events,
        streamed_text_parts=streamed_text_parts,
        used_subagents=used_subagents,
        has_tool_activity=has_tool_activity,
    )


def _finalize_stream_stage(
    executed: StreamExecutedStage,
    connected: ConnectedStage,
) -> StreamFinalizedStage:
    """Apply governed source handling and guardrails to buffered stream output.

    Args:
        executed: Buffered stream execution stage.
        connected: Connected stage with runtime auth context.

    Returns:
        Finalized stream stage with guardrail decision and output metadata.
    """
    if executed.used_subagents:
        guardrail_subagents = executed.used_subagents
    elif executed.has_tool_activity:
        guardrail_subagents = [
            subagent
            for subagent in connected.runtime_auth.policy_allowed_subagents
            if subagent.requires_evidence
        ]
    else:
        guardrail_subagents = []

    source_suffix = _governed_source_suffix(executed.used_subagents)
    if not source_suffix and guardrail_subagents and executed.has_tool_activity:
        source_suffix = "\n\nSource: tool-backed governed response."

    streamed_text_parts = list(executed.streamed_text_parts)
    stream_text = "\n".join(streamed_text_parts)
    if source_suffix and source_suffix not in stream_text:
        streamed_text_parts.append(source_suffix)
        stream_text = "\n".join(streamed_text_parts)

    stream_text, truncated = truncate_response_text(
        stream_text,
        max_response_chars=SETTINGS.max_response_chars,
    )

    guardrail = HANDLER_DEPS.guardrails_evaluator(
        stream_text,
        guardrail_subagents,
    )
    if guardrail.blocked:
        HANDLER_DEPS.message_bus.publish(
            "response.guardrail.blocked",
            {
                "reasons": list(guardrail.reasons),
                "mode": "stream",
                "truncated": truncated,
            },
        )
    else:
        HANDLER_DEPS.message_bus.publish(
            "response.guardrail.passed",
            {
                "reasons": list(guardrail.reasons),
                "mode": "stream",
                "truncated": truncated,
            },
        )

    return StreamFinalizedStage(
        event_count=executed.event_count,
        buffered_events=executed.buffered_events,
        source_suffix=source_suffix,
        unavailable=connected.unavailable,
        guardrail_blocked=guardrail.blocked,
        guardrail_reasons=guardrail.reasons,
        envelope=ResponseEnvelope(
            status="blocked" if guardrail.blocked else ("truncated" if truncated else "succeeded"),
            answer_chars=len(stream_text),
            truncated=truncated,
            guardrail_reasons=guardrail.reasons,
            source_metadata=(source_suffix,) if source_suffix else (),
        ),
    )


def _response_text_from_items(items: list[Any]) -> str:
    """Extract plain text from output items for guardrail evaluation."""
    chunks: list[str] = []
    for item in items:
        data = item.to_input_item() if hasattr(item, "to_input_item") else item
        if not isinstance(data, dict):
            continue
        content = data.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
    return "\n".join(chunks).strip()


def _text_from_stream_event(event: Any) -> str:
    """Extract text fragments from normalized stream events."""
    data = event.model_dump() if hasattr(event, "model_dump") else event
    if not isinstance(data, dict):
        return ""

    if data.get("type") == "response.output_text.delta":
        delta = data.get("delta")
        return delta if isinstance(delta, str) else ""

    item = data.get("item")
    if isinstance(item, dict):
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            return " ".join(chunks)
    return ""


def _guardrail_block_message(reasons: tuple[str, ...]) -> str:
    """Format a safe, user-facing explanation for blocked responses."""
    reason_list = ", ".join(reasons) if reasons else "policy_check_failed"
    return (
        "I couldn't return the answer because the response was blocked by a guardrail "
        f"({reason_list}). For `evidence_required`, ask the agent to include a citation "
        "such as `[1]` or an explicit `Source:` line."
    )


def _candidate_tool_names(data: dict[str, Any]) -> list[str]:
    """Extract candidate tool or subagent names from event or output-item data."""
    candidates: list[str] = []
    for key in ("name", "tool_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    item = data.get("item")
    if isinstance(item, dict):
        for key in ("name", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

    return candidates


def _resolve_subagent(candidate: str, subagents: list[SubagentConfig]) -> SubagentConfig | None:
    """Map a streamed tool identifier back to a configured subagent."""
    normalized = candidate.strip()
    if normalized.startswith("query_"):
        normalized = normalized[len("query_") :]
    elif normalized.startswith("Genie:"):
        normalized = normalized.split(":", 1)[1]
    elif normalized.startswith("MCP:"):
        normalized = normalized.split(":", 1)[1]

    for subagent in subagents:
        if normalized in {subagent.name, subagent.tool_name}:
            return subagent
    return None


def _used_subagents_from_payloads(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Collect the distinct configured subagents referenced in events or output items."""
    ordered: list[SubagentConfig] = []
    seen: set[str] = set()

    for payload in payloads:
        for candidate in _candidate_tool_names(payload):
            subagent = _resolve_subagent(candidate, subagents)
            if subagent is None or subagent.name in seen:
                continue
            seen.add(subagent.name)
            ordered.append(subagent)

    return ordered


def _governed_source_suffix(used_subagents: list[SubagentConfig]) -> str:
    """Build a deterministic source footer for governed tool-backed answers."""
    governed = [subagent for subagent in used_subagents if subagent.requires_evidence]
    if not governed:
        return ""

    parts: list[str] = []
    for subagent in governed:
        tool_type = "Genie MCP" if subagent.is_genie else subagent.kind.replace("_", " ")
        freshness = subagent.freshness_sla or "unknown freshness"
        parts.append(f"{subagent.name} ({tool_type}, freshness {freshness})")

    return "\n\nSource: " + "; ".join(parts)


def _event_has_tool_activity(payloads: list[dict[str, Any]]) -> bool:
    """Return true when stream/output payloads show any tool execution activity."""
    for payload in payloads:
        if _payload_has_tool_activity(payload):
                return True

    return False


def _payload_has_tool_activity(payload: dict[str, Any]) -> bool:
    """Return true when a single event/output payload indicates tool activity."""
    event_type = payload.get("type")
    if isinstance(event_type, str) and (
        event_type.startswith("response.output_item")
        or "tool" in event_type
        or "mcp" in event_type
    ):
        item = payload.get("item")
        if isinstance(item, dict):
            item_type = item.get("type")
            if isinstance(item_type, str) and ("tool" in item_type or "mcp" in item_type):
                return True
        elif "tool" in event_type or "mcp" in event_type:
            return True

    item = payload.get("item")
    if isinstance(item, dict):
        item_type = item.get("type")
        if isinstance(item_type, str) and ("tool" in item_type or "mcp" in item_type):
            return True

    return False


def _governed_source_suffix_with_fallback(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> str:
    """Build a governed source suffix with a fallback for unlabelled tool events."""
    used_subagents = _used_subagents_from_payloads(payloads, subagents)
    suffix = _governed_source_suffix(used_subagents)
    if suffix:
        return suffix

    governed = [subagent for subagent in subagents if subagent.requires_evidence]
    if governed and _event_has_tool_activity(payloads):
        return "\n\nSource: tool-backed governed response."

    return ""


def _guardrail_scope_subagents(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Limit guardrail checks to subagents that likely contributed to the answer."""
    used_subagents = _used_subagents_from_payloads(payloads, subagents)
    if used_subagents:
        return used_subagents

    if _event_has_tool_activity(payloads):
        return [subagent for subagent in subagents if subagent.requires_evidence]

    return []


def _append_source_to_output_items(
    output_items: list[dict[str, Any]],
    source_suffix: str,
) -> list[dict[str, Any]]:
    """Append a source footer to the last assistant message item."""
    if not source_suffix:
        return output_items

    updated = [dict(item) for item in output_items]
    for item in reversed(updated):
        if item.get("role") != "assistant":
            continue

        content = item.get("content")
        if isinstance(content, str):
            item["content"] = content + source_suffix
            return updated

        if isinstance(content, list):
            mutable_blocks: list[Any] = []
            appended = False
            for block in content:
                if isinstance(block, dict):
                    mutable_blocks.append(dict(block))
                else:
                    mutable_blocks.append(block)
            for block in reversed(mutable_blocks):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"] = block["text"] + source_suffix
                    appended = True
                    break
            if not appended:
                mutable_blocks.append({"type": "output_text", "text": source_suffix.strip()})
            item["content"] = mutable_blocks
            return updated

    return output_items


def _truncate_output_items(
    output_items: list[dict[str, Any]],
    *,
    max_response_chars: int,
) -> list[dict[str, Any]]:
    """Apply the response budget to the returned assistant content."""
    updated = [dict(item) for item in output_items]
    for item in reversed(updated):
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, str):
            item["content"], _ = truncate_response_text(
                content,
                max_response_chars=max_response_chars,
            )
            return updated
        if isinstance(content, list):
            for block in reversed(content):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"], _ = truncate_response_text(
                        block["text"],
                        max_response_chars=max_response_chars,
                    )
                    return updated
    return output_items


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    HANDLER_DEPS.message_bus.publish(
        "request.invoke.started",
        {
            "subagents_total": len(SUBAGENTS),
        },
    )
    prepared = _prepare_request_stage(request)

    try:
        async with AsyncExitStack() as stack:
            connected = await _connect_request_stage(stack, prepared)
            result = await _execute_invoke_stage(connected, prepared.messages)
            finalized = _finalize_invoke_stage(result, connected)
            HANDLER_DEPS.message_bus.publish(
                "request.invoke.succeeded",
                {
                    "output_items": len(result.new_items),
                    "unavailable_tools": len(finalized.unavailable),
                    "unavailable_tool_details": finalized.unavailable,
                    "response_envelope": finalized.envelope.__dict__,
                },
            )
            return ResponsesAgentResponse(output=cast(Any, finalized.output_items))
    except UserError as e:
        HANDLER_DEPS.message_bus.publish(
            "request.invoke.failed",
            {
                "error_type": type(e).__name__,
                "reason": "authorization",
            },
        )
        logger.warning("Authorization error during invoke: %s", e)
        raise
    except Exception as e:
        HANDLER_DEPS.message_bus.publish(
            "request.invoke.failed",
            {
                "error_type": type(e).__name__,
            },
        )
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during invoke: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
        raise


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    HANDLER_DEPS.message_bus.publish(
        "request.stream.started",
        {
            "subagents_total": len(SUBAGENTS),
        },
    )
    prepared = _prepare_request_stage(request)

    try:
        async with AsyncExitStack() as stack:
            connected = await _connect_request_stage(stack, prepared)
            executed = await _execute_stream_stage(connected, prepared.messages)
            finalized = _finalize_stream_stage(executed, connected)
            if finalized.guardrail_blocked:
                yield cast(
                    Any,
                    {
                        "type": "response.output_text.delta",
                        "item_id": "item_guardrail",
                        "delta": _guardrail_block_message(finalized.guardrail_reasons),
                    },
                )
                HANDLER_DEPS.message_bus.publish(
                    "request.stream.failed",
                    {
                        "error_type": "UserError",
                        "reason": "guardrail",
                    },
                )
                return

            for event in finalized.buffered_events:
                yield event
            if finalized.source_suffix:
                yield cast(
                    Any,
                    {
                        "type": "response.output_text.delta",
                        "item_id": "item_source",
                        "delta": finalized.source_suffix,
                    },
                )
            HANDLER_DEPS.message_bus.publish(
                "request.stream.succeeded",
                {
                    "events_streamed": finalized.event_count,
                    "unavailable_tools": len(finalized.unavailable),
                    "unavailable_tool_details": finalized.unavailable,
                    "response_envelope": finalized.envelope.__dict__,
                },
            )
    except UserError as e:
        HANDLER_DEPS.message_bus.publish(
            "request.stream.failed",
            {
                "error_type": type(e).__name__,
                "reason": "authorization",
            },
        )
        logger.warning("Authorization error during stream: %s", e)
        raise
    except Exception as e:
        HANDLER_DEPS.message_bus.publish(
            "request.stream.failed",
            {
                "error_type": type(e).__name__,
            },
        )
        mcp_errors = extract_mcp_errors(e)
        if mcp_errors:
            logger.warning(
                "MCP tool error during stream: %s",
                "; ".join(str(x) for x in mcp_errors),
            )
            return
        raise
