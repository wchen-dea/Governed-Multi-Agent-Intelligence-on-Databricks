"""Typed contracts shared by routing, execution, and response policy layers."""

from dataclasses import dataclass, field
from typing import Literal


ExecutionStatus = Literal["succeeded", "failed", "blocked", "truncated"]


@dataclass(frozen=True)
class RoutePlan:
    """Describe the deterministic routing decision made before execution."""

    candidates: tuple[str, ...] = ()
    reason: str = "model_selected"
    confidence: float = 0.0
    requires_evidence: bool = False


@dataclass(frozen=True)
class ToolExecutionResult:
    """Normalize one tool invocation outcome for traces and lifecycle events."""

    tool_name: str
    status: ExecutionStatus
    latency_ms: float = 0.0
    attempt_count: int = 1
    auth_mode: str = "unknown"
    error_code: str | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResponseEnvelope:
    """Represent governed response metadata without changing the public payload."""

    status: ExecutionStatus
    answer_chars: int
    truncated: bool = False
    route_plan: RoutePlan = field(default_factory=RoutePlan)
    tool_results: tuple[ToolExecutionResult, ...] = ()
    guardrail_reasons: tuple[str, ...] = ()
    source_metadata: tuple[str, ...] = ()
