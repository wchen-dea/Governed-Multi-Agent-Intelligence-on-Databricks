#!/usr/bin/env python3
"""Build a wheel and prepare a minimal Databricks app source directory."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
APP_SOURCE_DIR = REPO_ROOT / ".databricks_app_source"
WHEELS_DIR = APP_SOURCE_DIR / "wheels"
REACT_UI_DIR = REPO_ROOT / "src" / "aiweb"
REACT_DIST_DIR = REACT_UI_DIR / "dist"
APP_REACT_DIST_DIR = APP_SOURCE_DIR / "aiweb-dist"
APP_YML_PATH = APP_SOURCE_DIR / "app.yml"
BUNDLE_FILE = REPO_ROOT / "databricks.yml"
APP_RESOURCE_FILE = REPO_ROOT / "resources" / "multiagent_app.yml"
TARGET_ENV_VARS = ("DATABRICKS_BUNDLE_TARGET", "BUNDLE_TARGET", "TARGET", "APP_ENV")

_VAR_REF_RE = re.compile(r"^\$\{var\.([a-zA-Z0-9_]+)\}$")


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


def _current_target() -> str:
    for env_var in TARGET_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return value
    return "dev"


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8")) or {}


def _resolve_bundle_variables(target: str) -> dict[str, str]:
    """Merge databricks.yml variable defaults with target-specific overrides."""
    bundle_data = _load_yaml(BUNDLE_FILE)
    defaults = {
        name: str(spec.get("default", "")) if isinstance(spec, dict) else ""
        for name, spec in (bundle_data.get("variables") or {}).items()
    }

    target_file = REPO_ROOT / "targets" / f"{target}.yml"
    if not target_file.exists():
        return defaults

    targets_data = _load_yaml(target_file)
    overrides = targets_data.get("targets", {}).get(target, {}).get("variables", {}) or {}

    resolved = dict(defaults)
    resolved.update({name: str(value) for name, value in overrides.items()})
    return resolved


def _sync_app_yml_env(target: str) -> None:
    """Regenerate app.yml's env block from resources/multiagent_app.yml + target variables.

    Keeps the checked-in app.yml aligned with target config, since SNAPSHOT
    deploys read env vars from this file instead of the bundle-applied resource env.
    """
    if not APP_YML_PATH.exists():
        _log(f"Skipping app.yml env sync; not found at {APP_YML_PATH}")
        return
    if not APP_RESOURCE_FILE.exists():
        _log(f"Skipping app.yml env sync; not found at {APP_RESOURCE_FILE}")
        return

    app_resource_data = _load_yaml(APP_RESOURCE_FILE)
    env_entries = (
        app_resource_data.get("resources", {})
        .get("apps", {})
        .get("multiagent-app", {})
        .get("config", {})
        .get("env", [])
    )
    if not env_entries:
        _log("Skipping app.yml env sync; no env entries found in resources/multiagent_app.yml")
        return

    resolved_vars = _resolve_bundle_variables(target)

    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    app_yml_data = yaml.load(APP_YML_PATH.read_text(encoding="utf-8")) or {}

    new_env: list[dict[str, str]] = []
    unresolved: set[str] = set()
    for entry in env_entries:
        name = entry.get("name")
        raw_value = entry.get("value", "")
        match = _VAR_REF_RE.match(str(raw_value))
        if match:
            var_name = match.group(1)
            if var_name not in resolved_vars:
                unresolved.add(var_name)
            value = resolved_vars.get(var_name, "")
        else:
            value = raw_value
        new_env.append({"name": name, "value": value})

    if unresolved:
        _log(f"WARNING: no bundle variable found for: {', '.join(sorted(unresolved))}")

    app_yml_data["env"] = new_env
    with APP_YML_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(app_yml_data, f)

    _log(f"Synced app.yml env block for target '{target}' ({len(new_env)} vars)")


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

    target = _current_target()
    _sync_app_yml_env(target)

    print(f"Prepared Databricks app source at: {APP_SOURCE_DIR}")
    print(f"Wheel included: {destination.name}")
    print(f"React UI assets included: {APP_REACT_DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
