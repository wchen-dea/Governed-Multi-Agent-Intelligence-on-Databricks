#!/usr/bin/env python3
"""Deploy a Databricks App through the Apps REST API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

from databricks.sdk import WorkspaceClient
from ruamel.yaml import YAML


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_app_create_payload(
    app_name: str, source_code_path: str, target: str, app_spec_path: str
) -> dict:
    yaml = YAML(typ="safe")
    bundle = yaml.load((REPO_ROOT / "databricks.yml").read_text())
    target_config = yaml.load((REPO_ROOT / "targets" / f"{target}.yml").read_text())
    spec_path = Path(app_spec_path)
    if not spec_path.is_absolute():
        spec_path = REPO_ROOT / spec_path
    app_resources = yaml.load(spec_path.read_text())["resources"]["apps"]
    app_resource = next(iter(app_resources.values()))

    values = {
        name: definition.get("default")
        for name, definition in bundle.get("variables", {}).items()
        if isinstance(definition, dict) and "default" in definition
    }
    values.update(target_config["targets"][target].get("variables", {}))

    def resolve(value):
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, str):
            value = value.replace("${bundle.target}", target)
            for name, replacement in values.items():
                value = value.replace(f"${{var.{name}}}", str(replacement or ""))
            return value
        return value

    resolved = resolve(app_resource)
    resolved["name"] = app_name
    resolved["default_source_code_path"] = source_code_path
    resolved.pop("source_code_path", None)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--source-code-path", required=True)
    parser.add_argument("--target", default="dev")
    parser.add_argument(
        "--app-spec-path", default="resources/multiagent_app.yml"
    )
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    kwargs = {"profile": args.profile} if args.profile else {}
    workspace = WorkspaceClient(**kwargs)
    try:
        app = workspace.apps.get(args.app_name)
    except Exception:
        app = workspace.api_client.do(
            "POST",
            "/api/2.0/apps",
            body=_load_app_create_payload(
                args.app_name, args.source_code_path, args.target, args.app_spec_path
            ),
        )
        print(f"Created app record {args.app_name} through the Apps REST API.")
    path = f"/api/2.0/apps/{quote(args.app_name, safe='')}/deployments"
    response = workspace.api_client.do(
        "POST",
        path,
        body={
            "source_code_path": args.source_code_path,
            "mode": "SNAPSHOT",
        },
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    print(
        f"Submitted REST deployment for {args.app_name} "
        f"from {args.source_code_path}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REST app deployment failed: {exc}", file=sys.stderr)
        raise
