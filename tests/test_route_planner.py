from datetime import UTC, datetime, timedelta

from aiserver.application.orchestration.routing import build_route_plan
from aiserver.contracts.execution import RouteAffinity
from aiserver.contracts.subagents import SubagentConfig
from aiserver.infrastructure.persistence.routing import InMemoryRouteAffinityStore


def test_route_planner_selects_best_capability_match():
    subagents = [
        SubagentConfig(
            name="sales", kind="app", endpoint="sales", description="revenue store analytics"
        ),
        SubagentConfig(
            name="docs", kind="app", endpoint="docs", description="product documentation"
        ),
    ]

    plan, selected = build_route_plan("revenue by store", subagents)

    assert plan.reason == "capability_match"
    assert plan.candidates == ("sales",)
    assert selected == [subagents[0]]


def test_route_planner_falls_back_when_no_capability_matches():
    subagents = [SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue")]

    plan, selected = build_route_plan("hello", subagents)

    assert plan.reason == "ambiguous_fallback"
    assert selected == subagents


def test_route_planner_prefers_discriminative_product_terms():
    subagents = [
        SubagentConfig(
            name="sales", kind="app", endpoint="sales", description="revenue and store analytics"
        ),
        SubagentConfig(
            name="product_index",
            kind="mcp",
            mcp_url="/product",
            description="product catalog lookups by brand code and article type",
        ),
        SubagentConfig(
            name="lakebase",
            kind="app",
            endpoint="lakebase",
            description="appointments and orders operational data",
        ),
    ]

    plan, selected = build_route_plan("products matching brand code MCH", subagents)

    assert plan.reason == "capability_match"
    assert [subagent.name for subagent in selected] == ["product_index"]


def test_route_planner_uses_system_prompt_capabilities():
    subagents = [
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="analytics"),
        SubagentConfig(
            name="product_index",
            kind="mcp",
            mcp_url="/product",
            description="product knowledge",
            system_prompt="Verify exact brand_code and product_code matches.",
        ),
        SubagentConfig(
            name="lakebase", kind="app", endpoint="lakebase", description="operational data"
        ),
    ]

    _, selected = build_route_plan("products matching brand code MCH", subagents)

    assert [subagent.name for subagent in selected] == ["product_index"]


def test_route_planner_selects_lakebase_for_appointments_and_order_status():
    lakebase = SubagentConfig(
        name="lakebase_ods_agent",
        kind="lakebase",
        project_id="ore",
        branch_id="production",
        database="operations",
        pg_host="lakebase.example.com",
        endpoint_id="primary",
        description="appointments, orders, invoices, and scheduling operational data",
    )
    product = SubagentConfig(
        name="product_index",
        kind="mcp",
        mcp_url="/product",
        description="product catalog lookups",
    )

    plan, selected = build_route_plan(
        "List latest day's appointments and their current order status.",
        [product, lakebase],
    )

    assert plan.reason == "capability_match"
    assert [subagent.name for subagent in selected] == ["lakebase_ods_agent"]


def test_route_planner_ignores_plural_generic_type_term():
    product = SubagentConfig(
        name="product_index",
        kind="mcp",
        mcp_url="/product",
        description="product catalog lookups",
        system_prompt="Verify article_type and product_code.",
    )
    lakebase = SubagentConfig(
        name="lakebase",
        kind="app",
        endpoint="lakebase",
        description="operational data",
        system_prompt="Return result tables with clear column headers.",
    )

    _, selected = build_route_plan("article types for those products", [product, lakebase])

    assert [subagent.name for subagent in selected] == ["product_index"]


def test_route_planner_keeps_all_tools_for_weak_matches():
    subagents = [
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue analytics"),
        SubagentConfig(
            name="docs", kind="app", endpoint="docs", description="general documentation"
        ),
    ]

    plan, selected = build_route_plan("please help me", subagents)

    assert plan.reason == "ambiguous_fallback"
    assert selected == subagents


def test_route_planner_sticky_route_reused_for_weak_followup():
    affinity_store = InMemoryRouteAffinityStore()
    subagents = [
        SubagentConfig(
            name="flink_support_agent",
            kind="mcp",
            mcp_url="/flink",
            description="flink streaming troubleshooting and configuration support",
        ),
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue analytics"),
    ]

    first_plan, _ = build_route_plan(
        "Flink streaming job has increasing consumer lag",
        subagents,
        conversation_id="conv-sticky-1",
        affinity_store=affinity_store,
    )
    assert first_plan.reason == "capability_match"
    assert first_plan.candidates == ("flink_support_agent",)

    followup_plan, followup_selected = build_route_plan(
        "any recommendations on tuning",
        subagents,
        conversation_id="conv-sticky-1",
        affinity_store=affinity_store,
    )

    assert followup_plan.reason == "sticky_route"
    assert followup_plan.candidates == ("flink_support_agent",)
    assert [subagent.name for subagent in followup_selected] == ["flink_support_agent"]


