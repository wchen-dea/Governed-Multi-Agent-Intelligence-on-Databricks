"""Approval decision persistence adapters."""

import logging
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

from aiserver.config.settings import AppSettings, get_settings
from aiserver.contracts.responses import ApprovalDecisionRecord

logger = logging.getLogger(__name__)


class InMemoryApprovalRepository:
    """Development repository used when durable approval storage is disabled."""

    def __init__(self) -> None:
        self._records: dict[str, ApprovalDecisionRecord] = {}

    def save(self, record: ApprovalDecisionRecord) -> ApprovalDecisionRecord:
        self._records[record.request_id] = record
        return record

    def get(self, request_id: str) -> ApprovalDecisionRecord | None:
        return self._records.get(request_id)


class UcApprovalRepository:
    """Persist approval decisions in a Unity Catalog Delta table."""

    def __init__(self, warehouse_id: str, catalog: str, schema: str, table: str, fail_open: bool,
                 workspace_client: WorkspaceClient | None = None) -> None:
        if not warehouse_id or not catalog or not schema or not table:
            raise ValueError("Approval UC warehouse, catalog, schema, and table are required")
        self._warehouse_id = warehouse_id
        self._catalog = catalog
        self._schema = schema
        self._table_fqn = f"{catalog}.{schema}.{table}"
        self._fail_open = fail_open
        self._workspace_client = workspace_client or WorkspaceClient()
        self._ensure_table()

    def _execute(self, statement: str, parameters: list[StatementParameterListItem] | None = None) -> Any:
        return self._workspace_client.statement_execution.execute_statement(
            statement=statement, warehouse_id=self._warehouse_id, parameters=parameters or [],
            wait_timeout="10s", catalog=self._catalog, schema=self._schema,
        )

    def _ensure_table(self) -> None:
        self._execute(f"CREATE SCHEMA IF NOT EXISTS {self._catalog}.{self._schema}")
        self._execute(
            f"CREATE TABLE IF NOT EXISTS {self._table_fqn} ("
            "request_id STRING, agent_name STRING, store_id STRING, approver STRING, "
            "decision STRING, reason STRING, notes STRING, status STRING, updated_at TIMESTAMP"
            ") USING DELTA"
        )

    def save(self, record: ApprovalDecisionRecord) -> ApprovalDecisionRecord:
        try:
            self._execute(
                f"MERGE INTO {self._table_fqn} AS target "
                "USING (SELECT :request_id AS request_id) AS source ON target.request_id = source.request_id "
                "WHEN MATCHED THEN UPDATE SET agent_name = :agent_name, store_id = :store_id, "
                "approver = :approver, decision = :decision, reason = :reason, notes = :notes, "
                "status = :status, updated_at = current_timestamp() "
                "WHEN NOT MATCHED THEN INSERT (request_id, agent_name, store_id, approver, decision, reason, notes, status, updated_at) "
                "VALUES (:request_id, :agent_name, :store_id, :approver, :decision, :reason, :notes, :status, current_timestamp())",
                _parameters(record),
            )
        except Exception:
            if self._fail_open:
                logger.exception("Approval decision persistence failed")
                return record
            raise
        return record

    def get(self, request_id: str) -> ApprovalDecisionRecord | None:
        response = self._execute(
            f"SELECT request_id, agent_name, store_id, approver, decision, reason, notes, status FROM {self._table_fqn} "
            "WHERE request_id = :request_id LIMIT 1",
            [StatementParameterListItem(name="request_id", type="STRING", value=request_id)],
        )
        rows = getattr(getattr(response, "result", None), "data_array", None) or []
        if not rows:
            return None
        names = ("request_id", "agent_name", "store_id", "approver", "decision", "reason", "notes", "status")
        return ApprovalDecisionRecord.from_payload(dict(zip(names, rows[0], strict=False)))


def _parameters(record: ApprovalDecisionRecord) -> list[StatementParameterListItem]:
    values = {"request_id": record.request_id, "agent_name": record.agent_name, "store_id": record.store_id,
              "approver": record.approver, "decision": record.decision, "reason": record.reason,
              "notes": record.notes, "status": record.status}
    return [StatementParameterListItem(name=name, type="STRING", value=value or "") for name, value in values.items()]


def default_approval_repository(settings: AppSettings | None = None):
    """Build the configured approval repository."""
    cfg = settings or get_settings()
    if cfg.approval_backend.strip().lower() != "uc_table":
        return InMemoryApprovalRepository()
    return UcApprovalRepository(cfg.approval_warehouse_id, cfg.approval_catalog, cfg.approval_schema,
                                cfg.approval_table, cfg.approval_fail_open)