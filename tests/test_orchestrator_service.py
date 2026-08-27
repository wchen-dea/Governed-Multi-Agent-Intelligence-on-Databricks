import asyncio
from types import SimpleNamespace

from aiserver.domain.subagent_config import SubagentConfig
from aiserver.services.orchestrator_service import (
    OrchestratorDependencies,
    _lakebase_failure_result,
    build_mcp_servers,
    build_subagent_tools,
    connect_healthy_mcp_servers,
    create_orchestrator_agent,
)


def test_lakebase_failure_result_classifies_authorization_without_details():
    result, category = _lakebase_failure_result(RuntimeError("OAuth: User is not authorized"))

    assert category == "authorization"
    assert "not authorized" in result.lower()
    assert "OAuth:" not in result
    assert "query returned no data" in result.lower()


def test_build_subagent_tools_uses_injected_wrapper_and_trace_updater():
    subagents = [
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            endpoint="knowledge_assistant",
            description="serving",
        )
    ]

    class FakeResponses:
        async def create(self, model, input):
            assert model == "knowledge_assistant"
            assert input[0]["content"] == "hello"
            return SimpleNamespace(output_text="ok")

    app_client = SimpleNamespace(responses=FakeResponses())
    trace_payload = {}

    deps = OrchestratorDependencies(
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        function_tool_wrapper=lambda func: func,
    )

    tools = build_subagent_tools(subagents, app_client, None, deps=deps)
    assert len(tools) == 1

    result = asyncio.run(tools[0]("hello"))

    assert result == "ok"
    assert trace_payload["auth.tool_name"] == "query_knowledge_assistant"
    assert trace_payload["auth.auth_mode_selected"] == "app"
    assert trace_payload["auth.user_token_present"] == "false"


def test_build_mcp_servers_uses_factory_and_tracks_obo_unavailable():
    subagents = [
        SubagentConfig(
            name="sales_obo",
            kind="genie",
            auth_mode="obo",
            space_id="space-obo",
            description="genie obo",
        ),
        SubagentConfig(
            name="sales_app",
            kind="genie",
            auth_mode="app",
            space_id="space-app",
            description="genie app",
        ),
    ]

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )

    created = []

    def fake_mcp_server_factory(**kwargs):
        created.append(kwargs)
        return kwargs

    deps = OrchestratorDependencies(mcp_server_factory=fake_mcp_server_factory)

    servers, unavailable = build_mcp_servers(subagents, identity_ctx, deps=deps)

    assert len(servers) == 1
    assert len(created) == 1
    assert created[0]["name"] == "Genie:sales_app"
    assert "space-app" in created[0]["url"]
    assert unavailable == ["Genie MCP tools (sales_obo) requires user authorization (OBO)"]


def test_build_mcp_servers_supports_generic_mcp_subagent():
    subagents = [
        SubagentConfig(
            name="product_search",
            kind="mcp",
            auth_mode="app",
            mcp_url="/api/2.0/mcp/ai-search/catalog/schema/index",
            description="ai search mcp",
        )
    ]

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )

    created = []

    def fake_mcp_server_factory(**kwargs):
        created.append(kwargs)
        return kwargs

    deps = OrchestratorDependencies(mcp_server_factory=fake_mcp_server_factory)

    servers, unavailable = build_mcp_servers(subagents, identity_ctx, deps=deps)

    assert len(servers) == 1
    assert unavailable == []
    assert created[0]["name"] == "MCP:product_search"
    assert created[0]["url"].endswith("/api/2.0/mcp/ai-search/catalog/schema/index")


def test_create_orchestrator_agent_requires_explicit_evidence_format_for_governed_tools():
    subagents = [
        SubagentConfig(
            name="sales_insights_agent",
            kind="genie",
            auth_mode="obo",
            data_classification="confidential",
            owner="sales-analytics",
            freshness_sla="15m",
            allowed_personas=("manager",),
            requires_evidence=True,
            space_id="space-1",
            description="sales genie",
        )
    ]

    agent = create_orchestrator_agent("test-model", subagents, [], [])

    assert "evidence=true" in agent.instructions
    assert "Source:" in agent.instructions
    assert "freshness SLA" in agent.instructions


def test_create_orchestrator_agent_includes_subagent_system_prompt():
    subagents = [
        SubagentConfig(
            name="product_index_assistant",
            kind="mcp",
            auth_mode="app",
            data_classification="internal",
            owner="platform-docs",
            freshness_sla="24h",
            allowed_personas=("manager",),
            requires_evidence=False,
            mcp_url="/api/2.0/mcp/ai-search/catalog/schema/index",
            description="product knowledge",
            system_prompt="Ground responses in index records.",
        )
    ]

    agent = create_orchestrator_agent("test-model", subagents, [], [])

    assert "System prompt: Ground responses in index records." in agent.instructions


def test_create_orchestrator_agent_requires_data_tool_attempt_before_refusal():
    subagents = [
        SubagentConfig(
            name="lakebase_ods_agent",
            kind="lakebase",
            auth_mode="app",
            project_id="ore",
            branch_id="production",
            database="operations",
            pg_host="lakebase.example.com",
            endpoint_id="primary",
            description="appointments, orders, invoices, and scheduling operational data",
        )
    ]

    agent = create_orchestrator_agent("test-model", subagents, [], [])

    assert "MUST call the matching configured tool" in agent.instructions
    assert "unless a tool call was attempted" in agent.instructions
    assert "one schema-discovery query followed by one data query" in agent.instructions
    assert "do not stop after returning schema metadata" in agent.instructions
    assert "LAKEBASE_QUERY_FAILED" in agent.instructions


def test_connect_healthy_mcp_servers_returns_detailed_unavailable_reason():
    class HealthyServer:
        name = "Genie:healthy"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def list_tools(self):
            return []

    class BrokenServer:
        name = "Genie:sales_insights_agent"

        async def __aenter__(self):
            raise RuntimeError("401 unauthorized")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def _run():
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            return await connect_healthy_mcp_servers(
                stack,
                [HealthyServer(), BrokenServer()],
            )

    healthy, unavailable = asyncio.run(_run())

    assert len(healthy) == 1
    assert unavailable == ["Genie:sales_insights_agent unavailable: RuntimeError: 401 unauthorized"]


def test_create_orchestrator_agent_includes_unavailable_details():
    agent = create_orchestrator_agent(
        "test-model",
        [],
        [],
        [],
        ["Genie:sales_insights_agent unavailable: RuntimeError: 401 unauthorized"],
    )

    assert "Unavailable tool/runtime details:" in agent.instructions
    assert (
        "Genie:sales_insights_agent unavailable: RuntimeError: 401 unauthorized"
        in agent.instructions
    )
