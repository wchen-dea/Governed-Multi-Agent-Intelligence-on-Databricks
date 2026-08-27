"""Regression test for the SPA fallback path-traversal fix in aiserver.api.server."""

from fastapi.testclient import TestClient

from aiserver.api import server


def test_spa_fallback_rejects_path_traversal_outside_ui_dist(tmp_path, monkeypatch):
    ui_dist = tmp_path / "ui-dist"
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text("<html>spa-index</html>")

    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-content")

    monkeypatch.setattr(server, "UI_DIST_DIR", ui_dist)

    client = TestClient(server.app)
    response = client.get("/../secret.txt")

    assert "top-secret-content" not in response.text
    assert response.status_code == 200
    assert response.text == "<html>spa-index</html>"


def test_spa_fallback_serves_existing_file_within_ui_dist(tmp_path, monkeypatch):
    ui_dist = tmp_path / "ui-dist"
    ui_dist.mkdir()
    (ui_dist / "index.html").write_text("<html>spa-index</html>")
    (ui_dist / "favicon.ico").write_bytes(b"icon-bytes")

    monkeypatch.setattr(server, "UI_DIST_DIR", ui_dist)

    client = TestClient(server.app)
    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.content == b"icon-bytes"
