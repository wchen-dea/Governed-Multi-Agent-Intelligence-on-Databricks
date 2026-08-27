"""Define typed runtime service interfaces for dependency injection and tests."""

from typing import Any, Protocol

from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.types.responses import ResponsesAgentRequest

from aiserver.domain.agent_messages import DelegationResult, DelegationTask, DelegationTaskRecord
from aiserver.domain.subagent_config import SubagentConfig
from aiserver.shared.runtime_utils import RequestIdentityContext


class IdentityContextProvider(Protocol):
    """Return request identity context for app and OBO execution paths."""

    def __call__(self) -> RequestIdentityContext: ...


class SessionIdProvider(Protocol):
    """Extract a session id from an incoming request payload."""

    def __call__(self, request: ResponsesAgentRequest) -> str | None: ...


class TraceMetadataUpdater(Protocol):
    """Persist authorization metadata on the active trace."""

    def __call__(self, metadata: dict[str, str]) -> Any: ...


class OboClientFactory(Protocol):
    """Build a user-scoped Databricks OpenAI client for OBO execution."""

    def __call__(self, workspace_client: Any) -> AsyncDatabricksOpenAI: ...


class SubagentToolsBuilder(Protocol):
    """Build function tools for configured non-MCP subagents."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
    ) -> list: ...


class McpServersBuilder(Protocol):
    """Build MCP servers and unavailability reasons for the current request."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        identity_ctx: RequestIdentityContext,
    ) -> tuple[list[McpServer], list[str]]: ...


class LakebaseToolsBuilder(Protocol):
    """Build function tools for Lakebase subagents."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        identity_ctx: RequestIdentityContext,
    ) -> list: ...


class FunctionToolWrapper(Protocol):
    """Wrap an async callable as an agent function tool."""

    def __call__(self, func: Any) -> Any: ...


class McpServerFactory(Protocol):
    """Build an MCP server instance from connection details."""

    def __call__(
        self, *, url: str, name: str, workspace_client: Any, timeout: float | None = None
    ) -> McpServer: ...


class MessageBus(Protocol):
    """Publish typed lifecycle events for request-scoped execution."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None: ...


class AgentTaskBus(Protocol):
    """Persist and lease durable agent-delegation tasks independently of audit events."""

    async def submit(self, task: DelegationTask) -> DelegationTaskRecord: ...
    async def claim(
        self, worker_id: str, *, limit: int = 1, lease_seconds: int = 60
    ) -> list[DelegationTaskRecord]: ...
    async def mark_running(self, task_id: str, worker_id: str) -> DelegationTaskRecord: ...
    async def complete(self, result: DelegationResult, worker_id: str) -> DelegationTaskRecord: ...
    async def fail(self, task_id: str, worker_id: str, error_code: str) -> DelegationTaskRecord: ...
    async def get(self, task_id: str) -> DelegationTaskRecord | None: ...


class ConversationMemory(Protocol):
    """Persist and recall conversation turns and persona preferences."""

    def save_turn(
        self, conversation_id: str, persona: str | None, role: str, content: str
    ) -> None: ...
    def recent_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]: ...
    def save_persona_preference(self, conversation_id: str, persona: str) -> None: ...
    def get_persona_preference(self, conversation_id: str) -> str | None: ...
