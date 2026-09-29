"""Shared route-affinity persistence for horizontally scaled web replicas."""

import json
import re
import threading
from datetime import UTC, datetime

from databricks.sdk import WorkspaceClient

from aiserver.application.ports.routing import RouteAffinityStore
from aiserver.config.settings import AppSettings
from aiserver.contracts.execution import RouteAffinity
from aiserver.infrastructure.databricks.lakebase import connect_lakebase

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class NoopRouteAffinityStore:
    """Disable sticky routing without retaining process-local state."""

    def get(self, conversation_id: str) -> RouteAffinity | None:
        del conversation_id
        return None

    def put(self, affinity: RouteAffinity) -> None:
        del affinity

    def delete(self, conversation_id: str) -> None:
        del conversation_id


class InMemoryRouteAffinityStore:
    """Concurrency-safe affinity storage for tests and local development."""

    def __init__(self) -> None:
        self._records: dict[str, RouteAffinity] = {}
        self._lock = threading.Lock()

    def get(self, conversation_id: str) -> RouteAffinity | None:
        with self._lock:
            affinity = self._records.get(conversation_id)
            if affinity is not None and affinity.expires_at <= datetime.now(UTC):
                self._records.pop(conversation_id, None)
                return None
            return affinity

    def put(self, affinity: RouteAffinity) -> None:
        with self._lock:
            self._records[affinity.conversation_id] = affinity

    def delete(self, conversation_id: str) -> None:
        with self._lock:
            self._records.pop(conversation_id, None)


class LakebaseRouteAffinityStore:
    """Persist short-lived route affinity in Lakebase Postgres."""

    def __init__(
        self,
        *,
        project_id: str,
        branch_id: str,
        endpoint_id: str,
        database: str,
        pg_host: str,
        pg_user: str,
        table: str,
        workspace_client: WorkspaceClient | None = None,
    ) -> None:
        if not (project_id and branch_id and endpoint_id and database and pg_host):
            raise ValueError(
                "ROUTE_AFFINITY_PROJECT_ID, ROUTE_AFFINITY_BRANCH_ID, "
                "ROUTE_AFFINITY_ENDPOINT_ID, ROUTE_AFFINITY_DATABASE, and "
                "ROUTE_AFFINITY_PG_HOST are required for the lakebase backend"
            )
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError("ROUTE_AFFINITY_TABLE must be a valid SQL identifier")
        self._project_id = project_id
        self._branch_id = branch_id
        self._endpoint_id = endpoint_id
        self._database = database
        self._pg_host = pg_host
        self._pg_user = pg_user
        self._table = table
        self._workspace_client = workspace_client or WorkspaceClient()
        self._ensure_table()

    def _connect(self):
        return connect_lakebase(
            self._workspace_client,
            project_id=self._project_id,
            branch_id=self._branch_id,
            endpoint_id=self._endpoint_id,
            database=self._database,
            pg_host=self._pg_host,
            pg_user=self._pg_user,
        )

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS {self._table} ("
                    "conversation_id TEXT PRIMARY KEY, "
                    "candidate_names JSONB NOT NULL, "
                    "expires_at TIMESTAMPTZ NOT NULL, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._table}_expires_at "
                    f"ON {self._table} (expires_at)"
                )
            conn.commit()
        finally:
            conn.close()

    def get(self, conversation_id: str) -> RouteAffinity | None:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {self._table} WHERE conversation_id = %s "
                    "AND expires_at <= now()",
                    (conversation_id,),
                )
                cursor.execute(
                    f"SELECT candidate_names, expires_at FROM {self._table} "
                    "WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = cursor.fetchone()
            conn.commit()
        finally:
            conn.close()
        if row is None:
            return None
        candidate_names, expires_at = row
        if isinstance(candidate_names, str):
            candidate_names = json.loads(candidate_names)
        return RouteAffinity(
            conversation_id=conversation_id,
            candidate_names=tuple(candidate_names),
            expires_at=expires_at,
        )

    def put(self, affinity: RouteAffinity) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO {self._table} "
                    "(conversation_id, candidate_names, expires_at) "
                    "VALUES (%s, %s::jsonb, %s) "
                    "ON CONFLICT (conversation_id) DO UPDATE SET "
                    "candidate_names = EXCLUDED.candidate_names, "
                    "expires_at = EXCLUDED.expires_at, updated_at = now()",
                    (
                        affinity.conversation_id,
                        json.dumps(affinity.candidate_names),
                        affinity.expires_at,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def delete(self, conversation_id: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {self._table} WHERE conversation_id = %s",
                    (conversation_id,),
                )
            conn.commit()
        finally:
            conn.close()


def default_route_affinity_store(settings: AppSettings) -> RouteAffinityStore:
    """Create the configured route-affinity store."""
    backend = settings.route_affinity_backend.strip().lower()
    if backend in {"", "disabled", "noop"}:
        return NoopRouteAffinityStore()
    if backend == "memory":
        return InMemoryRouteAffinityStore()
    if backend == "lakebase":
        return LakebaseRouteAffinityStore(
            project_id=settings.route_affinity_project_id,
            branch_id=settings.route_affinity_branch_id,
            endpoint_id=settings.route_affinity_endpoint_id,
            database=settings.route_affinity_database,
            pg_host=settings.route_affinity_pg_host,
            pg_user=settings.route_affinity_pg_user,
            table=settings.route_affinity_table,
        )
    raise ValueError(
        f"Unsupported ROUTE_AFFINITY_BACKEND={settings.route_affinity_backend!r}"
    )
