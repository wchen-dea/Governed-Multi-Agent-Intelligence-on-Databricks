"""Validation tests for the versioned application-facing API contracts."""

import pytest
from pydantic import ValidationError

from aiserver.contracts.public_api import (
    ApprovalDecisionRequest,
    ChatRequest,
    ChatTextDeltaEvent,
)


def test_chat_request_accepts_public_transcript():
    request = ChatRequest(
        messages=[{"role": "user", "content": "What changed?"}],
        conversation_id="conversation-1",
        persona="store-manager",
    )

    assert request.messages[0].content == "What changed?"
    assert request.stream is True


def test_chat_request_rejects_runtime_specific_fields():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "Hello"}],
            conversation_id="conversation-1",
            input=[],
        )


def test_approval_request_rejects_unknown_decision():
    with pytest.raises(ValidationError):
        ApprovalDecisionRequest(
            request_id="request-1",
            agent_name="store-intervention-agent",
            decision="dispatch",
        )


def test_stream_event_has_stable_public_type():
    event = ChatTextDeltaEvent(delta="Hello")

    assert event.model_dump() == {"type": "text_delta", "delta": "Hello"}