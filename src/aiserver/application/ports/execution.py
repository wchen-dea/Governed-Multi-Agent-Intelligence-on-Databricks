"""Application ports for governed agent execution."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from aiserver.contracts.execution import (
    ExecutionMessage,
    ExecutionStreamEvent,
    GovernedExecutionRequest,
    GovernedExecutionResult,
    RunnerExecutionResult,
    RunnerStreamEvent,
)


class AgentRunner(Protocol):
    """Execute an assembled agent without coupling use cases to an agent SDK."""

    async def run(
        self,
        agent: object,
        messages: Sequence[ExecutionMessage],
    ) -> RunnerExecutionResult: ...

    def stream(
        self,
        agent: object,
        messages: Sequence[ExecutionMessage],
    ) -> AsyncIterator[RunnerStreamEvent]: ...


class AgentExecutionService(Protocol):
    """Execute governed requests independently of HTTP or MLflow delivery."""

    async def invoke(self, request: GovernedExecutionRequest) -> GovernedExecutionResult: ...

    def stream(
        self,
        request: GovernedExecutionRequest,
    ) -> AsyncIterator[ExecutionStreamEvent]: ...
