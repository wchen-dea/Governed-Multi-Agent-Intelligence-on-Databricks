"""Regression test for the SPA fallback path-traversal fix in aiserver.api.server."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from aiserver.api import server


class StubLifecycle:
    async def start(self):
        return None

    async def stop(self):
        return None

    def close(self):
        return None


def _create_app(ui_dist):
    return server.create_app(
        container=SimpleNamespace(),
        approval_service=object(),
        runtime=object(),
        lifecycle=StubLifecycle(),
        ui_dist_dir=ui_dist,
    )


def test_spa_fallback_rejects_path_traversal_outside_ui_dist(tmp_path):
    ui_dist = tmp_path / "ui-dist"
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text("<html>spa-index</html>")

    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-content")

    client = TestClient(_create_app(ui_dist))
    response = client.get("/../secret.txt")

    assert "top-secret-content" not in response.text
    assert response.status_code == 200
    assert response.text == "<html>spa-index</html>"


def test_spa_fallback_serves_existing_file_within_ui_dist(tmp_path):
    ui_dist = tmp_path / "ui-dist"
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text("<html>spa-index</html>")
    (ui_dist / "favicon.ico").write_bytes(b"icon-bytes")

    client = TestClient(_create_app(ui_dist))
    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.content == b"icon-bytes"
