"""Versioned contracts for the application-facing API.

These models intentionally contain no MLflow or Agent Server types.  The API
adapter will translate them to the runtime-specific invocation contracts.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicMessage(BaseModel):
    """One message in a public chat transcript."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """Request accepted by the application-facing chat endpoint."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    messages: list[PublicMessage] = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    persona: str | None = None
    stream: bool = True


class ApprovalDecisionRequest(BaseModel):
    """Manager decision submitted through the public API."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    store_id: str | None = None
    approver: str | None = None
    decision: Literal["approved", "rejected", "more_info_requested"]
    reason: str | None = None
    notes: str | None = None


class ApprovalResponse(BaseModel):
    """Public representation of a persisted approval decision."""

    request_id: str
    agent_name: str
    store_id: str | None = None
    approver: str | None = None
    decision: str
    reason: str | None = None
    notes: str | None = None
    status: str


class DelegationResponse(BaseModel):
    """Payload-redacted delegation lifecycle state."""

    task_id: str
    correlation_id: str | None = None
    source_agent: str
    target_agent: str
    intent: str
    status: str
    attempt: int | None = None
    max_attempts: int | None = None
    failure_code: str | None = None
    completed: bool = False


class ApprovalDecisionResponse(BaseModel):
    """Result returned after recording an approval decision."""

    status: Literal["ok"] = "ok"
    approval: ApprovalResponse
    delegation: DelegationResponse | None = None


class ChatTextDeltaEvent(BaseModel):
    """Incremental user-visible text event."""

    type: Literal["text_delta"] = "text_delta"
    delta: str


class ChatMetadataEvent(BaseModel):
    """Governance metadata emitted during or after a chat stream."""

    type: Literal["metadata"] = "metadata"
    metadata: dict[str, Any]


class ChatCompletedEvent(BaseModel):
    """Successful end-of-stream event."""

    type: Literal["completed"] = "completed"


class PublicError(BaseModel):
    """User-safe API error payload."""

    code: str
    message: str
    request_id: str | None = None


class ChatErrorEvent(BaseModel):
    """Terminal stream error event."""

    type: Literal["error"] = "error"
    error: PublicError