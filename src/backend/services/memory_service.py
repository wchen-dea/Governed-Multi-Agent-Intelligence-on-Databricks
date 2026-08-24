"""Conversation and persona-preference memory backed by Lakebase PostgreSQL.

Disabled by default (`MEMORY_BACKEND=disabled`). When enabled, this stores raw
conversation turns and remembered persona preferences in Lakebase, keyed by the
request's session/conversation id. Operators should review data classification
and retention requirements before enabling persistence of conversation content.
"""

import logging

from databricks.sdk import WorkspaceClient

from backend.shared.lakebase_client import connect_lakebase
from backend.shared.settings import AppSettings, get_settings

logger = logging.getLogger(__name__)


class NoopConversationMemory:
    """Discard all memory operations when the memory backend is disabled."""

    def save_turn(self, conversation_id: str, persona: str | None, role: str, content: str) -> None:
        del conversation_id, persona, role, content

    def recent_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]:
        del conversation_id, limit
        return []

    def save_persona_preference(self, conversation_id: str, persona: str) -> None:
        del conversation_id, persona

    def get_persona_preference(self, conversation_id: str) -> str | None:
        del conversation_id
        return None


class LakebaseConversationMemory:
    """Persist conversation turns and persona preferences to Lakebase Postgres.

    Args:
        project_id: Lakebase project id.
        branch_id: Lakebase branch id.
        endpoint_id: Lakebase compute endpoint id.
        database: Lakebase database name.
        pg_host: Lakebase Postgres host.
        pg_user: Optional Postgres role; defaults to "databricks".
        conversation_table: Table name for conversation turns.
        preference_table: Table name for persona preferences.
        fail_open: When true, log and swallow persistence errors instead of raising.
        workspace_client: Optional workspace client override (for tests).

    Raises:
        ValueError: If required Lakebase connection fields are missing.
    """

    def __init__(
        self,
        *,
        project_id: str,
        branch_id: str,
        endpoint_id: str,
        database: str,
        pg_host: str,
        pg_user: str,
        conversation_table: str,
        preference_table: str,
        fail_open: bool,
        workspace_client: WorkspaceClient | None = None,
    ) -> None:
        if not (project_id and branch_id and endpoint_id and database and pg_host):
            raise ValueError(
                "MEMORY_PROJECT_ID, MEMORY_BRANCH_ID, MEMORY_ENDPOINT_ID, MEMORY_DATABASE, "
                "and MEMORY_PG_HOST must all be set when MEMORY_BACKEND=lakebase"
            )
        self._project_id = project_id
        self._branch_id = branch_id
        self._endpoint_id = endpoint_id
        self._database = database
        self._pg_host = pg_host
        self._pg_user = pg_user
        self._conversation_table = conversation_table
        self._preference_table = preference_table
        self._fail_open = fail_open
        self._workspace_client = workspace_client or WorkspaceClient()
        self._ensure_schema()

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

    def _ensure_schema(self) -> None:
        """Create memory tables if they do not already exist."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self._conversation_table} ("
                    "id BIGSERIAL PRIMARY KEY, "
                    "conversation_id TEXT NOT NULL, "
                    "persona TEXT, "
                    "role TEXT NOT NULL, "
                    "content TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._conversation_table}_conv "
                    f"ON {self._conversation_table} (conversation_id, created_at)"
                )
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self._preference_table} ("
                    "conversation_id TEXT PRIMARY KEY, "
                    "persona TEXT NOT NULL, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                )
            conn.commit()
        finally:
            conn.close()

    def save_turn(self, conversation_id: str, persona: str | None, role: str, content: str) -> None:
        """Persist a single conversation turn, swallowing errors when fail-open."""
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {self._conversation_table} "
                        "(conversation_id, persona, role, content) VALUES (%s, %s, %s, %s)",
                        (conversation_id, persona, role, content),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            if self._fail_open:
                logger.exception("Lakebase memory save_turn failed; dropping turn")
                return
            raise

    def recent_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]:
        """Return the most recent turns for a conversation, oldest first."""
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT role, content FROM {self._conversation_table} "
                        "WHERE conversation_id = %s ORDER BY created_at DESC LIMIT %s",
                        (conversation_id, max(limit, 1)),
                    )
                    rows = cur.fetchall()
                return [{"role": role, "content": content} for role, content in reversed(rows)]
            finally:
                conn.close()
        except Exception:
            if self._fail_open:
                logger.exception("Lakebase memory recent_turns failed; returning empty history")
                return []
            raise

    def save_persona_preference(self, conversation_id: str, persona: str) -> None:
        """Remember the last persona selected for a conversation."""
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {self._preference_table} (conversation_id, persona) "
                        "VALUES (%s, %s) ON CONFLICT (conversation_id) "
                        "DO UPDATE SET persona = EXCLUDED.persona, updated_at = now()",
                        (conversation_id, persona),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            if self._fail_open:
                logger.exception("Lakebase memory save_persona_preference failed; dropping update")
                return
            raise

    def get_persona_preference(self, conversation_id: str) -> str | None:
        """Return the last remembered persona for a conversation, if any."""
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT persona FROM {self._preference_table} WHERE conversation_id = %s",
                        (conversation_id,),
                    )
                    row = cur.fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except Exception:
            if self._fail_open:
                logger.exception(
                    "Lakebase memory get_persona_preference failed; returning no preference"
                )
                return None
            raise


def default_conversation_memory(settings: AppSettings | None = None):
    """Create the configured conversation memory implementation for runtime use.

    Notes:
        Falls back to a no-op implementation when disabled or when
        initialization fails and fail-open is enabled.
    """
    cfg = settings or get_settings()
    backend = cfg.memory_backend.strip().lower()

    if backend in {"", "disabled", "noop"}:
        return NoopConversationMemory()
    if backend == "lakebase":
        try:
            return LakebaseConversationMemory(
                project_id=cfg.memory_project_id,
                branch_id=cfg.memory_branch_id,
                endpoint_id=cfg.memory_endpoint_id,
                database=cfg.memory_database,
                pg_host=cfg.memory_pg_host,
                pg_user=cfg.memory_pg_user,
                conversation_table=cfg.memory_conversation_table,
                preference_table=cfg.memory_preference_table,
                fail_open=cfg.memory_fail_open,
            )
        except Exception:
            if cfg.memory_fail_open:
                logger.exception(
                    "Lakebase memory backend initialization failed; falling back to no-op memory"
                )
                return NoopConversationMemory()
            raise

    logger.warning("Unknown MEMORY_BACKEND %r; falling back to no-op memory", backend)
    return NoopConversationMemory()
