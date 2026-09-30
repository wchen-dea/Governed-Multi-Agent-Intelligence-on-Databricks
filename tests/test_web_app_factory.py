"""Composition tests for independent web application instances."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from aiserver.api.server import create_app
from aiserver.contracts.public_api import ChatRequest
from aiserver.infrastructure.runtime.request_identity import (
    get_forwarded_access_token,
)


class RecordingLifecycle:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.closed = 0

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

    def close(self) -> None:
        self.closed += 1


class RecordingRuntime:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []
        self.forwarded_tokens: list[str | None] = []

    async def invoke(self, payload: ChatRequest) -> dict[str, str]:
        self.requests.append(payload)
        self.forwarded_tokens.append(get_forwarded_access_token())
        return {"type": "completed"}

    async def stream(self, payload: ChatRequest):
        self.requests.append(payload)
        self.forwarded_tokens.append(get_forwarded_access_token())
        yield {"type": "completed"}


def _app(tmp_path, name: str, runtime: object | None = None):
    ui_dist = tmp_path / name
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text(f"<html>{name}</html>")
    lifecycle = RecordingLifecycle()
    container = SimpleNamespace(name=name)
    runtime = runtime or SimpleNamespace(name=name)
    approval_service = SimpleNamespace(name=name)
    app = create_app(
        container=container,
        approval_service=approval_service,
        runtime=runtime,
        lifecycle=lifecycle,
        ui_dist_dir=ui_dist,
    )
    return app, lifecycle, container, runtime, approval_service


def test_factory_keeps_application_state_and_ui_instances_isolated(tmp_path):
    first = _app(tmp_path, "first")
    second = _app(tmp_path, "second")

    with TestClient(first[0]) as first_client, TestClient(second[0]) as second_client:
        assert first_client.get("/").text == "<html>first</html>"
        assert second_client.get("/").text == "<html>second</html>"
        assert first[0].state.container is first[2]
        assert second[0].state.container is second[2]
        assert first[0].state.runtime is first[3]
        assert second[0].state.approval_service is second[4]

    assert (first[1].started, first[1].stopped, first[1].closed) == (1, 1, 1)
    assert (second[1].started, second[1].stopped, second[1].closed) == (1, 1, 1)


def test_factory_request_id_middleware_preserves_or_generates_id(tmp_path):
    app, *_ = _app(tmp_path, "request-id")

    with TestClient(app) as client:
        supplied = client.get("/health", headers={"X-Request-ID": "request-123"})
        generated = client.get("/health")

    assert supplied.headers["X-Request-ID"] == "request-123"
    assert generated.headers["X-Request-ID"]
    assert generated.headers["X-Request-ID"] != "request-123"


def test_public_chat_accepts_browser_message_contract(tmp_path):
    runtime = RecordingRuntime()
    app, *_ = _app(tmp_path, "public-chat", runtime=runtime)
    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Using the latest available season, which stores had the highest "
                    "total net_sales in the last 30 days? Include Store Code and total "
                    "net sales."
                ),
            }
        ],
        "conversation_id": "store-manager-regression",
        "persona": "store-manager",
        "stream": False,
    }

    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    assert response.json() == {"type": "completed"}
    assert len(runtime.requests) == 1
    assert runtime.requests[0].model_dump() == payload


def test_public_chat_preserves_forwarded_token_during_stream(tmp_path):
    runtime = RecordingRuntime()
    app, *_ = _app(tmp_path, "public-chat-token", runtime=runtime)
    payload = {
        "messages": [{"role": "user", "content": "Compare appointments and sales."}],
        "conversation_id": "executive-regression",
        "persona": "executive",
        "stream": True,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json=payload,
            headers={"x-forwarded-access-token": "user-token"},
        )

    assert response.status_code == 200
    assert runtime.forwarded_tokens == ["user-token"]
