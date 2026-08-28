"""Define Lakebase execution application ports."""

from typing import Any, Protocol

from aiserver.application.runtime.identity import RequestIdentityContext
from aiserver.contracts.subagents import SubagentConfig


class LakebaseConnectionFactory(Protocol):
    """Open a Lakebase PostgreSQL connection for a configured target."""

    def __call__(
        self,
        workspace_client: Any,
        *,
        project_id: str,
        branch_id: str,
        endpoint_id: str,
        database: str,
        pg_host: str,
        pg_user: str | None = None,
    ) -> Any: ...


class LakebaseToolsBuilder(Protocol):
    """Build function tools for Lakebase subagents."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        identity_ctx: RequestIdentityContext,
    ) -> list: ...


class LakebaseDelegationExecutorsBuilder(Protocol):
    """Build executors for delegated Lakebase tasks."""

    def __call__(
        self,
        subagents: list[SubagentConfig],
        identity_ctx: RequestIdentityContext,
    ) -> dict[str, Any]: ...