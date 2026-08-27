#!/usr/bin/env python3
"""Install bundled wheel and launch the multiagent app."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _find_wheel() -> Path:
    source_root = Path(__file__).resolve().parent
    wheels_dir = source_root / "wheels"
    wheels = sorted(wheels_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        raise FileNotFoundError(
            "No wheel file found under ./wheels. Deploy with a prepared app source package."
        )
    return wheels[0]


def _install_wheel(wheel_path: Path) -> None:
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--upgrade",
            "--force-reinstall",
            "--no-warn-conflicts",
            str(wheel_path),
        ]
    )


def _load_app_yml_env(source_root: Path) -> dict[str, str]:
    """Load env vars from app.yml since Databricks Apps SNAPSHOT mode may not inject them."""
    import json as _json
    import re

    app_yml = source_root / "app.yml"
    if not app_yml.exists():
        return {}
    try:
        text = app_yml.read_text()
        env_vars: dict[str, str] = {}
        in_env = False
        current_name = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "env:":
                in_env = True
                continue
            if in_env:
                if not stripped or (not line.startswith(" ") and not line.startswith("-")):
                    break
                m_name = re.match(r"-?\s*name:\s*(.+)", stripped)
                m_value = re.match(r"value:\s*(.*)", stripped)
                if m_name:
                    current_name = m_name.group(1).strip().strip("'\"")
                elif m_value and current_name:
                    val = m_value.group(1).strip().strip("'\"")
                    env_vars[current_name] = val
                    current_name = None
        return env_vars
    except Exception as exc:
        print(f"Warning: failed to parse app.yml env: {exc}")
        return {}


def main() -> None:
    source_root = Path(__file__).resolve().parent
    wheel_path = _find_wheel()
    print(f"Installing wheel: {wheel_path.name}")
    _install_wheel(wheel_path)

    env = os.environ.copy()
    # Inject env vars from app.yml (don't override existing env)
    for key, value in _load_app_yml_env(source_root).items():
        env.setdefault(key, value)
    env.setdefault("AIWEB_DIST_DIR", str(source_root / "aiweb-dist"))
    # Start the packaged app entrypoint after installation.
    cmd = ["uv", "run", "python", "-m", "scripts.start_app"]
    raise SystemExit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    main()
