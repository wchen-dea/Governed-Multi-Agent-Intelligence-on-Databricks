"""Pydantic HTTP request models for the backend API boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecisionInput(BaseModel):
    """Validate a manager approval decision before it reaches domain contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    store_id: str | None = None
    approver: str | None = None
    decision: Literal["approved", "rejected", "more_info_requested"] = "approved"
    reason: str | None = None
    notes: str | None = None