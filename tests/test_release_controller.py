from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from operations.release_controller import (
    _resolve_worker_job_id,
    build_manifest,
    write_manifest_only,
)


def test_release_manifest_records_worker_job_evidence(tmp_path: Path):
    with patch("operations.release_controller.REPO_ROOT", tmp_path), patch(
        "operations.release_controller.subprocess.check_output",
        return_value="abc123\n",
    ):
        manifest = build_manifest(
            "qa",
            "/Workspace/release",
            ("hitl-qa", "multiagent-qa"),
            job_ids={"delegation_worker": 42},
        )

    assert manifest.job_ids == {"delegation_worker": 42}
    assert manifest.release_id == "abc123"


def test_resolve_worker_job_id_requires_one_exact_match():
    client = MagicMock()
    client.jobs.list.return_value = [
        SimpleNamespace(job_id=42, settings=SimpleNamespace(name="delegation_worker_dev"))
    ]

    assert _resolve_worker_job_id(client, "dev") == 42
    client.jobs.list.assert_called_once_with(name="delegation_worker_dev")


def test_resolve_worker_job_id_rejects_missing_job():
    client = MagicMock()
    client.jobs.list.return_value = []

    with pytest.raises(RuntimeError, match="Expected exactly one"):
        _resolve_worker_job_id(client, "stg")


def test_write_manifest_only_records_deployed_worker(tmp_path: Path):
    client = MagicMock()
    client.jobs.list.return_value = [
        SimpleNamespace(job_id=77, settings=SimpleNamespace(name="delegation_worker_qa"))
    ]
    output = tmp_path / "manifest.json"

    with patch(
        "operations.release_controller._bundle_file_path",
        return_value="/Workspace/release",
    ), patch("operations.release_controller.WorkspaceClient", return_value=client), patch(
        "operations.release_controller.REPO_ROOT", tmp_path
    ), patch(
        "operations.release_controller.subprocess.check_output",
        return_value="def456\n",
    ):
        manifest = write_manifest_only(
            target="qa",
            profile="qa",
            app_names=("hitl-qa", "multiagent-qa"),
            manifest_path=output,
        )

    assert manifest.job_ids == {"delegation_worker": 77}
    assert output.exists()
