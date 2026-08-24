import asyncio
from types import SimpleNamespace

from backend.domain.subagent_config import SubagentConfig
from backend.services.orchestrator_service import OrchestratorDependencies, build_subagent_tools


def test_tool_lifecycle_events_include_normalized_execution_metadata():
    events = []

    class Responses:
        async def create(self, **kwargs):
            return SimpleNamespace(output_text="ok")

    cfg = SubagentConfig(name="docs", kind="serving_endpoint", endpoint="docs", description="docs")
    deps = OrchestratorDependencies(
        function_tool_wrapper=lambda func: func,
        message_bus=SimpleNamespace(
            publish=lambda event_type, payload: events.append((event_type, payload))
        ),
    )
    tools = build_subagent_tools(cfg and [cfg], SimpleNamespace(responses=Responses()), None, deps)

    assert asyncio.run(tools[0]("hello")) == "ok"
    success = next(payload for event, payload in events if event == "tool.call.succeeded")
    assert success["status"] == "succeeded"
    assert success["attempt_count"] == 1
    assert success["latency_ms"] >= 0
