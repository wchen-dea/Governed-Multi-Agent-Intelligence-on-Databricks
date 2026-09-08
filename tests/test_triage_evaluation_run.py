from types import SimpleNamespace
from unittest.mock import Mock

from operations import triage_evaluation_run


def test_triage_run_passes_experiment_location_for_run_id(monkeypatch):
    get_run = Mock(return_value=SimpleNamespace(info=SimpleNamespace(experiment_id="1234")))
    search_traces = Mock(return_value=[])
    monkeypatch.setattr(triage_evaluation_run.mlflow, "get_run", get_run)
    monkeypatch.setattr(triage_evaluation_run.mlflow, "search_traces", search_traces)

    assert triage_evaluation_run.triage_run("run-1", None) == {}

    get_run.assert_called_once_with("run-1")
    search_traces.assert_called_once_with(
        run_id="run-1",
        locations=["1234"],
        return_type="list",
    )