"""Tests for user-safe delegation status responses."""

from backend.api.server import _delegation_status_payload
from backend.domain.agent_messages import DelegationTask, DelegationTaskRecord


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