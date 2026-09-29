"""Framework-neutral contracts for governed agent execution."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from aiserver.contracts.responses import ResponseEnvelope

ExecutionRole = Literal["user", "assistant", "system", "developer", "tool"]
ExecutionStreamEventKind = Literal[
    "progress",
    "text_delta",
    "output_item",
    "runtime",
    "governance",
    "error",
    "completed",
]


@dataclass(frozen=True)
class ExecutionMessage:
    """Represent one normalized message consumed by the application core."""

    role: ExecutionRole
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Execution message content is required")


@dataclass(frozen=True)
class GovernedExecutionRequest:
    """Represent a runtime-independent governed agent request."""

    messages: tuple[ExecutionMessage, ...]
    conversation_id: str | None = None
    persona: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.conversation_id is not None and not self.conversation_id.strip():
            raise ValueError("Conversation ID cannot be blank")
        if self.persona is not None and not self.persona.strip():
            raise ValueError("Persona cannot be blank")


@dataclass(frozen=True)
class RunnerExecutionResult:
    """Normalize an agent SDK result before response governance is applied."""

    output_items: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class RunnerStreamEvent:
    """Normalize one agent SDK stream event for application processing."""

    payload: Mapping[str, Any]


@dataclass(frozen=True)
class GovernedExecutionResult:
    """Return governed output without exposing a delivery-framework response type."""

    output_items: tuple[Mapping[str, Any], ...]
    envelope: ResponseEnvelope
    unavailable_tool_details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionStreamEvent:
    """Represent one delivery-neutral event from governed streaming execution."""

    kind: ExecutionStreamEventKind
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "type" in self.payload:
            raise ValueError("Execution stream payload must not override the event type")

    def to_payload(self) -> dict[str, Any]:
        """Return a serializable event payload for delivery adapters."""
        return {"type": self.kind, **self.payload}


@dataclass(frozen=True)
class RouteAffinity:
    """Persist a conversation's last confident route across app instances."""

    conversation_id: str
    candidate_names: tuple[str, ...]
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.conversation_id.strip():
            raise ValueError("Route affinity conversation ID is required")
        if not self.candidate_names or any(not name.strip() for name in self.candidate_names):
            raise ValueError("Route affinity requires non-empty candidate names")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("Route affinity expiry must be timezone-aware")
