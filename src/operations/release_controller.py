"""Coordinate DAB infrastructure deployment and Databricks App release steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from databricks.sdk import WorkspaceClient

from operations.databricks_apps_client import AppHealth, DatabricksAppsClient

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ReleaseManifest:
    """Identify the immutable source payload and App deployments for a release."""

    release_id: str
    target: str
    bundle_name: str
    workspace_file_path: str
    apps: tuple[str, ...]
    source_paths: dict[str, str]
    artifact_digests: dict[str, str]

    def write(self, path: Path) -> None:
        """Write the manifest as stable, reviewable JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")


def _run(command: list[str], *, output: bool = False) -> str:
    """Run a release command from the repository root."""
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=output,
    )
    return result.stdout if output else ""


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file or directory tree."""
    digest = hashlib.sha256()
    paths = sorted(path.rglob("*") if path.is_dir() else [path])
    for item in paths:
        if item.is_file():
            digest.update(str(item.relative_to(path if path.is_dir() else item.parent)).encode())
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _bundle_file_path(target: str, profile: str) -> str:
    """Resolve the workspace payload root from bundle validation output."""
    raw = _run(
        [
            "databricks",
            "bundle",
            "validate",
            "-t",
            target,
            "--profile",
            profile,
            "--output",
            "json",
        ],
        output=True,
    )
    payload = json.loads(raw)
    file_path = payload.get("workspace", {}).get("file_path")
    if not file_path:
        raise RuntimeError("Bundle validation did not return workspace.file_path")
    return file_path


def _import_source(local_path: Path, workspace_path: str, profile: str) -> None:
    """Synchronize a local source directory into the workspace payload."""
    _run(
        [
            "databricks",
            "workspace",
            "import-dir",
            str(local_path),
            workspace_path,
            "--overwrite",
            "--profile",
            profile,
        ]
    )


def build_manifest(target: str, workspace_file_path: str, app_names: tuple[str, ...]) -> ReleaseManifest:
    """Build a release manifest from the current source payload."""
    source_paths = {
        app_names[0]: f"{workspace_file_path}/src/hitl-agent",
        app_names[1]: f"{workspace_file_path}/.databricks_app_source",
    }
    source_roots = {
        app_names[0]: REPO_ROOT / "src" / "hitl-agent",
        app_names[1]: REPO_ROOT / ".databricks_app_source",
    }
    digests = {name: _sha256(path) for name, path in source_roots.items() if path.exists()}
    return ReleaseManifest(
        release_id=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        target=target,
        bundle_name="multiagent-app-on-databricks",
        workspace_file_path=workspace_file_path,
        apps=app_names,
        source_paths=source_paths,
        artifact_digests=digests,
    )


def _default_app_names(target: str) -> tuple[str, str]:
    """Return the repository's target-specific HITL and orchestrator names."""
    hitl_name = "hitl-app-agent" if target == "dev" else (
        "store-intervention-agent" if target == "prd" else f"store-intervention-agent-{target}"
    )
    app_name = "multiagent-app" if target == "prd" else f"multiagent-app-{target}"
    return hitl_name, app_name


def start_and_check(
    *, profile: str, app_names: tuple[str, ...], timeout_seconds: float
) -> list[AppHealth]:
    """Start Apps and wait until every App has a healthy active deployment."""
    client = DatabricksAppsClient(WorkspaceClient(profile=profile))
    for app_name in app_names:
        client.start(app_name)
    return [
        client.wait_for_health(app_name, timeout_seconds=timeout_seconds)
        for app_name in app_names
    ]


def release(
    *,
    target: str,
    profile: str,
    app_names: tuple[str, ...],
    deploy_infrastructure: bool,
    start_apps: bool,
    timeout_seconds: float,
    manifest_path: Path,
) -> list[AppHealth]:
    """Deploy infrastructure, publish App snapshots, and verify App health."""
    if len(app_names) != 2:
        raise ValueError("Exactly two Apps are required: HITL App and orchestrator App")

    workspace_file_path = _bundle_file_path(target, profile)
    if deploy_infrastructure:
        _run(["databricks", "bundle", "deploy", "-t", target, "--profile", profile])

    hitl_local = REPO_ROOT / "src" / "hitl-agent"
    app_local = REPO_ROOT / ".databricks_app_source"
    _import_source(hitl_local, f"{workspace_file_path}/src/hitl-agent", profile)
    _import_source(app_local, f"{workspace_file_path}/.databricks_app_source", profile)

    client = DatabricksAppsClient(WorkspaceClient(profile=profile))
    manifest = build_manifest(target, workspace_file_path, app_names)
    manifest.write(manifest_path)
    for app_name in app_names:
        client.deploy_snapshot(app_name, manifest.source_paths[app_name])
    if start_apps:
        for app_name in app_names:
            client.start(app_name)
    return [
        client.wait_for_health(app_name, timeout_seconds=timeout_seconds)
        for app_name in app_names
    ]


def main() -> int:
    """Run the advanced hybrid release controller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="dev", choices=("dev", "qa", "stg", "prd"))
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--app-name", default=None)
    parser.add_argument("--hitl-app-name", default=None)
    parser.add_argument("--manifest", type=Path, default=Path("dist/release-manifest.json"))
    parser.add_argument("--timeout-seconds", type=float, default=1200)
    parser.add_argument("--skip-infrastructure", action="store_true")
    parser.add_argument("--skip-start", action="store_true")
    parser.add_argument("--start-and-check", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    default_hitl, default_app = _default_app_names(args.target)
    names = (args.hitl_app_name or default_hitl, args.app_name or default_app)
    if args.check_only:
        client = DatabricksAppsClient(WorkspaceClient(profile=args.profile))
        health = [
            client.wait_for_health(name, timeout_seconds=args.timeout_seconds)
            for name in names
        ]
    elif args.start_and_check:
        health = start_and_check(
            profile=args.profile, app_names=names, timeout_seconds=args.timeout_seconds
        )
    else:
        health = release(
            target=args.target,
            profile=args.profile,
            app_names=names,
            deploy_infrastructure=not args.skip_infrastructure,
            start_apps=not args.skip_start,
            timeout_seconds=args.timeout_seconds,
            manifest_path=(REPO_ROOT / args.manifest).resolve(),
        )
    for item in health:
        print(json.dumps(asdict(item), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())