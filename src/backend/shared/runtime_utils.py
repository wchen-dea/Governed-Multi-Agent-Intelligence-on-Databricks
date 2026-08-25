"""Shared runtime helpers for identity, session handling, and streaming.

These helpers centralize request-scoped Databricks client construction,
forwarded-token handling, and stream event normalization used by the backend.
"""

import logging
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass

from agents.result import StreamEvent
from databricks.sdk import WorkspaceClient
from mlflow.genai.agent_server import get_request_headers
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentStreamEvent

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


def get_session_id(request: ResponsesAgentRequest) -> str | None:
    """Extract a stable session identifier from request context or custom inputs."""
    if request.context and request.context.conversation_id:
        return request.context.conversation_id
    if request.custom_inputs and isinstance(request.custom_inputs, dict):
        sid = request.custom_inputs.get("session_id")
        if sid:
            return sid
    # Fallback: derive a stable session ID from the forwarded access token header.
    import hashlib
    try:
        from mlflow.genai.agent_server import get_request_headers
        headers = get_request_headers() or {}
        fwd_token = headers.get("x-forwarded-access-token", "")
        if fwd_token:
            return hashlib.sha256(fwd_token[:64].encode()).hexdigest()[:24]
    except Exception:
        pass
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


def get_user_workspace_client() -> WorkspaceClient:
    """Create a workspace client authenticated with the forwarded user token."""
    token = get_forwarded_access_token()
    if not token:
        raise ValueError(
            f"Missing required forwarded access token header: {FORWARDED_ACCESS_TOKEN_HEADER}"
        )
    return WorkspaceClient(token=token, auth_type="pat")


def get_forwarded_access_token() -> str | None:
    """Read the forwarded user token from inbound request headers."""
    headers = get_request_headers() or {}
    token = headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
    if not token:
        return None
    stripped = token.strip()
    return stripped or None


def build_request_identity_context() -> RequestIdentityContext:
    """Build the request-scoped app and optional user identity clients."""
    app_workspace_client = WorkspaceClient()
    token = get_forwarded_access_token()
    user_workspace_client = WorkspaceClient(token=token, auth_type="pat") if token else None
    return RequestIdentityContext(
        app_workspace_client=app_workspace_client,
        user_workspace_client=user_workspace_client,
        forwarded_access_token=token,
    )


async def process_agent_stream_events(
    async_stream: AsyncIterator[StreamEvent],
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Normalize streamed item identifiers for downstream consumers."""
    item_counter = 0
    curr_item_id = f"item_{item_counter}"
    async for event in async_stream:
        if event.type == "raw_response_event":
            event_data = event.data.model_dump()
            if event_data["type"] == "response.output_item.added":
                item_counter += 1
                curr_item_id = f"item_{item_counter}"
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item") is not None and event_data["item"].get("id") is not None:
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item_id") is not None:
                event_data["item_id"] = curr_item_id
            yield event_data
        elif event.type == "run_item_stream_event" and event.item.type == "tool_call_output_item":
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=event.item.to_input_item(),
            )
