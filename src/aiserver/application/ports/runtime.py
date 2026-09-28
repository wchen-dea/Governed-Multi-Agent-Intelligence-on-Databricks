"""Application port for executing governed agent requests."""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from aiserver.contracts.public_api import ChatRequest


class AgentRuntimePort(Protocol):
    """Runtime-neutral interface used by the public HTTP API."""

    async def invoke(self, request: ChatRequest) -> dict[str, Any]:
        """Execute a non-streaming chat request."""

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        """Yield public stream events for a chat request."""