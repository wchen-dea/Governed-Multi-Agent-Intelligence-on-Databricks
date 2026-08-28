"""Tests for user-safe delegation status responses."""

from types import SimpleNamespace

from aiserver.api import server
from aiserver.api.server import _delegation_status_payload
from aiserver.contracts.delegation import DelegationTask, DelegationTaskRecord


def test_delegation_status_does_not_expose_task_sql_payload():
    task = DelegationTask(
        source_agent="orchestrator",
        target_agent="lakebase_ods_agent",
        intent="appointment_summary",
        payload={"sql_query": "SELECT confidential_column FROM appointment"},
        correlation_id="corr-1",
        idempotency_key="task-1",
    )

    payload = _delegation_status_payload(DelegationTaskRecord(task=task, status="pending"))

    assert payload["status"] == "pending"
    assert "sql_query" not in payload
    assert "payload" not in payload


def test_close_message_bus_closes_closeable_adapter(monkeypatch):
    class CloseableBus:
        closed = False

        def close(self):
            self.closed = True

    message_bus = CloseableBus()
    container = SimpleNamespace(handlers=SimpleNamespace(message_bus=message_bus))
    monkeypatch.setattr(server, "get_app_dependency_container", lambda: container)

    server._close_message_bus()

    assert message_bus.closed is True
