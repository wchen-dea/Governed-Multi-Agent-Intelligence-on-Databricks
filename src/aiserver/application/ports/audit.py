"""Define lifecycle audit and tracing application ports."""

from typing import Any, Protocol

from aiserver.contracts.responses import ApprovalDecisionRecord


class TraceMetadataUpdater(Protocol):
    """Persist authorization metadata on the active trace."""

    def __call__(self, metadata: dict[str, str]) -> Any: ...


class MessageBus(Protocol):
    """Publish typed lifecycle events for request-scoped execution."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None: ...


class ApprovalRepository(Protocol):
    """Persist and retrieve manager approval decisions."""

    def save(self, record: ApprovalDecisionRecord) -> ApprovalDecisionRecord: ...

    def get(self, request_id: str) -> ApprovalDecisionRecord | None: ...


class NoOpMessageBus:
    """Discard lifecycle events until bootstrap provides a concrete adapter."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        del event_type, payload


def noop_trace_metadata(metadata: dict[str, str]) -> None:
    """Discard trace metadata until bootstrap provides a concrete adapter."""
    del metadata