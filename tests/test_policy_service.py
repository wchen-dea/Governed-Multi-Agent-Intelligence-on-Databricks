from types import SimpleNamespace

from mlflow.types.responses import ResponsesAgentRequest

from backend.domain.subagent_config import SubagentConfig
from backend.services.policy_service import build_policy_context, filter_subagents_by_policy
from backend.shared.settings import get_settings


def _subagents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="public_docs",
            kind="serving_endpoint",
            description="docs",
            endpoint="docs",
            auth_mode="app",
            data_classification="public",
            allowed_personas=("analyst", "engineer"),
        ),
        SubagentConfig(
            name="sales_confidential",
            kind="genie",
            description="sales",
            space_id="space-1",
            auth_mode="obo",
            data_classification="confidential",
            allowed_personas=("analyst",),
        ),
    ]


def test_build_policy_context_reads_persona():
    request = ResponsesAgentRequest(
        input=[],
        custom_inputs={"persona": "Analyst", "tool": "query_public_docs", "confidence": 0.9},
    )
    identity_ctx = SimpleNamespace(has_user_identity=True)

    ctx = build_policy_context(request, identity_ctx)

    assert ctx.persona == "analyst"
    assert ctx.has_user_identity is True
    assert ctx.requested_tool == "query_public_docs"
    assert ctx.request_confidence == 0.9


def test_build_policy_context_uses_default_persona(monkeypatch):
    monkeypatch.setenv("DEFAULT_REQUEST_PERSONA", "manager")
    get_settings.cache_clear()
    request = ResponsesAgentRequest(input=[])
    identity_ctx = SimpleNamespace(has_user_identity=True)

    ctx = build_policy_context(request, identity_ctx)

    assert ctx.persona == "manager"


def test_filter_subagents_by_policy_blocks_disallowed_persona():
    subagents = _subagents()
    ctx = SimpleNamespace(
        persona="manager",
        has_user_identity=True,
        requested_tool=None,
        request_confidence=None,
    )

    allowed, decisions = filter_subagents_by_policy(subagents, ctx)

    assert allowed == []
    assert len([d for d in decisions if not d.allowed]) == 2


def test_filter_subagents_by_policy_blocks_confidential_obo_without_identity():
    subagents = _subagents()
    ctx = SimpleNamespace(
        persona="analyst",
        has_user_identity=False,
        requested_tool=None,
        request_confidence=None,
    )

    allowed, decisions = filter_subagents_by_policy(subagents, ctx)
    denied = [d.reason for d in decisions if not d.allowed]

    assert len(allowed) == 1
    assert allowed[0].name == "public_docs"
    assert any("OBO identity is required" in reason for reason in denied)


def test_filter_subagents_by_policy_blocks_sensitive_on_low_confidence():
    subagents = _subagents()
    ctx = SimpleNamespace(
        persona="analyst",
        has_user_identity=True,
        requested_tool="query_sales_confidential",
        request_confidence=0.6,
    )

    allowed, decisions = filter_subagents_by_policy(subagents, ctx)

    assert allowed == []
    assert any(d.reason_code == "low_confidence_sensitive" for d in decisions)
