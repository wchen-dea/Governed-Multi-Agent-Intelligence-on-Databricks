from types import SimpleNamespace

from mlflow.types.responses import ResponsesAgentRequest

from aiserver.api.dependencies import build_dependency_container
from aiserver.domain.subagent_config import SubagentConfig
from aiserver.services.orchestrator_service import OrchestratorDependencies, build_subagent_tools
from aiserver.services.runtime_auth_service import (
    RuntimeAuthDependencies,
    build_runtime_auth_context,
)


class RecordingBus:
    def __init__(self):
        self.events: list[tuple[str, dict[str, object]]] = []

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, payload))


def test_dependency_container_shares_bus_across_services():
    container = build_dependency_container()
    assert container.orchestrator.message_bus is container.runtime_auth.message_bus
    assert container.runtime_auth.message_bus is container.handlers.message_bus


def test_runtime_auth_publishes_context_events():
    subagents = [
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="knowledge_assistant",
            description="serving",
        )
    ]

    bus = RecordingBus()
    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda req: "conv-1",
        trace_metadata_updater=lambda metadata: None,
        subagent_tools_builder=lambda s, app, obo: ["tool-a"],
        mcp_servers_builder=lambda s, ctx: ([], []),
        message_bus=bus,
    )

    request = ResponsesAgentRequest(input=[])
    build_runtime_auth_context(request, subagents, app_client=object(), deps=deps)

    event_types = [event_type for event_type, _ in bus.events]
    assert "policy.subagent.decision" in event_types
    assert "auth.identity.resolved" in event_types
    assert "auth.trace.metadata.updated" in event_types
    assert "auth.context.built" in event_types


def test_subagent_tools_publish_tool_call_events():
    subagents = [
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="knowledge_assistant",
            description="serving",
        )
    ]

    bus = RecordingBus()

    class FakeResponses:
        async def create(self, model, input):
            return SimpleNamespace(output_text="ok")

    app_client = SimpleNamespace(responses=FakeResponses())
    deps = OrchestratorDependencies(
        trace_metadata_updater=lambda metadata: None,
        function_tool_wrapper=lambda fn: fn,
        message_bus=bus,
    )

    tool = build_subagent_tools(subagents, app_client, None, deps=deps)[0]

    import asyncio

    result = asyncio.run(tool("hello"))
    assert result == "ok"

    event_types = [event_type for event_type, _ in bus.events]
    assert "tool.call.started" in event_types
    assert "tool.call.succeeded" in event_types