def test_route_planner_sticky_route_ignored_when_subagent_no_longer_allowed():
    affinity_store = InMemoryRouteAffinityStore()
    subagents = [
        SubagentConfig(
            name="flink_support_agent",
            kind="mcp",
            mcp_url="/flink",
            description="flink streaming troubleshooting and configuration support",
        ),
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue analytics"),
    ]

    build_route_plan(
        "Flink streaming job has increasing consumer lag",
        subagents,
        conversation_id="conv-sticky-2",
        affinity_store=affinity_store,
    )

    followup_plan, followup_selected = build_route_plan(
        "any recommendations on tuning",
        [subagents[1]],
        conversation_id="conv-sticky-2",
        affinity_store=affinity_store,
    )

    assert followup_plan.reason == "ambiguous_fallback"
    assert followup_selected == [subagents[1]]
    assert affinity_store.get("conv-sticky-2") is None


def test_route_planner_no_sticky_route_without_conversation_id():
    subagents = [
        SubagentConfig(
            name="flink_support_agent",
            kind="mcp",
            mcp_url="/flink",
            description="flink streaming troubleshooting and configuration support",
        ),
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue analytics"),
    ]

    build_route_plan("Flink streaming job has increasing consumer lag", subagents)

    followup_plan, followup_selected = build_route_plan("any recommendations on tuning", subagents)

    assert followup_plan.reason == "ambiguous_fallback"
    assert followup_selected == subagents


def test_route_planner_shares_affinity_across_service_instances():
    affinity_store = InMemoryRouteAffinityStore()
    subagents = [
        SubagentConfig(
            name="flink_support_agent",
            kind="mcp",
            mcp_url="/flink",
            description="flink streaming troubleshooting support",
        ),
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue"),
    ]

    def first_instance(question):
        return build_route_plan(
            question,
            subagents,
            "conv-shared",
            affinity_store=affinity_store,
        )

    def second_instance(question):
        return build_route_plan(
            question,
            subagents,
            "conv-shared",
            affinity_store=affinity_store,
        )

    first_instance("Flink streaming consumer lag")
    plan, selected = second_instance("what should I tune")

    assert plan.reason == "sticky_route"
    assert [subagent.name for subagent in selected] == ["flink_support_agent"]


def test_route_planner_ignores_expired_affinity():
    affinity_store = InMemoryRouteAffinityStore()
    affinity_store.put(
        RouteAffinity(
            conversation_id="conv-expired",
            candidate_names=("sales",),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    subagents = [SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue")]

    plan, selected = build_route_plan(
        "hello",
        subagents,
        "conv-expired",
        affinity_store=affinity_store,
    )

    assert plan.reason == "ambiguous_fallback"
    assert selected == subagents
    assert affinity_store.get("conv-expired") is None


def _keyword_subagents():
    return [
        SubagentConfig(
            name="sales",
            kind="app",
            endpoint="sales",
            description="revenue analytics",
            routing_keywords=("net sales", "sales"),
            requires_evidence=False,
        ),
        SubagentConfig(
            name="cdi",
            kind="app",
            endpoint="cdi",
            description="customer delight",
            routing_keywords=("nps", "cdi"),
            requires_evidence=True,
        ),
        SubagentConfig(
            name="ods",
            kind="app",
            endpoint="ods",
            description="operational data",
            routing_keywords=("article", "appointment"),
        ),
    ]


def test_route_planner_composite_match_exposes_every_keyword_domain():
    affinity_store = InMemoryRouteAffinityStore()
    plan, selected = build_route_plan(
        "Which of the top 20 stores by net sales have NPS below average?",
        _keyword_subagents(),
        "conv-composite",
        affinity_store=affinity_store,
    )

    assert plan.reason == "composite_match"
    assert plan.candidates == ("sales", "cdi")
    assert plan.requires_evidence is True
    assert [subagent.name for subagent in selected] == ["sales", "cdi"]
    affinity = affinity_store.get("conv-composite")
    assert affinity is not None
    assert affinity.candidate_names == ("sales", "cdi")


def test_route_planner_single_keyword_match_routes_to_one_subagent():
    plan, selected = build_route_plan(
        "Compare month-to-date net sales by region", _keyword_subagents()
    )

    assert plan.reason == "keyword_match"
    assert [subagent.name for subagent in selected] == ["sales"]


def test_route_planner_keywords_match_on_word_boundaries():
    plan, _ = build_route_plan("Return the article_type for each product", _keyword_subagents())

    assert plan.reason not in {"keyword_match", "composite_match"}


def test_route_planner_composite_respects_policy_filtered_subagents():
    allowed = [subagent for subagent in _keyword_subagents() if subagent.name != "ods"]
    plan, selected = build_route_plan(
        "Top 5 stores by appointment count and their net sales rank", allowed
    )

    assert plan.reason == "keyword_match"
    assert [subagent.name for subagent in selected] == ["sales"]
