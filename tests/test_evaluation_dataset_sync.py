"""Keep evaluate_agent.py's test_cases in sync with the loaded subagent config.

If a test case's `expected_tool_calls`/`restricted_tools` reference a subagent
name that doesn't exist, or a persona that isn't allowed to use that subagent,
the corresponding expectation can never be satisfied under current policy —
`ToolCallCorrectness` (or the restriction check) will fail for reasons that
have nothing to do with routing/model quality.
"""

from backend.domain.subagent_config import SUBAGENTS
from backend.evaluate_agent import test_cases

_SUBAGENTS_BY_NAME = {subagent.name: subagent for subagent in SUBAGENTS}


def _persona(test_case: dict) -> str | None:
    custom_inputs = test_case.get("custom_inputs") or {}
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
