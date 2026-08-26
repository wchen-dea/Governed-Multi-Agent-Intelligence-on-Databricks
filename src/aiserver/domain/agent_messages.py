"""Typed contracts for bounded agent-to-agent delegation."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

DelegationTaskStatus = Literal[
    "pending",
    "claimed",
    "running",
    "succeeded",
    "failed",
    "rejected",
    "expired",
    "dead_letter",
]
DelegationResultStatus = Literal["succeeded", "failed", "rejected", "expired"]


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for delegation state transitions."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class DelegationTask:
    """Represent one bounded request from a source agent to a target agent."""

    source_agent: str
    target_agent: str
    intent: str
    payload: dict[str, Any]
    correlation_id: str
    idempotency_key: str
    conversation_id: str | None = None
    parent_task_id: str | None = None
    ancestry: tuple[str, ...] = ()
    data_classification: str = "internal"
    auth_mode: Literal["app", "obo"] = "app"
    task_id: str = field(default_factory=lambda: str(uuid4()))
    attempt: int = 0
    max_attempts: int = 2
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.source_agent or not self.target_agent or not self.intent:
            raise ValueError("Delegation task source, target, and intent are required")
        if self.auth_mode != "app":
            raise ValueError("Asynchronous agent delegation supports app auth only")
        if self.max_attempts < 1:
            raise ValueError("Delegation task max_attempts must be at least 1")
        if self.source_agent == self.target_agent or self.target_agent in self.ancestry:
            raise ValueError("Delegation task contains an agent loop")
        if self.expires_at and self.expires_at <= self.created_at:
            raise ValueError("Delegation task expiry must be after creation")


@dataclass(frozen=True)
class DelegationResult:
    """Represent normalized terminal output for a delegated task."""

    task_id: str
    correlation_id: str
    status: DelegationResultStatus
    output: dict[str, Any] | None = None
    error_code: str | None = None
    completed_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class DelegationTaskRecord:
    """Persist task state, lease, and terminal result for a delegation."""

    task: DelegationTask
    status: DelegationTaskStatus = "pending"
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    result: DelegationResult | None = None
    failure_code: str | None = None
