from fastapi.testclient import TestClient

from aiserver.api.server import app
from aiserver.contracts.responses import (
    ApprovalDecisionRequest,
    ApprovalDecisionRecord,
    ResponseEnvelope,
    RoutePlan,
)
from operations.evaluate_agent import direct_groundedness_score


def test_response_envelope_is_typed_and_serializable():
    envelope = ResponseEnvelope(
        status="truncated",
        answer_chars=100,
        truncated=True,
        route_plan=RoutePlan(candidates=("sales",), reason="capability_match"),
    )

    assert envelope.status == "truncated"
    assert envelope.route_plan.candidates == ("sales",)
    assert envelope.__dict__["truncated"] is True


def test_explicit_approval_decision_contract_round_trip():
    approval = ApprovalDecisionRequest(
        request_id="req-123",
        agent_name="store_intervention_agent",
        store_id="store-123",
        approver="sam.manager",
        decision="approved",
        reason="Revenue remains strong and the CDI decline is within trend guardrails.",
        notes="Escalate to district manager for a 2-week service review.",
    )

    payload = approval.to_payload()
    assert payload["decision"] == "approved"
    assert payload["request_id"] == "req-123"

    with TestClient(app) as client:
        response = client.post("/approval-decisions", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["approval"]["decision"] == "approved"
    assert body["approval"]["approver"] == "sam.manager"

    record = ApprovalDecisionRecord.from_payload(body["approval"])
    assert record.decision == "approved"
    assert record.status == "approved"


def test_direct_groundedness_requires_freshness_metadata():
    assert (
        direct_groundedness_score(
            "Revenue is 100. Source: sales (freshness 15m).",
            requires_evidence=True,
            freshness_sla="15m",
        )
        == 1.0
    )
    assert (
        direct_groundedness_score(
            "Revenue is 100. Source: sales.",
            requires_evidence=True,
            freshness_sla="15m",
        )
        == 0.5
    )
