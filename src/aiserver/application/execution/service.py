"""Governed invoke and streaming execution use case."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any
from uuid import uuid4

from aiserver.application.auth.context import RuntimeAuthContext
from aiserver.application.exceptions import GovernedExecutionError
from aiserver.application.execution.memory import (
    hydrate_request,
    last_assistant_text,
    latest_user_question,
    persist_turns,
)
from aiserver.application.execution.response_policy import (
    APPROVAL_MESSAGE,
    append_approval_message,
    append_text_to_last_assistant,
    approval_state_for_subagents,
    candidate_tool_names,
    governed_source_suffix,
    governed_source_suffix_with_fallback,
    guardrail_block_message,
    guardrail_scope_subagents,
    payload_has_tool_activity,
    resolve_subagent,
    response_text_from_items,
    text_from_stream_event,
    truncate_output_items,
)
from aiserver.application.execution.stages import (
    ConnectedExecution,
    ExecutedStream,
    FinalizedInvoke,
    FinalizedStream,
    PreparedExecution,
)
from aiserver.application.guardrails.checks import (
    GuardrailResult,
    InputGuardrailResult,
    truncate_response_text,
)
from aiserver.application.orchestration.model import ModelSelection
from aiserver.application.ports.audit import MessageBus
from aiserver.application.ports.execution import AgentRunner
from aiserver.application.ports.memory import ConversationMemory
from aiserver.application.runtime.requests import extract_mcp_errors
from aiserver.config.settings import AppSettings
from aiserver.contracts.execution import (
    ExecutionStreamEvent,
    GovernedExecutionRequest,
    GovernedExecutionResult,
)
from aiserver.contracts.responses import OpenAIAgentRunMetadata, ResponseEnvelope, RoutePlan
from aiserver.contracts.subagents import SubagentConfig

logger = logging.getLogger(__name__)
_TRANSIENT_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.0


@dataclass(frozen=True)
class GovernedAgentServiceDependencies:
    """Injectable collaborators for governed execution."""

    settings: AppSettings
    subagents: tuple[SubagentConfig, ...]
    runtime_auth_builder: Callable[[GovernedExecutionRequest], RuntimeAuthContext]
    mcp_connector: Callable[
        [AsyncExitStack, list[Any]],
        Awaitable[tuple[list[Any], list[str]]],
    ]
    orchestrator_factory: Callable[
        [str, list[SubagentConfig], list[Any], list[Any], list[str] | None],
        Any,
    ]
    route_planner: Callable[
        [str, list[SubagentConfig], str | None],
        tuple[RoutePlan, list[SubagentConfig]],
    ]
    model_selector: Callable[[str, AppSettings], ModelSelection]
    input_guardrails_evaluator: Callable[..., InputGuardrailResult]
    response_guardrails_evaluator: Callable[[str, list[SubagentConfig]], GuardrailResult]
    message_bus: MessageBus
    memory: ConversationMemory
    runner: AgentRunner


class GovernedAgentService:
    """Coordinate request preparation, routing, execution, and governance."""

    def __init__(self, dependencies: GovernedAgentServiceDependencies) -> None:
        self._deps = dependencies

    async def invoke(self, request: GovernedExecutionRequest) -> GovernedExecutionResult:
        """Execute one governed non-streaming request."""
        self._publish("request.invoke.started", {"subagents_total": len(self._deps.subagents)})
        try:
            hydrated = hydrate_request(
                request,
                self._deps.memory,
                max_turns=self._deps.settings.memory_max_turns,
            )
            prepared = self._prepare(hydrated)
            async with AsyncExitStack() as stack:
                connected = await self._connect(stack, prepared)
                result = await self._run_with_retry(connected, prepared.request)
                finalized = self._finalize_invoke(result.output_items, connected)
                persist_turns(
                    prepared.request,
                    self._deps.memory,
                    answer=last_assistant_text(finalized.output_items),
                )
                self._publish(
                    "request.invoke.succeeded",
                    {
                        "output_items": len(finalized.output_items),
                        "unavailable_tools": len(finalized.unavailable),
                        "unavailable_tool_details": list(finalized.unavailable),
                        "response_envelope": asdict(finalized.envelope),
                    },
                )
                self._publish_run_completed(finalized.envelope)
                return GovernedExecutionResult(
                    output_items=finalized.output_items,
                    envelope=finalized.envelope,
                    unavailable_tool_details=finalized.unavailable,
                )
        except GovernedExecutionError as exc:
            self._publish(
                "request.invoke.failed",
                {
                    "error_type": type(exc).__name__,
                    "reason": user_error_failure_reason(exc),
                },
            )
            logger.warning("Governed invoke rejected: %s", exc)
            raise
        except Exception as exc:
            self._publish("request.invoke.failed", {"error_type": type(exc).__name__})
            mcp_errors = extract_mcp_errors(exc)
            if mcp_errors:
                logger.warning(
                    "MCP tool error during invoke: %s",
                    "; ".join(str(error) for error in mcp_errors),
                )
            raise

    async def stream(
        self,
        request: GovernedExecutionRequest,
    ) -> AsyncIterator[ExecutionStreamEvent]:
        """Execute one governed request and yield delivery-neutral events."""
        started_at = monotonic()
        self._publish("request.stream.started", {"subagents_total": len(self._deps.subagents)})
        yield progress_event("accepted")

        try:
            async with asyncio.timeout(self._deps.settings.stream_execution_timeout_seconds):
                hydrated = hydrate_request(
                    request,
                    self._deps.memory,
                    max_turns=self._deps.settings.memory_max_turns,
                )
                prepared = self._prepare(hydrated)
                self._publish_stream_stage("prepared", started_at)
                yield progress_event("prepared")

                async with AsyncExitStack() as stack:
                    connected = await self._connect(stack, prepared)
                    self._publish_stream_stage("connected", started_at)
                    yield progress_event("executing")
                    executed = await self._stream_with_retry(connected, prepared.request)
                    self._publish_stream_stage("executed", started_at)
                    yield progress_event("finalizing")
                    finalized = self._finalize_stream(executed, connected)

                    if finalized.guardrail_blocked:
                        yield text_delta_event(
                            "item_guardrail",
                            guardrail_block_message(finalized.guardrail_reasons),
                        )
                        self._publish_run_completed(finalized.envelope)
                        self._publish(
                            "request.stream.failed",
                            {"error_type": "UserError", "reason": "guardrail"},
                        )
                        return

                    for event in finalized.events:
                        yield ExecutionStreamEvent(kind="runtime", payload={"event": event})
                    yield ExecutionStreamEvent(
                        kind="governance",
                        payload={"response_envelope": asdict(finalized.envelope)},
                    )
                    if finalized.source_suffix:
                        yield text_delta_event("item_source", finalized.source_suffix)

                    persist_turns(
                        prepared.request,
                        self._deps.memory,
                        answer="".join(finalized.text_parts) + finalized.source_suffix,
                    )
                    self._publish(
                        "request.stream.succeeded",
                        {
                            "events_streamed": len(finalized.events),
                            "unavailable_tools": len(finalized.unavailable),
                            "unavailable_tool_details": list(finalized.unavailable),
                            "response_envelope": asdict(finalized.envelope),
                            "elapsed_ms": (monotonic() - started_at) * 1000,
                        },
                    )
                    self._publish_run_completed(finalized.envelope)
        except TimeoutError:
            self._publish(
                "request.stream.failed",
                {
                    "error_type": "TimeoutError",
                    "reason": "stream_execution_timeout",
                    "elapsed_ms": (monotonic() - started_at) * 1000,
                },
            )
            logger.warning(
                "Stream execution exceeded %.1f seconds",
                self._deps.settings.stream_execution_timeout_seconds,
            )
            yield text_delta_event(
                "item_timeout",
                "This request took too long to complete. Please retry or narrow the request.",
            )
        except asyncio.CancelledError:
            self._publish(
                "request.stream.client_disconnected",
                {"elapsed_ms": (monotonic() - started_at) * 1000},
            )
            logger.info("Client disconnected during streamed request")
            raise
        except GovernedExecutionError as exc:
            self._publish(
                "request.stream.failed",
                {
                    "error_type": type(exc).__name__,
                    "reason": user_error_failure_reason(exc),
                    "elapsed_ms": (monotonic() - started_at) * 1000,
                },
            )
            logger.warning("Governed stream rejected: %s", exc)
            raise
        except Exception as exc:
            self._publish(
                "request.stream.failed",
                {
                    "error_type": type(exc).__name__,
                    "elapsed_ms": (monotonic() - started_at) * 1000,
                },
            )
            mcp_errors = extract_mcp_errors(exc)
            if mcp_errors:
                logger.warning(
                    "MCP tool error during stream: %s",
                    "; ".join(str(error) for error in mcp_errors),
                )
                message = (
                    "I couldn't complete this request because a connected "
                    "assistant or data source was unavailable. Please try again."
                )
            else:
                logger.exception("Unhandled stream execution failure")
                message = (
                    "I couldn't complete this request because the backend "
                    "or a connected data source failed. Please try again."
                )
            yield text_delta_event("item_error", message)

    def _prepare(self, request: GovernedExecutionRequest) -> PreparedExecution:
        if not request.messages:
            raise GovernedExecutionError(
                "At least one non-empty, role-bearing execution message is required"
            )
        guardrail = self._deps.input_guardrails_evaluator(
            [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            max_input_chars=self._deps.settings.max_input_chars,
        )
        if guardrail.blocked:
            self._publish(
                "request.guardrail.blocked",
                {
                    "phase": "input",
                    "reasons": list(guardrail.reasons),
                    "character_count": guardrail.character_count,
                },
            )
            raise GovernedExecutionError(
                "Request blocked by input guardrails: " + ", ".join(guardrail.reasons)
            )
        return PreparedExecution(
            request=request,
            runtime_auth=self._deps.runtime_auth_builder(request),
        )

    async def _connect(
        self,
        stack: AsyncExitStack,
        prepared: PreparedExecution,
    ) -> ConnectedExecution:
        question = latest_user_question(prepared.request)
        route_plan, route_candidates = self._deps.route_planner(
            question,
            prepared.runtime_auth.policy_allowed_subagents,
            prepared.request.conversation_id,
        )
        candidate_names = {candidate.name for candidate in route_candidates}
        planned_servers = [
            server
            for server in prepared.runtime_auth.mcp_servers
            if str(getattr(server, "name", "")).split(":", 1)[-1] in candidate_names
        ]
        if (
            not planned_servers
            and prepared.runtime_auth.mcp_servers
            and route_plan.reason == "ambiguous_fallback"
        ):
            planned_servers = prepared.runtime_auth.mcp_servers
        servers, unavailable_health = await self._deps.mcp_connector(stack, planned_servers)
        unavailable = tuple(prepared.runtime_auth.unavailable_auth + unavailable_health)
        candidate_tools = select_route_tools(
            prepared.runtime_auth.subagent_tools,
            route_candidates,
            route_plan.reason,
        )
        model_selection = self._deps.model_selector(question, self._deps.settings)
        selected_tool_names = tuple(
            sorted(
                name
                for name in (
                    *(tool_name(tool) for tool in candidate_tools),
                    *(str(getattr(server, "name", "")).strip() for server in servers),
                )
                if name
            )
        )
        openai_run = OpenAIAgentRunMetadata(
            run_id=str(uuid4()),
            model=model_selection.model,
            model_task_type=model_selection.task_type,
            model_reason=model_selection.reason,
            model_rationale=model_selection.rationale,
            candidate_subagents=tuple(route_plan.candidates),
            selected_tool_names=selected_tool_names,
            unavailable_tool_details=unavailable,
            ai_gateway_enabled=bool(
                self._deps.settings.openai_base_url.strip()
                or self._deps.settings.openai_use_ai_gateway_native_api
                or self._deps.settings.openai_use_ai_gateway
            ),
        )
        agent = self._deps.orchestrator_factory(
            model_selection.model,
            route_candidates,
            servers,
            candidate_tools,
            list(unavailable),
        )
        self._publish(
            "routing.plan.selected",
            {
                "candidates": list(route_plan.candidates),
                "reason": route_plan.reason,
                "confidence": route_plan.confidence,
                "requires_evidence": route_plan.requires_evidence,
                "model": model_selection.model,
                "model_task_type": model_selection.task_type,
                "model_reason": model_selection.reason,
                "model_rationale": model_selection.rationale,
                "selected_tool_names": list(selected_tool_names),
                "openai_api": openai_run.api,
                "ai_gateway_enabled": openai_run.ai_gateway_enabled,
            },
        )
        self._publish("openai.agent.run.started", asdict(openai_run))
        return ConnectedExecution(
            runtime_auth=prepared.runtime_auth,
            unavailable=unavailable,
            route_plan=route_plan,
            openai_run=openai_run,
            agent=agent,
        )

    async def _run_with_retry(
        self,
        connected: ConnectedExecution,
        request: GovernedExecutionRequest,
    ):
        last_exc: BaseException | None = None
        for attempt in range(_TRANSIENT_RETRIES + 1):
            try:
                return await self._deps.runner.run(connected.agent, request.messages)
            except Exception as exc:
                if not is_transient(exc) or attempt >= _TRANSIENT_RETRIES:
                    raise
                last_exc = exc
                logger.warning(
                    "Transient error on invoke attempt %d, retrying: %s",
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise last_exc

    async def _stream_with_retry(
        self,
        connected: ConnectedExecution,
        request: GovernedExecutionRequest,
    ) -> ExecutedStream:
        last_exc: BaseException | None = None
        for attempt in range(_TRANSIENT_RETRIES + 1):
            try:
                return await self._execute_stream(connected, request)
            except Exception as exc:
                if not is_transient(exc) or attempt >= _TRANSIENT_RETRIES:
                    raise
                last_exc = exc
                logger.warning(
                    "Transient error on stream attempt %d, retrying: %s",
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise last_exc

    async def _execute_stream(
        self,
        connected: ConnectedExecution,
        request: GovernedExecutionRequest,
    ) -> ExecutedStream:
        events: list[dict[str, Any]] = []
        text_parts: list[str] = []
        used_subagents: list[SubagentConfig] = []
        seen_subagents: set[str] = set()
        has_tool_activity = False
        allowed = connected.runtime_auth.policy_allowed_subagents
        async for event in self._deps.runner.stream(connected.agent, request.messages):
            payload = dict(event.payload)
            events.append(payload)
            text = text_from_stream_event(payload)
            if text:
                text_parts.append(text)
            has_tool_activity = has_tool_activity or payload_has_tool_activity(payload)
            for candidate in candidate_tool_names(payload):
                subagent = resolve_subagent(candidate, allowed)
                if subagent is not None and subagent.name not in seen_subagents:
                    seen_subagents.add(subagent.name)
                    used_subagents.append(subagent)
        return ExecutedStream(
            events=tuple(events),
            text_parts=tuple(text_parts),
            used_subagents=tuple(used_subagents),
            has_tool_activity=has_tool_activity,
        )

    def _finalize_invoke(
        self,
        raw_output_items,
        connected: ConnectedExecution,
    ) -> FinalizedInvoke:
        output_items = [dict(item) for item in raw_output_items]
        response_text = response_text_from_items(output_items)
        guardrail_subagents = guardrail_scope_subagents(
            output_items,
            connected.runtime_auth.policy_allowed_subagents,
        )
        approval = approval_state_for_subagents(guardrail_subagents)
        source_suffix = governed_source_suffix_with_fallback(
            output_items,
            guardrail_subagents,
        )
        if source_suffix and source_suffix not in response_text:
            response_text += source_suffix
            output_items = append_text_to_last_assistant(output_items, source_suffix)
        if approval.required and approval.status == "pending" and APPROVAL_MESSAGE not in response_text:
            response_text += APPROVAL_MESSAGE
            output_items = append_approval_message(output_items, approval)
        response_text, truncated = truncate_response_text(
            response_text,
            max_response_chars=self._deps.settings.max_response_chars,
        )
        if truncated:
            output_items = truncate_output_items(
                output_items,
                max_response_chars=self._deps.settings.max_response_chars,
            )
        guardrail = self._deps.response_guardrails_evaluator(
            response_text,
            guardrail_subagents,
        )
        if "evidence_required" in guardrail.reasons and guardrail_subagents:
            fallback = (
                "\n\nSource: governed response; source metadata was unavailable "
                "in the final output item."
            )
            if fallback not in response_text:
                response_text += fallback
                output_items = append_text_to_last_assistant(output_items, fallback)
                guardrail = self._deps.response_guardrails_evaluator(
                    response_text,
                    guardrail_subagents,
                )
        envelope = ResponseEnvelope(
            status="blocked" if guardrail.blocked else ("truncated" if truncated else "succeeded"),
            answer_chars=len(response_text),
            truncated=truncated,
            route_plan=connected.route_plan,
            openai_run=connected.openai_run,
            guardrail_reasons=guardrail.reasons,
            source_metadata=(source_suffix,) if source_suffix else (),
            approval_state=approval,
        )
        self._publish_guardrail(guardrail, truncated, connected.openai_run)
        if guardrail.blocked:
            self._publish_run_completed(envelope)
            raise GovernedExecutionError(
                "Response blocked by guardrails: " + ", ".join(guardrail.reasons)
            )
        return FinalizedInvoke(
            output_items=tuple(output_items),
            unavailable=connected.unavailable,
            envelope=envelope,
        )

    def _finalize_stream(
        self,
        executed: ExecutedStream,
        connected: ConnectedExecution,
    ) -> FinalizedStream:
        if executed.used_subagents:
            guardrail_subagents = list(executed.used_subagents)
        elif executed.has_tool_activity:
            guardrail_subagents = [
                subagent
                for subagent in connected.runtime_auth.policy_allowed_subagents
                if subagent.requires_evidence
            ]
        else:
            guardrail_subagents = []
        source_suffix = governed_source_suffix(list(executed.used_subagents))
        if not source_suffix and guardrail_subagents and executed.has_tool_activity:
            source_suffix = "\n\nSource: tool-backed governed response."
        approval = approval_state_for_subagents(guardrail_subagents)
        text_parts = list(executed.text_parts)
        stream_text = "\n".join(text_parts)
        if source_suffix and source_suffix not in stream_text:
            stream_text += source_suffix
        if approval.required and approval.status == "pending" and APPROVAL_MESSAGE not in stream_text:
            stream_text += APPROVAL_MESSAGE
        stream_text, truncated = truncate_response_text(
            stream_text,
            max_response_chars=self._deps.settings.max_response_chars,
        )
        guardrail = self._deps.response_guardrails_evaluator(
            stream_text,
            guardrail_subagents,
        )
        if "evidence_required" in guardrail.reasons and guardrail_subagents:
            fallback = (
                "\n\nSource: governed response; source metadata was unavailable "
                "in the final output item."
            )
            if fallback not in stream_text:
                stream_text += fallback
                guardrail = self._deps.response_guardrails_evaluator(
                    stream_text,
                    guardrail_subagents,
                )
        self._publish_guardrail(guardrail, truncated, connected.openai_run, mode="stream")
        envelope = ResponseEnvelope(
            status="blocked" if guardrail.blocked else ("truncated" if truncated else "succeeded"),
            answer_chars=len(stream_text),
            truncated=truncated,
            route_plan=connected.route_plan,
            openai_run=connected.openai_run,
            guardrail_reasons=guardrail.reasons,
            source_metadata=(source_suffix,) if source_suffix else (),
            approval_state=approval,
        )
        return FinalizedStream(
            events=executed.events,
            text_parts=executed.text_parts,
            source_suffix=source_suffix,
            unavailable=connected.unavailable,
            guardrail_blocked=guardrail.blocked,
            guardrail_reasons=guardrail.reasons,
            envelope=envelope,
        )

    def _publish_guardrail(
        self,
        guardrail: GuardrailResult,
        truncated: bool,
        openai_run: OpenAIAgentRunMetadata,
        *,
        mode: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "reasons": list(guardrail.reasons),
            "truncated": truncated,
            "openai_run": asdict(openai_run),
        }
        if mode:
            payload["mode"] = mode
        self._publish(
            "response.guardrail.blocked" if guardrail.blocked else "response.guardrail.passed",
            payload,
        )

    def _publish_run_completed(self, envelope: ResponseEnvelope) -> None:
        self._publish(
            "openai.agent.run.completed",
            {
                **asdict(envelope.openai_run),
                "status": envelope.status,
                "guardrail_reasons": list(envelope.guardrail_reasons),
                "answer_chars": envelope.answer_chars,
            },
        )

    def _publish_stream_stage(self, stage: str, started_at: float) -> None:
        self._publish(
            "request.stream.stage.completed",
            {"stage": stage, "elapsed_ms": (monotonic() - started_at) * 1000},
        )

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self._deps.message_bus.publish(event_type, payload)


def select_route_tools(
    tools: list[Any],
    route_candidates: list[SubagentConfig],
    route_reason: str,
) -> list[Any]:
    """Select function tools without leaking them into confident MCP routes."""
    candidate_names = {candidate.name for candidate in route_candidates}
    selected = [
        tool
        for tool in tools
        if tool_name(tool).removeprefix("query_") in candidate_names
    ]
    if not selected and route_reason in {"ambiguous_fallback", "low_confidence_fallback"}:
        return tools
    return selected


def tool_name(tool: Any) -> str:
    """Return a stable runtime tool name."""
    return str(getattr(tool, "name", getattr(tool, "__name__", ""))).strip()


def progress_event(stage: str) -> ExecutionStreamEvent:
    """Build a non-content execution progress event."""
    return ExecutionStreamEvent(kind="progress", payload={"stage": stage})


def text_delta_event(item_id: str, delta: str) -> ExecutionStreamEvent:
    """Build an application-owned text delta event."""
    return ExecutionStreamEvent(
        kind="text_delta",
        payload={"item_id": item_id, "delta": delta},
    )


def user_error_failure_reason(exc: GovernedExecutionError) -> str:
    """Classify a governed user-facing failure."""
    return "guardrail" if "guardrail" in str(exc).lower() else "authorization"


def is_transient(exc: BaseException) -> bool:
    """Return whether an execution failure is safe to retry."""
    name = type(exc).__name__
    return "APIConnectionError" in name or "ConnectionError" in name
