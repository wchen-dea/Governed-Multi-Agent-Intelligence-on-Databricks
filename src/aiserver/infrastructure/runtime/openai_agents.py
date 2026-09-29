"""OpenAI Agents SDK adapter for the application runner port."""

import logging
from collections.abc import AsyncIterator, Sequence

from agents import Runner
from agents.exceptions import UserError
from openai.types.responses.easy_input_message_param import EasyInputMessageParam

from aiserver.application.exceptions import GovernedExecutionError
from aiserver.application.ports.execution import AgentRunner
from aiserver.application.runtime.streaming import process_agent_stream_events
from aiserver.contracts.execution import (
    ExecutionMessage,
    RunnerExecutionResult,
    RunnerStreamEvent,
)

logger = logging.getLogger(__name__)


class OpenAIAgentsRunner(AgentRunner):
    """Execute assembled agents and normalize SDK-specific outputs."""

    async def run(
        self,
        agent: object,
        messages: Sequence[ExecutionMessage],
    ) -> RunnerExecutionResult:
        try:
            result = await Runner.run(agent, _runtime_messages(messages))
        except UserError as exc:
            raise GovernedExecutionError(str(exc)) from exc
        return RunnerExecutionResult(
            output_items=tuple(item.to_input_item() for item in result.new_items),
        )

    async def stream(
        self,
        agent: object,
        messages: Sequence[ExecutionMessage],
    ) -> AsyncIterator[RunnerStreamEvent]:
        try:
            result = Runner.run_streamed(agent, input=_runtime_messages(messages))
            async for event in process_agent_stream_events(result.stream_events()):
                payload = event.model_dump() if hasattr(event, "model_dump") else event
                if isinstance(payload, dict):
                    yield RunnerStreamEvent(payload=payload)
                else:
                    logger.warning(
                        "Dropping unsupported runner stream event payload type: %s",
                        type(payload).__name__,
                    )
        except UserError as exc:
            raise GovernedExecutionError(str(exc)) from exc


def _runtime_messages(
    messages: Sequence[ExecutionMessage],
) -> list[EasyInputMessageParam]:
    return [
        EasyInputMessageParam(role=message.role, content=message.content)
        for message in messages
    ]
