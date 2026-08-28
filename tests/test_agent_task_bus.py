"""Tests for Unity Catalog-backed delegation task storage."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

from aiserver.config.settings import AppSettings
from aiserver.contracts.delegation import DelegationTask, utc_now
from aiserver.infrastructure.persistence.tasks import (
    InMemoryAgentTaskBus,
    UcAgentTaskBus,
    _record_from_row,
    default_agent_task_bus,
)


class FakeStatementExecution:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute_statement(self, *, statement: str, **kwargs):
        del kwargs
        self.statements.append(statement)
        return SimpleNamespace(
            result=SimpleNamespace(data_array=[]),
            manifest=SimpleNamespace(schema=SimpleNamespace(columns=[])),
        )


def _task() -> DelegationTask:
    return DelegationTask(
        source_agent="orchestrator",
        target_agent="lakebase_ods_agent",
        intent="appointment_summary",
        payload={"sql_query": "SELECT 1"},
        correlation_id="corr-1",
        idempotency_key="key-1",
        expires_at=utc_now() + timedelta(minutes=10),
    )


def test_uc_agent_task_bus_creates_tables_and_submits_task():
    statement_execution = FakeStatementExecution()
    workspace_client = SimpleNamespace(statement_execution=statement_execution)
    bus = UcAgentTaskBus(
        warehouse_id="warehouse-1",
        catalog="main",
        schema="agent_ops",
        workspace_client=workspace_client,
    )

    record = asyncio.run(bus.submit(_task()))

    assert record.status == "pending"
    assert any(
        "CREATE TABLE IF NOT EXISTS main.agent_ops.agent_delegation_tasks" in statement
        for statement in statement_execution.statements
    )
    assert any(
        "INSERT INTO main.agent_ops.agent_delegation_tasks" in statement
        for statement in statement_execution.statements
    )
    assert any(
        "delegation.task.created" in statement for statement in statement_execution.statements
    )


def test_default_agent_task_bus_uses_memory_by_default_and_validates_uc_config():
    assert isinstance(default_agent_task_bus(AppSettings()), InMemoryAgentTaskBus)
    try:
        default_agent_task_bus(AppSettings(agent_task_backend="uc_table"))
    except ValueError as exc:
        assert "AGENT_TASK_WAREHOUSE_ID" in str(exc)
    else:
        raise AssertionError("Expected UC task store configuration failure")


def test_record_decoder_restores_task_state_from_uc_payload():
    task = _task()
    row = {
        "task_payload": __import__("json").dumps(
            {
                "task_id": task.task_id,
                "source_agent": task.source_agent,
                "target_agent": task.target_agent,
                "intent": task.intent,
                "payload": task.payload,
                "correlation_id": task.correlation_id,
                "idempotency_key": task.idempotency_key,
                "conversation_id": None,
                "parent_task_id": None,
                "ancestry": [],
                "data_classification": task.data_classification,
                "auth_mode": task.auth_mode,
                "attempt": 1,
                "max_attempts": task.max_attempts,
                "expires_at": task.expires_at.isoformat() if task.expires_at else None,
                "created_at": task.created_at.isoformat(),
            }
        ),
        "status": "running",
        "lease_owner": "worker-1",
        "lease_expires_at": None,
        "result_payload": None,
        "failure_code": None,
    }

    record = _record_from_row(row)

    assert record.status == "running"
    assert record.task.attempt == 1
    assert record.lease_owner == "worker-1"
