from types import SimpleNamespace

from backend.domain.subagent_config import SubagentConfig
from backend.services.runtime_auth_service import (
    RuntimeAuthDependencies,
    build_runtime_auth_context,
)
from backend.services.agent_task_bus import InMemoryAgentTaskBus
from mlflow.types.responses import ResponsesAgentRequest


def _sample_subagents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="sales_insights_agent",
            kind="genie",
            auth_mode="obo",
            data_classification="confidential",
            allowed_personas=("analyst",),
            space_id="space-1",
            description="genie",
        ),
        SubagentConfig(
            name="knowledge_assistant",
            kind="serving_endpoint",
            auth_mode="app",
            allowed_personas=("analyst", "manager"),
            endpoint="knowledge_assistant",
            description="serving",
        ),
    ]


def test_build_runtime_auth_context_without_user_identity():
    subagents = _sample_subagents()
    app_client = object()
    trace_payload = {}

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )
    def fake_build_subagent_tools(s, app, obo):
        assert s == subagents
        assert app is app_client
        assert obo is None
        return ["tool-a"]

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda req: "conv-1",
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        policy_context_builder=lambda request, identity: SimpleNamespace(
            persona="analyst",
            has_user_identity=False,
            requested_tool=None,
            request_confidence=None,
        ),
        subagent_policy_filter=lambda s, ctx: (
            s,
            [
                SimpleNamespace(
                    subagent_name=agent.name,
                    tool_name=agent.tool_name,
                    allowed=True,
                    reason_code="allowed",
                    reason="allowed",
                )
                for agent in s
            ],
        ),
        subagent_tools_builder=fake_build_subagent_tools,
        mcp_servers_builder=lambda s, ctx: (["mcp-a"], ["missing-obo"]),
    )

    request = ResponsesAgentRequest(input=[])
    ctx = build_runtime_auth_context(
        request=request,
        subagents=subagents,
        app_client=app_client,
        deps=deps,
    )

    assert ctx.subagent_tools == ["tool-a"]
    assert ctx.mcp_servers == ["mcp-a"]
    assert ctx.unavailable_auth == ["missing-obo"]
    assert trace_payload["auth.user_token_present"] == "false"
    assert trace_payload["mlflow.trace.session"] == "conv-1"


def test_build_runtime_auth_context_with_user_identity():
    subagents = _sample_subagents()
    app_client = object()
    trace_payload = {}

    identity_ctx = SimpleNamespace(
        has_user_identity=True,
        user_workspace_client=object(),
        app_workspace_client=object(),
    )
    obo_client = object()

    def fake_obo_client_factory(workspace_client):
        assert workspace_client is identity_ctx.user_workspace_client
        return obo_client

    def fake_build_subagent_tools(s, app, obo):
        assert s == subagents
        assert app is app_client
        assert obo is obo_client
        return ["tool-b"]

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda req: None,
        trace_metadata_updater=lambda metadata: trace_payload.update(metadata),
        policy_context_builder=lambda request, identity: SimpleNamespace(
            persona="analyst",
            has_user_identity=True,
            requested_tool=None,
            request_confidence=None,
        ),
        subagent_policy_filter=lambda s, ctx: (
            s,
            [
                SimpleNamespace(
                    subagent_name=agent.name,
                    tool_name=agent.tool_name,
                    allowed=True,
                    reason_code="allowed",
                    reason="allowed",
                )
                for agent in s
            ],
        ),
        obo_client_factory=fake_obo_client_factory,
        subagent_tools_builder=fake_build_subagent_tools,
        mcp_servers_builder=lambda s, ctx: (["mcp-b"], []),
    )

    request = ResponsesAgentRequest(input=[])
    ctx = build_runtime_auth_context(
        request=request,
        subagents=subagents,
        app_client=app_client,
        deps=deps,
    )

    assert ctx.subagent_tools == ["tool-b"]
    assert ctx.mcp_servers == ["mcp-b"]
    assert ctx.unavailable_auth == []
    assert trace_payload["auth.user_token_present"] == "true"


def test_build_runtime_auth_context_applies_policy_filter_denials():
    subagents = _sample_subagents()
    app_client = object()

    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )

    def fake_policy_filter(s, ctx):
        assert ctx.persona == "manager"
        return (
            [s[1]],
            [
                SimpleNamespace(
                    subagent_name="sales_insights_agent",
                    tool_name="query_sales_agent",
                    allowed=False,
                    reason_code="persona_not_allowed",
                    reason="sales_insights_agent denied by policy (persona 'manager' is not allowed)",
                ),
                SimpleNamespace(
                    subagent_name="knowledge_assistant",
                    tool_name="query_knowledge_assistant",
                    allowed=True,
                    reason_code="allowed",
                    reason="knowledge_assistant allowed",
                ),
            ],
        )

    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        policy_context_builder=lambda request, identity: SimpleNamespace(
            persona="manager",
            has_user_identity=False,
            requested_tool=None,
            request_confidence=None,
        ),
        subagent_policy_filter=fake_policy_filter,
        subagent_tools_builder=lambda s, app, obo: ["tool-managed"] if len(s) == 1 else [],
        mcp_servers_builder=lambda s, ctx: ([], []),
    )

    request = ResponsesAgentRequest(input=[])
    ctx = build_runtime_auth_context(
        request=request,
        subagents=subagents,
        app_client=app_client,
        deps=deps,
    )

    assert ctx.subagent_tools == ["tool-managed"]
    assert ctx.unavailable_auth == ["sales_insights_agent denied by policy (persona 'manager' is not allowed)"]


def test_runtime_auth_exposes_native_handoff_for_approved_lakebase_target():
    lakebase = SubagentConfig(
        name="lakebase_ods_agent",
        kind="lakebase",
        auth_mode="app",
        project_id="ore",
        branch_id="production",
        database="operationaldatastore",
        pg_host="lakebase.example.com",
        endpoint_id="primary",
        description="appointments",
        accepts_delegations_from=("orchestrator",),
        allowed_task_intents=("appointment_summary",),
    )
    identity_ctx = SimpleNamespace(
        has_user_identity=False,
        user_workspace_client=None,
        app_workspace_client=object(),
    )
    allowed_decision = SimpleNamespace(
        subagent_name=lakebase.name,
        tool_name=lakebase.tool_name,
        allowed=True,
        reason_code="allowed",
        reason="allowed",
    )
    deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: identity_ctx,
        session_id_provider=lambda request: "delegation-test",
        trace_metadata_updater=lambda metadata: None,
        policy_context_builder=lambda request, identity: SimpleNamespace(
            persona="manager",
            has_user_identity=False,
            requested_tool=None,
            request_confidence=None,
        ),
        subagent_policy_filter=lambda subagents, context: ([lakebase], [allowed_decision]),
        subagent_tools_builder=lambda subagents, app_client, obo_client: [],
        lakebase_tools_builder=lambda subagents, context: ["lakebase-tool"],
        mcp_servers_builder=lambda subagents, context: ([], []),
        delegation_task_bus=InMemoryAgentTaskBus(),
    )

    ctx = build_runtime_auth_context(
        request=ResponsesAgentRequest(input=[]),
        subagents=[lakebase],
        app_client=object(),
        deps=deps,
    )

    assert "lakebase-tool" in ctx.subagent_tools
    assert any(getattr(tool, "name", "") == "delegate_to_agent" for tool in ctx.subagent_tools)
