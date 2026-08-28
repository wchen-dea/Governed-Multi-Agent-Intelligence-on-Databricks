from aiserver.application.orchestration.routing import build_route_plan
from aiserver.contracts.subagents import SubagentConfig


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
    )
    assert first_plan.reason == "capability_match"
    assert first_plan.candidates == ("flink_support_agent",)

    followup_plan, followup_selected = build_route_plan(
        "any recommendations on tuning",
        subagents,
        conversation_id="conv-sticky-1",
    )

    assert followup_plan.reason == "sticky_route"
    assert followup_plan.candidates == ("flink_support_agent",)
    assert [subagent.name for subagent in followup_selected] == ["flink_support_agent"]


def test_route_planner_sticky_route_ignored_when_subagent_no_longer_allowed():
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
    )

    followup_plan, followup_selected = build_route_plan(
        "any recommendations on tuning",
        [subagents[1]],
        conversation_id="conv-sticky-2",
    )

    assert followup_plan.reason == "ambiguous_fallback"
    assert followup_selected == [subagents[1]]


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
