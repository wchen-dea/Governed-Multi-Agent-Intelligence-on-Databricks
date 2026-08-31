"""Regression coverage for Pydantic validation at external boundaries."""

import pytest
from pydantic import ValidationError

from aiserver.api.models import ApprovalDecisionInput
from aiserver.config.settings import get_settings


def test_settings_reads_existing_environment_variable_aliases(monkeypatch):
    monkeypatch.setenv("DATABRICKS_OPENAI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("KAFKA_CLIENT_ID", "audit-client")
    monkeypatch.setenv("MCP_SESSION_TIMEOUT_SECONDS", "60")
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.openai_timeout_seconds == 12.5
        assert settings.message_bus_kafka_client_id == "audit-client"
        assert settings.mcp_session_timeout_seconds == 60.0
    finally:
        get_settings.cache_clear()


def test_settings_uses_orchestrator_model_as_default_route_fallback(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_MODEL", "custom-orchestrator")
    monkeypatch.delenv("MODEL_ROUTING_DEFAULT_MODEL", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings.orchestrator_model == "custom-orchestrator"
        assert settings.model_routing_default_model == "custom-orchestrator"
    finally:
        get_settings.cache_clear()


def test_settings_rejects_invalid_positive_timeout(monkeypatch):
    monkeypatch.setenv("MCP_SESSION_TIMEOUT_SECONDS", "0")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError, match="mcp_session_timeout_seconds"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_settings_reads_stream_execution_timeout(monkeypatch):
    monkeypatch.setenv("STREAM_EXECUTION_TIMEOUT_SECONDS", "180")
    get_settings.cache_clear()

    try:
        assert get_settings().stream_execution_timeout_seconds == 180.0
    finally:
        get_settings.cache_clear()


def test_approval_decision_input_rejects_invalid_or_unknown_values():
    with pytest.raises(ValidationError):
        ApprovalDecisionInput(request_id="", agent_name="store-intervention-agent")

    with pytest.raises(ValidationError):
        ApprovalDecisionInput(
            request_id="request-1",
            agent_name="store-intervention-agent",
            decision="dispatch",
        )

    with pytest.raises(ValidationError):
        ApprovalDecisionInput(
            request_id="request-1",
            agent_name="store-intervention-agent",
            unrecognized_field=True,
        )


def test_approval_decision_input_trims_required_fields():
    payload = ApprovalDecisionInput(
        request_id=" request-1 ",
        agent_name=" store-intervention-agent ",
    )

    assert payload.request_id == "request-1"
    assert payload.agent_name == "store-intervention-agent"