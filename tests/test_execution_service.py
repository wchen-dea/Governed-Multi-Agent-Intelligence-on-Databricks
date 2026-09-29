"""Behavior tests for the framework-neutral governed execution service."""

import asyncio

import pytest

from aiserver.application.auth.context import RuntimeAuthContext
from aiserver.application.exceptions import GovernedExecutionError
from aiserver.application.execution.service import (
    GovernedAgentService,
    GovernedAgentServiceDependencies,
)
from aiserver.application.guardrails.checks import GuardrailResult, InputGuardrailResult
from aiserver.application.orchestration.model import ModelSelection
from aiserver.config.settings import AppSettings
from aiserver.contracts.execution import (
    ExecutionMessage,
    GovernedExecutionRequest,
    RunnerExecutionResult,
    RunnerStreamEvent,
)
from aiserver.contracts.responses import RoutePlan
from aiserver.contracts.subagents import SubagentConfig


class RecordingBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, payload))


class RecordingMemory:
    def __init__(self) -> None:
        self.turns: list[tuple[str, str | None, str, str]] = []

    def save_turn(
        self,
        conversation_id: str,
        persona: str | None,
        role: str,
        content: str,
    ) -> None:
        self.turns.append((conversation_id, persona, role, content))

    def recent_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]:
        return []

    def save_persona_preference(self, conversation_id: str, persona: str) -> None:
        return None

    def get_persona_preference(self, conversation_id: str) -> str | None:
        return None


class FakeRunner:
    async def run(self, agent, messages):
        return RunnerExecutionResult(
            output_items=(
                {
                    "role": "assistant",
                    "content": "Revenue increased after the promotion.",
                    "name": "query_sales_agent",
                },
            )
        )

    async def stream(self, agent, messages):
        yield RunnerStreamEvent(
            payload={
                "type": "response.output_item.added",
                "item": {"type": "function_call", "name": "query_sales_agent"},
            }
        )
        yield RunnerStreamEvent(
            payload={
                "type": "response.output_text.delta",
                "item_id": "answer",
                "delta": "Revenue increased.",
            }
        )


def _service() -> tuple[GovernedAgentService, RecordingBus, RecordingMemory]:
    subagent = SubagentConfig(
        name="sales_agent",
        kind="serving_endpoint",
        endpoint="sales-endpoint",
        description="sales performance",
        freshness_sla="15m",
        requires_evidence=True,
    )
    runtime_auth = RuntimeAuthContext(
        subagent_tools=[type("Tool", (), {"name": "query_sales_agent"})()],
        mcp_servers=[],
        unavailable_auth=[],
        policy_allowed_subagents=[subagent],
    )
    bus = RecordingBus()
    memory = RecordingMemory()

    async def connect(stack, servers):
        return [], []

    dependencies = GovernedAgentServiceDependencies(
        settings=AppSettings(memory_max_turns=0),
        subagents=(subagent,),
        runtime_auth_builder=lambda request: runtime_auth,
        mcp_connector=connect,
        orchestrator_factory=lambda model, candidates, servers, tools, unavailable: object(),
        route_planner=lambda question, subagents, conversation_id: (
            RoutePlan(
                candidates=("sales_agent",),
                reason="capability_match",
                confidence=1.0,
                requires_evidence=True,
            ),
            subagents,
        ),
        model_selector=lambda question, settings: ModelSelection(
            model="test-model",
            task_type="standard",
            reason="test",
            rationale="test route",
        ),
        input_guardrails_evaluator=lambda items, max_input_chars: InputGuardrailResult(
            blocked=False,
            reasons=(),
            character_count=10,
        ),
        response_guardrails_evaluator=lambda text, subagents: GuardrailResult(
            blocked=False,
            reasons=(),
        ),
        message_bus=bus,
        memory=memory,
        runner=FakeRunner(),
    )
    return GovernedAgentService(dependencies), bus, memory


def _request() -> GovernedExecutionRequest:
    return GovernedExecutionRequest(
        messages=(ExecutionMessage(role="user", content="How did revenue change?"),),
        conversation_id="conversation-1",
        persona="store-manager",
    )


def test_invoke_applies_source_metadata_and_persists_memory():
    service, bus, memory = _service()

    result = asyncio.run(service.invoke(_request()))

    assert result.envelope.status == "succeeded"
    assert result.envelope.route_plan.candidates == ("sales_agent",)
    assert "Source: sales_agent" in result.output_items[0]["content"]
    assert [turn[2] for turn in memory.turns] == ["user", "assistant"]
    assert "request.invoke.succeeded" in [event_type for event_type, _ in bus.events]


def test_invoke_audits_empty_normalized_request():
    service, bus, _ = _service()

    with pytest.raises(GovernedExecutionError, match="role-bearing"):
        asyncio.run(service.invoke(GovernedExecutionRequest(messages=())))

    assert [event_type for event_type, _ in bus.events] == [
        "request.invoke.started",
        "request.invoke.failed",
    ]


def test_stream_audits_empty_normalized_request():
    service, bus, _ = _service()

    async def collect():
        return [
            event async for event in service.stream(GovernedExecutionRequest(messages=()))
        ]

    with pytest.raises(GovernedExecutionError, match="role-bearing"):
        asyncio.run(collect())

    assert [event_type for event_type, _ in bus.events] == [
        "request.stream.started",
        "request.stream.failed",
    ]


def test_stream_buffers_runtime_output_until_governance_passes():
    service, bus, memory = _service()

    async def collect():
        return [event async for event in service.stream(_request())]

    events = asyncio.run(collect())
    event_types = [event.kind for event in events]

    assert event_types[:4] == ["progress", "progress", "progress", "progress"]
    assert event_types[4:7] == ["runtime", "runtime", "governance"]
    assert events[-1].kind == "text_delta"
    assert "Source: sales_agent" in events[-1].payload["delta"]
    assert [turn[2] for turn in memory.turns] == ["user", "assistant"]
    assert "request.stream.succeeded" in [event_type for event_type, _ in bus.events]
