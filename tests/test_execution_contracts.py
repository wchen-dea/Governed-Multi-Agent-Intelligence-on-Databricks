from fastapi.testclient import TestClient

from aiserver.api.server import app
from aiserver.contracts.responses import (
    ApprovalDecisionRecord,
    ApprovalDecisionRequest,
    OpenAIAgentRunMetadata,
    ResponseEnvelope,
    RoutePlan,
)
from operations.evaluate_agent import (
    direct_groundedness_score,
    eval_judge_model,
    eval_simulator_user_model,
)


def test_response_envelope_is_typed_and_serializable():
    envelope = ResponseEnvelope(
        status="truncated",
        answer_chars=100,
        truncated=True,
        route_plan=RoutePlan(candidates=("sales",), reason="capability_match"),
        openai_run=OpenAIAgentRunMetadata(
            run_id="run-123",
            model="databricks-gpt-5-6-luna",
            model_task_type="reasoning",
            model_reason="task_type_match",
            model_rationale="Use stronger reasoning for quality.",
            candidate_subagents=("sales",),
            selected_tool_names=("Genie:sales",),
            unavailable_tool_details=("Genie:cdi unavailable",),
            ai_gateway_enabled=True,
        ),
    )

    assert envelope.status == "truncated"
    assert envelope.route_plan.candidates == ("sales",)
    assert envelope.__dict__["truncated"] is True
    assert envelope.openai_run.api == "responses"
    assert envelope.openai_run.run_id == "run-123"
    assert "quality" in envelope.openai_run.model_rationale
    assert envelope.openai_run.selected_tool_names == ("Genie:sales",)


def test_explicit_approval_decision_contract_round_trip():
    approval = ApprovalDecisionRequest(
        request_id="req-123",
        agent_name="store-intervention-agent",
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
    assert body["delegation"]["correlation_id"] == "req-123"
    assert body["delegation"]["target_agent"] == "store-intervention-agent"
    assert body["delegation"]["intent"] == "store_intervention_planning"
    assert body["delegation"]["status"] == "pending"

    record = ApprovalDecisionRecord.from_payload(body["approval"])
    assert record.decision == "approved"
    assert record.status == "approved"


def test_rejected_approval_does_not_create_delegation_task():
    approval = ApprovalDecisionRequest(
        request_id="req-rejected-123",
        agent_name="store-intervention-agent",
        approver="sam.manager",
        decision="rejected",
        reason="Insufficient evidence for intervention.",
    )

    with TestClient(app) as client:
        response = client.post("/approval-decisions", json=approval.to_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["approval"]["decision"] == "rejected"
    assert body["delegation"] is None


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


def test_eval_judge_and_simulator_models_are_configurable(monkeypatch):
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "databricks:/judge-model")
    monkeypatch.delenv("EVAL_SIMULATOR_USER_MODEL", raising=False)

    assert eval_judge_model() == "databricks:/judge-model"
    assert eval_simulator_user_model() == "databricks:/judge-model"

    monkeypatch.setenv("EVAL_SIMULATOR_USER_MODEL", "databricks:/user-model")

    assert eval_simulator_user_model() == "databricks:/user-model"
