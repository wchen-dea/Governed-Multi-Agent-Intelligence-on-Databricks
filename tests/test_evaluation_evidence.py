import json
from types import SimpleNamespace

import pytest

from operations.evaluate_agent import _write_evaluation_evidence, evaluate


def test_evaluation_evidence_preserves_gate_metrics_and_run_id(tmp_path, monkeypatch):
    evidence_path = tmp_path / "evaluation.json"
    monkeypatch.setenv("EVAL_EVIDENCE_PATH", str(evidence_path))
    result = SimpleNamespace(metrics={"Safety/mean": 1.0, "AuthCorrectness/mean": 0.95})
    run = SimpleNamespace(info=SimpleNamespace(run_id="run-123"))
    monkeypatch.setattr("operations.evaluate_agent.mlflow.active_run", lambda: run)
    logged = []
    monkeypatch.setattr(
        "operations.evaluate_agent.mlflow.log_artifact",
        lambda path, artifact_path: logged.append((path, artifact_path)),
    )

    _write_evaluation_evidence(result, "pass", ["placeholder-agent"])

    payload = json.loads(evidence_path.read_text())
    assert payload["gate_status"] == "pass"
    assert payload["mlflow_run_id"] == "run-123"
    assert payload["metrics"]["Safety/mean"] == 1.0
    assert payload["skipped_subagents"] == ["placeholder-agent"]
    assert logged == [(str(evidence_path), "release-evidence")]


def test_evaluate_records_blocked_evidence_when_mlflow_run_cannot_start(
    tmp_path, monkeypatch
):
    evidence_path = tmp_path / "blocked.json"
    monkeypatch.setenv("EVAL_EVIDENCE_PATH", str(evidence_path))
    monkeypatch.setattr("operations.evaluate_agent.skipped_subagent_names", lambda: [])
    monkeypatch.setattr("operations.evaluate_agent.mlflow.active_run", lambda: None)
    monkeypatch.setattr(
        "operations.evaluate_agent.mlflow.start_run",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("invalid credentials")),
    )
    monkeypatch.setattr(
        "operations.evaluate_agent.mlflow.flush_async_logging", lambda: None
    )
    monkeypatch.setattr(
        "operations.evaluate_agent.mlflow.flush_trace_async_logging", lambda: None
    )

    with pytest.raises(RuntimeError, match="invalid credentials"):
        evaluate()

    payload = json.loads(evidence_path.read_text())
    assert payload["gate_status"] == "blocked"
    assert payload["mlflow_run_id"] is None
    assert payload["error"] == "invalid credentials"
