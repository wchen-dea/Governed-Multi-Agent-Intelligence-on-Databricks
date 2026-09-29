"""Static bundle contracts for the durable delegation worker."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_worker_job_is_continuous_singleton_wheel_task():
    payload = yaml.safe_load(
        (ROOT / "resources" / "delegation_worker_job.yml").read_text()
    )
    job = payload["resources"]["jobs"]["delegation_worker"]
    task = job["tasks"][0]

    assert job["continuous"]["pause_status"] == "${var.delegation_worker_pause_status}"
    assert job["max_concurrent_runs"] == 1
    assert task["python_wheel_task"]["entry_point"] == "delegation-worker"
    assert "../dist/multiagent-*.whl" in job["environments"][0]["spec"]["dependencies"]


def test_dev_uses_job_worker_not_in_process_worker():
    payload = yaml.safe_load((ROOT / "targets" / "dev.yml").read_text())
    variables = payload["targets"]["dev"]["variables"]

    assert variables["agent_task_backend"] == "uc_table"
    assert variables["delegation_worker_pause_status"] == "UNPAUSED"


def test_all_deployed_targets_require_shared_state_and_job_worker():
    for target in ("dev", "qa", "stg", "prd"):
        payload = yaml.safe_load((ROOT / "targets" / f"{target}.yml").read_text())
        variables = payload["targets"][target]["variables"]

        assert variables["message_bus_backend"] == "uc_table"
        assert variables["approval_backend"] == "uc_table"
        assert variables["agent_task_backend"] == "uc_table"
        assert variables["memory_backend"] == "lakebase"
        assert variables["route_affinity_backend"] == "lakebase"
        assert variables["delegation_worker_pause_status"] == "UNPAUSED"


def test_app_has_no_in_process_worker_configuration():
    payload = yaml.safe_load((ROOT / "resources" / "multiagent_app.yml").read_text())
    env_names = {
        item["name"]
        for item in payload["resources"]["apps"]["multiagent-app"]["config"]["env"]
    }

    assert "AGENT_TASK_WORKER_ENABLED" not in env_names
    assert "AGENT_TASK_WORKER_POLL_SECONDS" not in env_names
    assert "ROUTE_AFFINITY_BACKEND" in env_names
