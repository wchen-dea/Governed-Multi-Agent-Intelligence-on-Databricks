"""Define typed runtime service interfaces for dependency injection and tests."""

from typing import Any, Protocol

from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer

from aiserver.application.runtime.identity import RequestIdentityContext
from aiserver.contracts.subagents import SubagentConfig


class ToolAdapter(Protocol):
    """Resolve and build a callable tool for a subagent."""

    def supports(self, subagent: SubagentConfig) -> bool: ...

    def build(
        self,
        *,
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
        deps: Any,
    ) -> Any: ...


class ToolRegistry(Protocol):
    """Return the adapter that should handle a subagent."""

    def resolve(self, subagent: SubagentConfig) -> ToolAdapter | None: ...


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


class FunctionToolWrapper(Protocol):
    """Wrap an async callable as an agent function tool."""

    def __call__(self, func: Any) -> Any: ...


class McpServerFactory(Protocol):
    """Build an MCP server instance from connection details."""

    def __call__(
        self, *, url: str, name: str, workspace_client: Any, timeout: float | None = None
    ) -> McpServer: ...
