import os
from unittest.mock import patch

import pytest

from backend.evaluate_agent import enforce_release_gate


class _FakeResult:
    def __init__(self, metrics: dict[str, float]) -> None:
        self.metrics = metrics


def test_enforce_release_gate_does_not_block_on_low_tool_call_accuracy():
    """tool_call_accuracy is reported but non-blocking (known MLflow scoring gap)."""
    result = _FakeResult(
        {
            "tool_call_correctness/mean": 0.30,
            "authcorrectness/mean": 0.975,
            "safety/mean": 1.0,
            "directgroundedness/mean": 0.9875,
        }
    )
    enforce_release_gate(result)  # must not raise


def test_enforce_release_gate_still_blocks_on_low_safety():
    result = _FakeResult(
        {
            "tool_call_correctness/mean": 0.30,
            "authcorrectness/mean": 0.975,
            "safety/mean": 0.50,
            "directgroundedness/mean": 0.9875,
        }
    )
    with pytest.raises(RuntimeError, match="safety"):
        enforce_release_gate(result)


def test_enforce_release_gate_raises_when_no_metrics_at_all():
    with pytest.raises(RuntimeError, match="no aggregate metrics"):
        enforce_release_gate(_FakeResult({}))


def test_enforce_release_gate_missing_tool_call_accuracy_never_blocks_even_with_require_all():
    result = _FakeResult(
        {
            "authcorrectness/mean": 0.975,
            "safety/mean": 1.0,
            "directgroundedness/mean": 0.9875,
        }
    )
    with patch.dict(os.environ, {"EVAL_REQUIRE_ALL_KPIS": "true"}):
        enforce_release_gate(result)  # must not raise despite missing tool_call metric
