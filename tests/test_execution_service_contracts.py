"""Contract tests for the framework-neutral execution boundary."""

from datetime import UTC, datetime, timedelta

import pytest

from aiserver.contracts.execution import (
    ExecutionMessage,
    ExecutionStreamEvent,
    GovernedExecutionRequest,
    RouteAffinity,
)


def test_governed_execution_request_accepts_normalized_messages():
    request = GovernedExecutionRequest(
        messages=(ExecutionMessage(role="user", content="What changed?"),),
        conversation_id="conversation-1",
        persona="store-manager",
        metadata={"request_id": "request-1"},
    )

    assert request.messages[0].role == "user"
    assert request.metadata["request_id"] == "request-1"


def test_governed_execution_request_can_represent_rejected_delivery_input():
    request = GovernedExecutionRequest(messages=())

    assert request.messages == ()


def test_execution_stream_event_keeps_type_owned_by_contract():
    event = ExecutionStreamEvent(kind="text_delta", payload={"delta": "Hello"})

    assert event.to_payload() == {"type": "text_delta", "delta": "Hello"}

    with pytest.raises(ValueError, match="must not override"):
        ExecutionStreamEvent(kind="progress", payload={"type": "runtime_event"})


def test_route_affinity_requires_aware_expiry_and_candidates():
    affinity = RouteAffinity(
        conversation_id="conversation-1",
        candidate_names=("sales-agent",),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    assert affinity.candidate_names == ("sales-agent",)

    with pytest.raises(ValueError, match="timezone-aware"):
        RouteAffinity(
            conversation_id="conversation-1",
            candidate_names=("sales-agent",),
            expires_at=datetime.now(),
        )

    with pytest.raises(ValueError, match="candidate names"):
        RouteAffinity(
            conversation_id="conversation-1",
            candidate_names=(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
