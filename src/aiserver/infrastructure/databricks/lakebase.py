"""Shared Lakebase PostgreSQL connection helpers for OAuth-authenticated access."""

import logging

from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)


def get_lakebase_token(
    ws_client: WorkspaceClient,
    *,
    project_id: str,
    branch_id: str,
    endpoint_id: str,
) -> str:
    """Get an OAuth token for a Lakebase Postgres endpoint via the credentials API.

    Falls back to the workspace client's own bearer token when the dedicated
    credentials API call fails (for example during local development).
    """
    import httpx

    host = ws_client.config.host.rstrip("/")
    headers = ws_client.config.authenticate()
    endpoint_path = f"projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}"
    try:
        resp = httpx.post(
            f"{host}/api/2.0/postgres/credentials",
            json={"endpoint": endpoint_path},
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()["token"]
    except Exception as cred_exc:
        logger.warning(
            "Postgres credentials API failed (%s: %s); using workspace token",
            type(cred_exc).__name__,
            str(cred_exc)[:200],
        )
        auth_token = headers.get("Authorization", "")
        if auth_token.startswith("Bearer "):
            return auth_token[7:]
        raise ValueError(
            f"Cannot obtain Lakebase token: credentials API failed ({cred_exc}) "
            "and no Bearer token available from workspace client"
        ) from cred_exc


def connect_lakebase(
    ws_client: WorkspaceClient,
    *,
    project_id: str,
    branch_id: str,
    endpoint_id: str,
    database: str,
    pg_host: str,
    pg_user: str | None = None,
    connect_timeout: int = 15,
):
    """Open a psycopg2 connection to Lakebase Postgres using OAuth credentials."""
    import psycopg2

    token = get_lakebase_token(
        ws_client, project_id=project_id, branch_id=branch_id, endpoint_id=endpoint_id
    )
    return psycopg2.connect(
        host=pg_host,
        port=5432,
        dbname=database,
        user=pg_user or "databricks",
        password=token,
        sslmode="require",
        connect_timeout=connect_timeout,
    )
