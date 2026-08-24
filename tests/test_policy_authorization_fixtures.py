import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.domain.subagent_config import SubagentConfig
from backend.services.policy_service import filter_subagents_by_policy


def _subagents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="public_docs",
            kind="serving_endpoint",
            endpoint="docs",
            description="docs",
            auth_mode="app",
            data_classification="public",
            allowed_personas=("analyst", "engineer"),
        ),
        SubagentConfig(
            name="sales_confidential",
            kind="genie",
            space_id="space-1",
            description="sales",
            auth_mode="obo",
            data_classification="confidential",
            allowed_personas=("analyst",),
        ),
    ]


CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "policy_authorization_cases.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_policy_authorization_fixture(case):
    context = SimpleNamespace(
        persona=case["persona"],
        has_user_identity=case["has_user_identity"],
        requested_tool=case.get("requested_tool"),
        request_confidence=case["confidence"],
    )

    allowed, decisions = filter_subagents_by_policy(_subagents(), context)

    assert [subagent.name for subagent in allowed] == case["expected_allowed"]
    denied_reasons = {decision.reason_code for decision in decisions if not decision.allowed}
    assert set(case["expected_denied_reasons"]).issubset(denied_reasons)