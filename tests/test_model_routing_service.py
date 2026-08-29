"""Tests for deterministic request model selection."""

from aiserver.application.orchestration.model import select_model
from aiserver.config.settings import AppSettings


def _settings(**overrides: object) -> AppSettings:
    values = AppSettings().__dict__.copy()
    values.update(overrides)
    return AppSettings(**values)


def test_standard_product_lookup_uses_default_model():
    selection = select_model("Look up product details for brand code MICH", _settings())

    assert selection.task_type == "standard"
    assert selection.model == "databricks-gpt-5-6-luna"
    assert "cost" in selection.rationale


def test_operational_query_uses_reasoning_model():
    selection = select_model("List open appointments and current order status", _settings())

    assert selection.task_type == "reasoning"
    assert selection.model == "databricks-claude-sonnet-5"
    assert "reliability" in selection.rationale


def test_analysis_request_uses_quality_model():
    selection = select_model("Create an executive analysis and recommendation", _settings())

    assert selection.task_type == "synthesis"
    assert selection.model == "databricks-claude-sonnet-5"
    assert "quality" in selection.rationale


def test_mixed_recommendation_and_operational_terms_prioritize_synthesis():
    selection = select_model(
        "Analyze appointment trends and recommend a store intervention plan",
        _settings(),
    )

    assert selection.task_type == "synthesis"
    assert selection.reason == "matched_analysis_or_synthesis_terms"


def test_diagnose_incident_request_uses_reasoning_model():
    selection = select_model("Diagnose this streaming performance incident", _settings())

    assert selection.task_type == "reasoning"
    assert selection.reason == "matched_operational_or_support_terms"


def test_disabled_model_routing_keeps_orchestrator_model():
    selection = select_model(
        "Debug a Flink streaming lag incident",
        _settings(model_routing_enabled=False, orchestrator_model="configured-model"),
    )

    assert selection.task_type == "default"
    assert selection.model == "configured-model"
    assert "disabled" in selection.rationale
