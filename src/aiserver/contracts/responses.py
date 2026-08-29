"""Typed contracts shared by routing, execution, and response policy layers."""

from dataclasses import dataclass, field
from typing import Literal

ExecutionStatus = Literal["succeeded", "failed", "blocked", "truncated"]
ApprovalStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
    "more_info_requested",
    "expired",
]


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
class OpenAIAgentRunMetadata:
    """Describe one OpenAI-compatible agent run for audit and evaluation."""

    run_id: str = ""
    api: str = "responses"
    model: str = ""
    model_task_type: str = ""
    model_reason: str = ""
    model_rationale: str = ""
    candidate_subagents: tuple[str, ...] = ()
    selected_tool_names: tuple[str, ...] = ()
    unavailable_tool_details: tuple[str, ...] = ()
    ai_gateway_enabled: bool = False


@dataclass(frozen=True)
class HumanApprovalState:
    """Describe the review gate for business-impacting or action-oriented responses."""

    status: ApprovalStatus = "not_required"
    required: bool = False
    approver: str | None = None
    decision: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ApprovalDecisionRequest:
    """Explicit manager decision for a pending approval state."""

    request_id: str
    agent_name: str
    store_id: str | None = None
    approver: str | None = None
    decision: Literal["approved", "rejected", "more_info_requested"] = "approved"
    reason: str | None = None
    notes: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        """Convert the request to a serializable payload for API transport."""
        return {
            "request_id": self.request_id,
            "agent_name": self.agent_name,
            "store_id": self.store_id,
            "approver": self.approver,
            "decision": self.decision,
            "reason": self.reason,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ApprovalDecisionRecord:
    """Persisted approval decision record emitted after a manager review."""

    request_id: str
    agent_name: str
    store_id: str | None = None
    approver: str | None = None
    decision: Literal["approved", "rejected", "more_info_requested"] = "approved"
    reason: str | None = None
    notes: str | None = None
    status: ApprovalStatus = "pending"

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "ApprovalDecisionRecord":
        """Rehydrate a decision record from a request or persisted payload."""
        decision = payload.get("decision")
        if decision not in {"approved", "rejected", "more_info_requested"}:
            raise ValueError(f"Unsupported approval decision: {decision!r}")
        return cls(
            request_id=str(payload.get("request_id", "")),
            agent_name=str(payload.get("agent_name", "")),
            store_id=payload.get("store_id"),
            approver=payload.get("approver"),
            decision=decision,
            reason=payload.get("reason"),
            notes=payload.get("notes"),
            status=str(payload.get("status", "approved")),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class ResponseEnvelope:
    """Represent governed response metadata without changing the public payload."""

    status: ExecutionStatus
    answer_chars: int
    truncated: bool = False
    route_plan: RoutePlan = field(default_factory=RoutePlan)
    tool_results: tuple[ToolExecutionResult, ...] = ()
    openai_run: OpenAIAgentRunMetadata = field(default_factory=OpenAIAgentRunMetadata)
    guardrail_reasons: tuple[str, ...] = ()
    source_metadata: tuple[str, ...] = ()
    approval_state: HumanApprovalState = field(default_factory=HumanApprovalState)
