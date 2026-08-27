"""Durable-task-bus abstraction and in-memory implementation for delegations."""

import asyncio
import json
import re
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from databricks.sdk import WorkspaceClient

from aiserver.domain.agent_messages import (
    DelegationResult,
    DelegationTask,
    DelegationTaskRecord,
    utc_now,
)
from aiserver.shared.settings import AppSettings


class InMemoryAgentTaskBus:
    """Concurrency-safe task bus used by tests and local development.

    The interface mirrors a durable queue: submissions are idempotent, claims
    are leased, and failed work reaches a terminal dead-letter state.
    """

    def __init__(self) -> None:
        self._records: dict[str, DelegationTaskRecord] = {}
        self._task_id_by_idempotency_key: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def submit(self, task: DelegationTask) -> DelegationTaskRecord:
        """Store a pending task or return the existing idempotent submission."""
        async with self._lock:
            existing_id = self._task_id_by_idempotency_key.get(task.idempotency_key)
            if existing_id:
                return self._records[existing_id]
            record = DelegationTaskRecord(task=task)
            self._records[task.task_id] = record
            self._task_id_by_idempotency_key[task.idempotency_key] = task.task_id
            return record

    async def claim(
        self,
        worker_id: str,
        *,
        limit: int = 1,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> list[DelegationTaskRecord]:
        """Lease eligible tasks to a worker, recovering expired leases first."""
        current = now or utc_now()
        lease_expires_at = current + timedelta(seconds=max(lease_seconds, 1))
        claimed: list[DelegationTaskRecord] = []
        async with self._lock:
            for task_id, record in list(self._records.items()):
                if len(claimed) >= max(limit, 1):
                    break
                if record.task.expires_at and record.task.expires_at <= current:
                    self._records[task_id] = replace(
                        record, status="expired", failure_code="task_expired"
                    )
                    continue
                lease_expired = (
                    record.status in {"claimed", "running"}
                    and record.lease_expires_at is not None
                    and record.lease_expires_at <= current
                )
                eligible = record.status == "pending" or lease_expired
                if not eligible:
                    continue
                task = replace(record.task, attempt=record.task.attempt + 1)
                updated = DelegationTaskRecord(
                    task=task,
                    status="claimed",
                    lease_owner=worker_id,
                    lease_expires_at=lease_expires_at,
                )
                self._records[task_id] = updated
                claimed.append(updated)
        return claimed

    async def mark_running(self, task_id: str, worker_id: str) -> DelegationTaskRecord:
        """Mark a worker-owned lease as actively executing."""
        async with self._lock:
            record = self._require_owned(task_id, worker_id)
            updated = replace(record, status="running")
            self._records[task_id] = updated
            return updated

    async def complete(self, result: DelegationResult, worker_id: str) -> DelegationTaskRecord:
        """Persist a successful or terminal delegated result."""
        async with self._lock:
            record = self._require_owned(result.task_id, worker_id)
            status = "succeeded" if result.status == "succeeded" else result.status
            updated = replace(
                record, status=status, result=result, lease_owner=None, lease_expires_at=None
            )
            self._records[result.task_id] = updated
            return updated

    async def fail(self, task_id: str, worker_id: str, error_code: str) -> DelegationTaskRecord:
        """Retry an owned task until its attempt budget is exhausted."""
        async with self._lock:
            record = self._require_owned(task_id, worker_id)
            if record.task.attempt >= record.task.max_attempts:
                updated = replace(
                    record,
                    status="dead_letter",
                    lease_owner=None,
                    lease_expires_at=None,
                    failure_code=error_code,
                )
            else:
                updated = replace(
                    record,
                    status="pending",
                    lease_owner=None,
                    lease_expires_at=None,
                    failure_code=error_code,
                )
            self._records[task_id] = updated
            return updated

    async def get(self, task_id: str) -> DelegationTaskRecord | None:
        """Return a task record for status polling or tests."""
        async with self._lock:
            return self._records.get(task_id)

    def _require_owned(self, task_id: str, worker_id: str) -> DelegationTaskRecord:
        record = self._records[task_id]
        if record.lease_owner != worker_id or record.status not in {"claimed", "running"}:
            raise RuntimeError(f"Worker {worker_id!r} does not own task {task_id!r}")
        return record


class UcAgentTaskBus:
    """Persist delegation tasks and transitions in Unity Catalog Delta tables.

    This backend is intentionally fail-closed: delegation work must never be
    silently dropped when durable coordination is selected.
    """

    def __init__(
        self,
        *,
        warehouse_id: str,
        catalog: str,
        schema: str,
        task_table: str = "agent_delegation_tasks",
        event_table: str = "agent_delegation_events",
        workspace_client: WorkspaceClient | None = None,
    ) -> None:
        if not warehouse_id.strip():
            raise ValueError("AGENT_TASK_WAREHOUSE_ID must be set for uc_table task backend")
        self._warehouse_id = warehouse_id
        self._catalog = _identifier(catalog, "AGENT_TASK_CATALOG")
        self._schema = _identifier(schema, "AGENT_TASK_SCHEMA")
        self._task_table = _identifier(task_table, "AGENT_TASK_TABLE")
        self._event_table = _identifier(event_table, "AGENT_TASK_EVENT_TABLE")
        self._workspace_client = workspace_client or WorkspaceClient()
        self._ensure_tables()

    @property
    def _tasks_fqn(self) -> str:
        return f"{self._catalog}.{self._schema}.{self._task_table}"

    @property
    def _events_fqn(self) -> str:
        return f"{self._catalog}.{self._schema}.{self._event_table}"

    async def submit(self, task: DelegationTask) -> DelegationTaskRecord:
        """Insert a task unless its idempotency key already exists."""
        existing = await self._find_by_idempotency_key(task.idempotency_key)
        if existing is not None:
            return existing
        now = utc_now()
        task_json = json.dumps(_task_to_dict(task), sort_keys=True, default=str)
        await self._execute(
            "INSERT INTO "
            f"{self._tasks_fqn} (task_id, idempotency_key, status, task_payload, created_at, updated_at) VALUES "
            f"({_literal(task.task_id)}, {_literal(task.idempotency_key)}, 'pending', {_literal(task_json)}, "
            f"TIMESTAMP {_literal(now.isoformat())}, TIMESTAMP {_literal(now.isoformat())})"
        )
        await self._event(
            task.task_id, "delegation.task.created", {"correlation_id": task.correlation_id}
        )
        return DelegationTaskRecord(task=task)

    async def claim(
        self,
        worker_id: str,
        *,
        limit: int = 1,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> list[DelegationTaskRecord]:
        """Lease pending or abandoned tasks to a worker.

        Delta updates are conditioned on the prior state. If another worker
        wins the race, the following read verifies ownership and drops it.
        """
        current = now or utc_now()
        lease_until = current + timedelta(seconds=max(lease_seconds, 1))
        candidates = await self._query(
            "SELECT task_id FROM "
            f"{self._tasks_fqn} WHERE status = 'pending' OR "
            f"(status IN ('claimed', 'running') AND lease_expires_at <= TIMESTAMP {_literal(current.isoformat())}) "
            f"ORDER BY created_at LIMIT {max(limit, 1)}"
        )
        claimed: list[DelegationTaskRecord] = []
        for row in candidates:
            task_id = str(row["task_id"])
            await self._execute(
                f"UPDATE {self._tasks_fqn} SET status = 'claimed', lease_owner = {_literal(worker_id)}, "
                f"lease_expires_at = TIMESTAMP {_literal(lease_until.isoformat())}, "
                f"updated_at = TIMESTAMP {_literal(current.isoformat())} "
                f"WHERE task_id = {_literal(task_id)} AND (status = 'pending' OR "
                f"(status IN ('claimed', 'running') AND lease_expires_at <= TIMESTAMP {_literal(current.isoformat())}))"
            )
            record = await self.get(task_id)
            if record and record.lease_owner == worker_id and record.status == "claimed":
                task = replace(record.task, attempt=record.task.attempt + 1)
                await self._execute(
                    f"UPDATE {self._tasks_fqn} SET task_payload = {_literal(json.dumps(_task_to_dict(task), default=str))} "
                    f"WHERE task_id = {_literal(task_id)} AND lease_owner = {_literal(worker_id)}"
                )
                claimed_record = replace(record, task=task, lease_expires_at=lease_until)
                claimed.append(claimed_record)
                await self._event(task_id, "delegation.task.claimed", {"worker_id": worker_id})
        return claimed

    async def mark_running(self, task_id: str, worker_id: str) -> DelegationTaskRecord:
        """Transition an owned claim into execution."""
        await self._execute(
            f"UPDATE {self._tasks_fqn} SET status = 'running', updated_at = current_timestamp() "
            f"WHERE task_id = {_literal(task_id)} AND lease_owner = {_literal(worker_id)} AND status = 'claimed'"
        )
        record = await self._owned_record(task_id, worker_id)
        if record.status != "running":
            raise RuntimeError(f"Worker {worker_id!r} could not start task {task_id!r}")
        return record

    async def complete(self, result: DelegationResult, worker_id: str) -> DelegationTaskRecord:
        """Persist a terminal result for an owned task."""
        status = "succeeded" if result.status == "succeeded" else result.status
        await self._execute(
            f"UPDATE {self._tasks_fqn} SET status = {_literal(status)}, result_payload = "
            f"{_literal(json.dumps(_result_to_dict(result), default=str))}, lease_owner = NULL, "
            f"lease_expires_at = NULL, updated_at = current_timestamp() WHERE task_id = {_literal(result.task_id)} "
            f"AND lease_owner = {_literal(worker_id)} AND status IN ('claimed', 'running')"
        )
        record = await self.get(result.task_id)
        if record is None or record.status != status:
            raise RuntimeError(f"Worker {worker_id!r} could not complete task {result.task_id!r}")
        await self._event(result.task_id, "delegation.task.completed", {"status": status})
        return record

    async def fail(self, task_id: str, worker_id: str, error_code: str) -> DelegationTaskRecord:
        """Return work to pending or dead-letter it after its attempt budget."""
        record = await self._owned_record(task_id, worker_id)
        status = "dead_letter" if record.task.attempt >= record.task.max_attempts else "pending"
        await self._execute(
            f"UPDATE {self._tasks_fqn} SET status = {_literal(status)}, failure_code = {_literal(error_code)}, "
            "lease_owner = NULL, lease_expires_at = NULL, updated_at = current_timestamp() "
            f"WHERE task_id = {_literal(task_id)} AND lease_owner = {_literal(worker_id)}"
        )
        updated = await self.get(task_id)
        if updated is None:
            raise RuntimeError(f"Delegation task {task_id!r} was not found")
        await self._event(task_id, f"delegation.task.{status}", {"error_code": error_code})
        return updated

    async def get(self, task_id: str) -> DelegationTaskRecord | None:
        """Load one task record for worker settlement or status polling."""
        rows = await self._query(
            "SELECT task_payload, status, lease_owner, lease_expires_at, result_payload, failure_code "
            f"FROM {self._tasks_fqn} WHERE task_id = {_literal(task_id)}"
        )
        return _record_from_row(rows[0]) if rows else None

    async def _find_by_idempotency_key(self, key: str) -> DelegationTaskRecord | None:
        rows = await self._query(
            "SELECT task_payload, status, lease_owner, lease_expires_at, result_payload, failure_code "
            f"FROM {self._tasks_fqn} WHERE idempotency_key = {_literal(key)}"
        )
        return _record_from_row(rows[0]) if rows else None

    async def _owned_record(self, task_id: str, worker_id: str) -> DelegationTaskRecord:
        record = await self.get(task_id)
        if (
            record is None
            or record.lease_owner != worker_id
            or record.status not in {"claimed", "running"}
        ):
            raise RuntimeError(f"Worker {worker_id!r} does not own task {task_id!r}")
        return record

    def _ensure_tables(self) -> None:
        self._execute_sync(f"CREATE SCHEMA IF NOT EXISTS {self._catalog}.{self._schema}")
        self._execute_sync(
            f"CREATE TABLE IF NOT EXISTS {self._tasks_fqn} (task_id STRING, idempotency_key STRING, "
            "status STRING, task_payload STRING, result_payload STRING, failure_code STRING, "
            "lease_owner STRING, lease_expires_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP) USING DELTA"
        )
        self._execute_sync(
            f"CREATE TABLE IF NOT EXISTS {self._events_fqn} (task_id STRING, event_type STRING, "
            "event_ts TIMESTAMP, event_payload STRING) USING DELTA"
        )

    async def _execute(self, statement: str) -> Any:
        return await asyncio.to_thread(self._execute_sync, statement)

    def _execute_sync(self, statement: str) -> Any:
        return self._workspace_client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self._warehouse_id,
            wait_timeout="50s",
            catalog=self._catalog,
            schema=self._schema,
        )

    async def _query(self, statement: str) -> list[dict[str, Any]]:
        response = await self._execute(statement)
        return _statement_rows(response)

    async def _event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        await self._execute(
            f"INSERT INTO {self._events_fqn} (task_id, event_type, event_ts, event_payload) VALUES "
            f"({_literal(task_id)}, {_literal(event_type)}, current_timestamp(), {_literal(json.dumps(payload, default=str))})"
        )


def _identifier(value: str, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"{name} has invalid identifier: {value!r}")
    return value


def _literal(value: str) -> str:
    """Return a SQL string literal after escaping its only special delimiter."""
    return "'" + value.replace("'", "''") + "'"


def _task_to_dict(task: DelegationTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "source_agent": task.source_agent,
        "target_agent": task.target_agent,
        "intent": task.intent,
        "payload": task.payload,
        "correlation_id": task.correlation_id,
        "idempotency_key": task.idempotency_key,
        "conversation_id": task.conversation_id,
        "parent_task_id": task.parent_task_id,
        "ancestry": list(task.ancestry),
        "data_classification": task.data_classification,
        "auth_mode": task.auth_mode,
        "attempt": task.attempt,
        "max_attempts": task.max_attempts,
        "expires_at": task.expires_at.isoformat() if task.expires_at else None,
        "created_at": task.created_at.isoformat(),
    }


def _result_to_dict(result: DelegationResult) -> dict[str, Any]:
    return {
        "task_id": result.task_id,
        "correlation_id": result.correlation_id,
        "status": result.status,
        "output": result.output,
        "error_code": result.error_code,
        "completed_at": result.completed_at.isoformat(),
    }


def _record_from_row(row: dict[str, Any]) -> DelegationTaskRecord:
    task_data = json.loads(row["task_payload"])
    expires_at = task_data.get("expires_at")
    task = DelegationTask(
        **{
            **task_data,
            "ancestry": tuple(task_data.get("ancestry", [])),
            "expires_at": datetime.fromisoformat(expires_at) if expires_at else None,
            "created_at": datetime.fromisoformat(task_data["created_at"]),
        }
    )
    result_data = json.loads(row["result_payload"]) if row.get("result_payload") else None
    result = (
        DelegationResult(
            **{
                **result_data,
                "completed_at": datetime.fromisoformat(result_data["completed_at"]),
            }
        )
        if result_data
        else None
    )
    lease = row.get("lease_expires_at")
    lease_expires_at = datetime.fromisoformat(lease) if isinstance(lease, str) else lease
    return DelegationTaskRecord(
        task=task,
        status=row["status"],
        lease_owner=row.get("lease_owner"),
        lease_expires_at=lease_expires_at,
        result=result,
        failure_code=row.get("failure_code"),
    )


def _statement_rows(response: Any) -> list[dict[str, Any]]:
    result = getattr(response, "result", None)
    manifest = getattr(response, "manifest", None)
    data_array = getattr(result, "data_array", None)
    columns = getattr(getattr(manifest, "schema", None), "columns", None)
    if not data_array or not columns:
        return []
    names = [
        str(getattr(column, "name", column["name"] if isinstance(column, dict) else ""))
        for column in columns
    ]
    return [dict(zip(names, values, strict=True)) for values in data_array]


def default_agent_task_bus(settings: AppSettings) -> InMemoryAgentTaskBus | UcAgentTaskBus:
    """Create the configured delegation store; memory remains the safe default."""
    backend = settings.agent_task_backend.strip().lower()
    if backend == "memory":
        return InMemoryAgentTaskBus()
    if backend == "uc_table":
        return UcAgentTaskBus(
            warehouse_id=settings.agent_task_warehouse_id,
            catalog=settings.agent_task_catalog,
            schema=settings.agent_task_schema,
            task_table=settings.agent_task_table,
            event_table=settings.agent_task_event_table,
        )
    raise ValueError(f"Unsupported AGENT_TASK_BACKEND={settings.agent_task_backend!r}")
