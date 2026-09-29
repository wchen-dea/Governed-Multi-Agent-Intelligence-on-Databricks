"""Typed state passed between governed execution pipeline stages."""

from dataclasses import dataclass
from typing import Any

from aiserver.application.auth.context import RuntimeAuthContext
from aiserver.contracts.execution import GovernedExecutionRequest
from aiserver.contracts.responses import OpenAIAgentRunMetadata, ResponseEnvelope, RoutePlan
from aiserver.contracts.subagents import SubagentConfig


@dataclass(frozen=True)
class PreparedExecution:
    """Prepared request with request-scoped authorization and memory."""

    request: GovernedExecutionRequest
    runtime_auth: RuntimeAuthContext


@dataclass(frozen=True)
class ConnectedExecution:
    """Connected tools, routing metadata, and assembled agent."""

    runtime_auth: RuntimeAuthContext
    unavailable: tuple[str, ...]
    route_plan: RoutePlan
    openai_run: OpenAIAgentRunMetadata
    agent: Any


@dataclass(frozen=True)
class FinalizedInvoke:
    """Governed invoke output ready for a delivery adapter."""

    output_items: tuple[dict[str, Any], ...]
    unavailable: tuple[str, ...]
    envelope: ResponseEnvelope


@dataclass(frozen=True)
class ExecutedStream:
    """Buffered runner stream plus derived governance inputs."""

    events: tuple[dict[str, Any], ...]
    text_parts: tuple[str, ...]
    used_subagents: tuple[SubagentConfig, ...]
    has_tool_activity: bool


@dataclass(frozen=True)
class FinalizedStream:
    """Governed stream state ready for ordered delivery."""

    events: tuple[dict[str, Any], ...]
    text_parts: tuple[str, ...]
    source_suffix: str
    unavailable: tuple[str, ...]
    guardrail_blocked: bool
    guardrail_reasons: tuple[str, ...]
    envelope: ResponseEnvelope
