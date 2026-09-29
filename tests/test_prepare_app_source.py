from pathlib import Path

from operations import prepare_app_source


def test_prepare_react_assets_targets_public_chat_api(tmp_path, monkeypatch):
    react_ui_dir = tmp_path / "aiweb"
    react_dist_dir = react_ui_dir / "dist"
    packaged_ui_dir = tmp_path / "static"
    react_ui_dir.mkdir()
    (react_ui_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    observed_endpoints: list[str | None] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path = prepare_app_source.REPO_ROOT,
        env: dict[str, str] | None = None,
    ) -> None:
        observed_endpoints.append(env.get("VITE_API_PROXY") if env else None)
        if command == ["npm", "run", "build"]:
            react_dist_dir.mkdir()
            (react_dist_dir / "index.html").write_text("built", encoding="utf-8")

    monkeypatch.delenv("VITE_API_PROXY", raising=False)
    monkeypatch.setattr(prepare_app_source, "REACT_UI_DIR", react_ui_dir)
    monkeypatch.setattr(prepare_app_source, "REACT_DIST_DIR", react_dist_dir)
    monkeypatch.setattr(prepare_app_source, "PACKAGED_UI_DIR", packaged_ui_dir)
    monkeypatch.setattr(prepare_app_source, "_run", fake_run)

    prepare_app_source._prepare_react_assets()

    assert observed_endpoints == ["/api/chat", "/api/chat"]
    assert (packaged_ui_dir / "index.html").read_text(encoding="utf-8") == "built"
