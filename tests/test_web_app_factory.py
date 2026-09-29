"""Composition tests for independent web application instances."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from aiserver.api.server import create_app


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


def _app(tmp_path, name: str):
    ui_dist = tmp_path / name
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text(f"<html>{name}</html>")
    lifecycle = RecordingLifecycle()
    container = SimpleNamespace(name=name)
    runtime = SimpleNamespace(name=name)
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
