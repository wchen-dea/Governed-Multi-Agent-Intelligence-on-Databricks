"""Tests for the MLflow-to-application execution adapter."""

from mlflow.types.responses import ResponsesAgentRequest

from aiserver.api import invocations


def test_execution_request_normalizes_persona_and_preserves_metadata(monkeypatch):
    monkeypatch.setattr(invocations, "get_forwarded_access_token", lambda: None)
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "  Show revenue  "}],
        custom_inputs={
            "persona": " Store-Manager ",
            "session_id": " session-1 ",
            "request_id": "request-1",
        },
    )

    result = invocations._execution_request(request)

    assert result.persona == "store-manager"
    assert result.conversation_id == "session-1"
    assert result.messages[0].content == "Show revenue"
    assert result.metadata == {
        "session_id": " session-1 ",
        "request_id": "request-1",
    }


def test_execution_request_converts_blank_persona_to_none(monkeypatch):
    monkeypatch.setattr(invocations, "get_forwarded_access_token", lambda: None)
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "Show revenue"}],
        custom_inputs={"persona": "   "},
    )

    result = invocations._execution_request(request)

    assert result.persona is None


def test_execution_request_preserves_empty_normalized_input_for_governed_rejection(
    monkeypatch,
):
    monkeypatch.setattr(invocations, "get_forwarded_access_token", lambda: None)
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "   "}],
        custom_inputs={"persona": "manager"},
    )

    result = invocations._execution_request(request)

    assert result.messages == ()


def test_execution_request_uses_context_conversation_id(monkeypatch):
    monkeypatch.setattr(invocations, "get_forwarded_access_token", lambda: "token")
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "Show revenue"}],
        context={"conversation_id": "conversation-1"},
        custom_inputs={"session_id": "session-1"},
    )

    result = invocations._execution_request(request)

    assert result.conversation_id == "conversation-1"


def test_execution_request_derives_session_from_forwarded_token(monkeypatch):
    monkeypatch.setattr(invocations, "get_forwarded_access_token", lambda: "token")
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": "Show revenue"}],
    )

    result = invocations._execution_request(request)

    assert result.conversation_id == "3c469e9d6c5875d37a43f353"
