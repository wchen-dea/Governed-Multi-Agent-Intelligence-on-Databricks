"""Keep evaluate_agent.py's test_cases in sync with the loaded subagent config.

If a test case's `expected_tool_calls`/`restricted_tools` reference a subagent
name that doesn't exist, or a persona that isn't allowed to use that subagent,
the corresponding expectation can never be satisfied under current policy —
`ToolCallCorrectness` (or the restriction check) will fail for reasons that
have nothing to do with routing/model quality.
"""

from aiserver.domain.subagent_config import SUBAGENTS
from aiserver.evaluate_agent import test_cases

_SUBAGENTS_BY_NAME = {subagent.name: subagent for subagent in SUBAGENTS}
_SIMULATOR_KEYS = {"context", "goal", "simulation_guidelines", "persona", "expectations"}


def _persona(test_case: dict) -> str | None:
    context = test_case.get("context") or {}
    custom_inputs = context.get("custom_inputs") or {}
    return custom_inputs.get("persona")


def test_expected_tool_calls_reference_existing_subagents():
    unknown: list[str] = []
    for test_case in test_cases:
        for expected in test_case.get("expectations", {}).get("expected_tool_calls", []):
            name = expected.get("name")
            if name and name not in _SUBAGENTS_BY_NAME:
                unknown.append(f"{test_case['goal']!r} -> {name!r}")
    assert not unknown, f"expected_tool_calls reference unknown subagents: {unknown}"


def test_expected_tool_calls_persona_is_allowed_for_the_subagent():
    """A test case's persona must be authorized for its expected tool.

    Otherwise the tool is policy-denied before routing ever runs, and the
    test case can never pass regardless of model/routing quality.
    """
    mismatches: list[str] = []
    for test_case in test_cases:
        persona = _persona(test_case)
        if not persona:
            continue
        for expected in test_case.get("expectations", {}).get("expected_tool_calls", []):
            name = expected.get("name")
            subagent = _SUBAGENTS_BY_NAME.get(name)
            if subagent is None:
                continue
            if subagent.allowed_personas and persona not in subagent.allowed_personas:
                mismatches.append(
                    f"{test_case['goal']!r}: persona {persona!r} not in "
                    f"{name!r}.allowed_personas={subagent.allowed_personas}"
                )
    assert not mismatches, f"expected_tool_calls persona/policy mismatches: {mismatches}"


def test_restricted_tools_reference_existing_subagents():
    unknown: list[str] = []
    for test_case in test_cases:
        for name in test_case.get("expectations", {}).get("restricted_tools", []):
            if name not in _SUBAGENTS_BY_NAME:
                unknown.append(f"{test_case['goal']!r} -> {name!r}")
    assert not unknown, f"restricted_tools reference unknown subagents: {unknown}"


def test_cases_have_unique_goals_and_required_fields():
    goals = [test_case.get("goal") for test_case in test_cases]
    assert all(isinstance(goal, str) and goal.strip() for goal in goals)
    assert len(goals) == len(set(goals)), "evaluation test-case goals must be unique"

    for test_case in test_cases:
        assert set(test_case) <= _SIMULATOR_KEYS
        assert isinstance(test_case.get("persona"), str) and test_case["persona"].strip()
        context = test_case.get("context")
        assert isinstance(context, dict)
        custom_inputs = context.get("custom_inputs")
        assert isinstance(custom_inputs, dict)
        assert isinstance(custom_inputs.get("persona"), str)
        expectations = test_case.get("expectations")
        assert isinstance(expectations, dict)
        expected_tool_calls = expectations.get("expected_tool_calls")
        assert isinstance(expected_tool_calls, list)
        assert all(
            isinstance(expected, dict)
            and isinstance(expected.get("name"), str)
            and expected["name"].strip()
            for expected in expected_tool_calls
        )
        restricted_tools = expectations.get("restricted_tools", [])
        assert isinstance(restricted_tools, list)
        assert all(isinstance(name, str) and name.strip() for name in restricted_tools)


def test_tool_use_expectations_are_consistent():
    contradictions: list[str] = []
    for test_case in test_cases:
        expectations = test_case["expectations"]
        expected_names = {expected["name"] for expected in expectations["expected_tool_calls"]}
        restricted_names = set(expectations.get("restricted_tools", []))
        if expected_names & restricted_names:
            contradictions.append(test_case["goal"])
        if expectations.get("requires_tool_attempt") and not expected_names:
            contradictions.append(f"{test_case['goal']!r}: tool attempt has no expected tool")
        if expectations.get("freshness_sla") and not expectations.get("requires_evidence"):
            contradictions.append(f"{test_case['goal']!r}: freshness without evidence")
    assert not contradictions, f"contradictory evaluation expectations: {contradictions}"
