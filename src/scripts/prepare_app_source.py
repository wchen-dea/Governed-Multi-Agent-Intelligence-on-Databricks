#!/usr/bin/env python3
"""Build a wheel and prepare a minimal Databricks app source directory."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
APP_SOURCE_DIR = REPO_ROOT / ".databricks_app_source"
WHEELS_DIR = APP_SOURCE_DIR / "wheels"
REACT_UI_DIR = REPO_ROOT / "src" / "aiweb"
REACT_DIST_DIR = REACT_UI_DIR / "dist"
APP_REACT_DIST_DIR = APP_SOURCE_DIR / "aiweb-dist"


def _log(message: str) -> None:
    print(f"[prepare-app-source] {message}")


def _run(command: list[str], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> None:
    _log(f"Running: {' '.join(command)} (cwd={cwd})")
    subprocess.check_call(command, cwd=cwd, env=env)


def _latest_wheel() -> Path:
    wheels = sorted(DIST_DIR.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        raise FileNotFoundError("No wheel artifacts found in dist/.")
    return wheels[0]


def _prepare_react_assets() -> None:
    if not REACT_UI_DIR.exists():
        raise FileNotFoundError(f"React UI directory not found: {REACT_UI_DIR}")

    package_lock = REACT_UI_DIR / "package-lock.json"
    build_env = os.environ.copy()
    # Use same-origin backend proxy endpoint served by the React UI server.
    build_env.setdefault("VITE_API_PROXY", "/invocations")

    if package_lock.exists():
        _run(["npm", "ci"], cwd=REACT_UI_DIR, env=build_env)
    else:
        _run(["npm", "install"], cwd=REACT_UI_DIR, env=build_env)

    _run(["npm", "run", "build"], cwd=REACT_UI_DIR, env=build_env)

    if not REACT_DIST_DIR.exists():
        raise FileNotFoundError(f"React UI build output not found: {REACT_DIST_DIR}")

    if APP_REACT_DIST_DIR.exists():
        shutil.rmtree(APP_REACT_DIST_DIR)
    shutil.copytree(REACT_DIST_DIR, APP_REACT_DIST_DIR)


def main() -> int:
    APP_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    WHEELS_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"Preparing app source in {APP_SOURCE_DIR}")

    # Build a fresh wheel artifact for this revision.
    _run(["uv", "build", "--wheel"])

    # Keep only one wheel in the deploy payload to minimize source size.
    removed_wheels = 0
    for old_wheel in WHEELS_DIR.glob("*.whl"):
        old_wheel.unlink()
        removed_wheels += 1
    if removed_wheels:
        _log(f"Removed {removed_wheels} existing wheel artifact(s) from payload")

    latest = _latest_wheel()
    destination = WHEELS_DIR / latest.name
    shutil.copy2(latest, destination)
    _log(f"Copied wheel artifact: {latest.name}")

    # Build and package React UI assets for Databricks App static hosting.
    _prepare_react_assets()

    print(f"Prepared Databricks app source at: {APP_SOURCE_DIR}")
    print(f"Wheel included: {destination.name}")
    print(f"React UI assets included: {APP_REACT_DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
