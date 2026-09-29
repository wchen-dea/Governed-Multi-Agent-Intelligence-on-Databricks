"""Shared runtime helpers for identity, session handling, and streaming.

These helpers centralize request-scoped Databricks client construction,
forwarded-token handling, and stream event normalization used by the backend.
"""

import hashlib
import logging
from dataclasses import dataclass

from databricks.sdk import WorkspaceClient

from aiserver.contracts.execution import GovernedExecutionRequest

FORWARDED_ACCESS_TOKEN_HEADER = "x-forwarded-access-token"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestIdentityContext:
    """Resolved app and user identity state for a single request."""

    app_workspace_client: WorkspaceClient
    user_workspace_client: WorkspaceClient | None
    forwarded_access_token: str | None

    @property
    def has_user_identity(self) -> bool:
        return bool(self.user_workspace_client and self.forwarded_access_token)


def get_session_id(
    request: GovernedExecutionRequest,
    forwarded_access_token: str | None = None,
) -> str | None:
    """Extract a stable session identifier from request context or custom inputs."""
    if request.conversation_id:
        return request.conversation_id
    sid = request.metadata.get("session_id")
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    if forwarded_access_token:
        return hashlib.sha256(forwarded_access_token[:64].encode()).hexdigest()[:24]
    return None


def get_databricks_host(workspace_client: WorkspaceClient | None = None) -> str | None:
    """Resolve the Databricks workspace host from client configuration."""
    workspace_client = workspace_client or WorkspaceClient()
    try:
        return workspace_client.config.host
    except Exception:
        logger.exception("Failed to resolve Databricks host from environment")
        return None


def build_mcp_url(path: str, workspace_client: WorkspaceClient | None = None) -> str:
    """Convert a workspace-relative MCP path into an absolute URL."""
    if not path.startswith("/"):
        return path
    hostname = get_databricks_host(workspace_client)
    return f"{hostname}{path}"


def get_user_workspace_client(forwarded_access_token: str | None) -> WorkspaceClient:
    """Create a workspace client authenticated with the forwarded user token."""
    token = forwarded_access_token.strip() if forwarded_access_token else None
    if not token:
        raise ValueError(
            f"Missing required forwarded access token header: {FORWARDED_ACCESS_TOKEN_HEADER}"
        )
    return WorkspaceClient(token=token, auth_type="pat")


def build_request_identity_context(
    forwarded_access_token: str | None = None,
) -> RequestIdentityContext:
    """Build the request-scoped app and optional user identity clients."""
    app_workspace_client = WorkspaceClient()
    token = forwarded_access_token.strip() if forwarded_access_token else None
    user_workspace_client = WorkspaceClient(token=token, auth_type="pat") if token else None
    return RequestIdentityContext(
        app_workspace_client=app_workspace_client,
        user_workspace_client=user_workspace_client,
        forwarded_access_token=token,
    )
