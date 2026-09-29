"""Define authorization-related application ports."""

from typing import Any, Protocol

from databricks_openai import AsyncDatabricksOpenAI

from aiserver.application.runtime.identity import RequestIdentityContext
from aiserver.contracts.execution import GovernedExecutionRequest


class IdentityContextProvider(Protocol):
    """Return request identity context for app and OBO execution paths."""

    def __call__(self) -> RequestIdentityContext: ...


class SessionIdProvider(Protocol):
    """Extract a session id from an incoming request payload."""

    def __call__(self, request: GovernedExecutionRequest) -> str | None: ...


class OboClientFactory(Protocol):
    """Build a user-scoped Databricks OpenAI client for OBO execution."""

    def __call__(self, workspace_client: Any) -> AsyncDatabricksOpenAI: ...