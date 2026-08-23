from backend.domain.execution_contracts import ResponseEnvelope, RoutePlan
from backend.evaluate_agent import direct_groundedness_score


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


def test_direct_groundedness_requires_freshness_metadata():
    assert direct_groundedness_score(
        "Revenue is 100. Source: sales (freshness 15m).",
        requires_evidence=True,
        freshness_sla="15m",
    ) == 1.0
    assert direct_groundedness_score(
        "Revenue is 100. Source: sales.",
        requires_evidence=True,
        freshness_sla="15m",
    ) == 0.5