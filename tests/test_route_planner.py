from backend.domain.subagent_config import SubagentConfig
from backend.services.route_planner import build_route_plan


def test_route_planner_selects_best_capability_match():
    subagents = [
        SubagentConfig(name="sales", kind="app", endpoint="sales", description="revenue store analytics"),
        SubagentConfig(name="docs", kind="app", endpoint="docs", description="product documentation"),
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