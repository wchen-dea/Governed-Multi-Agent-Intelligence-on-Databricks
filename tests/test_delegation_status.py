"""Tests for user-safe delegation status responses."""

from aiserver.api.server import _delegation_status_payload
from aiserver.bootstrap.web_lifecycle import WebProcessLifecycle
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


def test_worker_lifecycle_closes_closeable_adapter():
    class CloseableBus:
        closed = False

        def close(self):
            self.closed = True

    message_bus = CloseableBus()
    container = type("Container", (), {"message_bus": message_bus})()
    lifecycle = WebProcessLifecycle(container)

    lifecycle.close()

    assert message_bus.closed is True
