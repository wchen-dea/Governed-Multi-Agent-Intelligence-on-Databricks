#!/usr/bin/env python3
"""Triage MLflow evaluation run traces into ToolCallCorrectness failure categories.

Usage:
    uv run assistant-triage-evaluation [--run-id RUN_ID] [--experiment-id EXPERIMENT_ID]

Classifies each trace with a failing ToolCallCorrectness (or DataToolAttempt)
assessment into one of the categories called out in `docs/quality/evaluation-spec.md`:

- incorrect_tool_selected
- required_tool_omitted
- tool_should_not_have_been_called
- policy_or_auth_mismatch
- scorer_invocation_failure

Classification is a best-effort heuristic over assessment rationale text and
error state; always confirm against the underlying trace before treating a
category as ground truth.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

import mlflow
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=True)

TOOL_CALL_SCORER_NAMES = ("tool_call_correctness", "data_tool_attempt")

_CATEGORY_KEYWORDS = {
    "policy_or_auth_mismatch": (
        "authoriz",
        "persona",
        "denied",
        "obo",
        "auth",
        "permission",
    ),
    "tool_should_not_have_been_called": (
        "should not have been called",
        "unnecessary",
        "did not need",
        "not required",
        "no tool",
    ),
    "required_tool_omitted": (
        "did not call",
        "should have called",
        "missing tool",
        "omitted",
        "failed to invoke",
        "no tool call",
    ),
}


def _classify(rationale: str, has_error: bool) -> str:
    """Classify one failing assessment into a triage category.

    Args:
        rationale: Free-text rationale from the scorer assessment, if any.
        has_error: Whether the assessment itself failed to execute.

    Returns:
        One of the five documented triage categories.
    """
    if has_error:
        return "scorer_invocation_failure"
    lowered = rationale.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "incorrect_tool_selected"


def triage_run(run_id: str | None, experiment_id: str | None) -> dict[str, list[dict[str, str]]]:
    """Fetch traces for a run and classify failing tool-call assessments.

    Args:
        run_id: MLflow run id to triage. Mutually exclusive with experiment_id.
        experiment_id: Experiment id to pull the most recent run's traces from.

    Returns:
        Mapping of triage category to a list of {trace_id, rationale} entries.
    """
    if not run_id and experiment_id:
        runs = mlflow.search_runs(
            experiment_ids=[experiment_id],
            order_by=["start_time DESC"],
            max_results=1,
        )
        if runs.empty:
            print(f"No runs found for experiment {experiment_id}", file=sys.stderr)
            return {}
        run_id = str(runs.iloc[0]["run_id"])

    if not run_id:
        print("Provide --run-id or --experiment-id", file=sys.stderr)
        return {}

    print(f"Triaging traces for run {run_id} ...")
    traces = mlflow.search_traces(run_id=run_id, return_type="list")
    buckets: dict[str, list[dict[str, str]]] = {}

    for trace in traces:
        trace_id = getattr(trace.info, "request_id", None) or getattr(
            trace.info, "trace_id", "<unknown>"
        )
        try:
            assessments = trace.search_assessments(all=True)
        except Exception as exc:  # defensive: assessment schema can vary by MLflow version
            print(f"  Could not read assessments for trace {trace_id}: {exc}", file=sys.stderr)
            continue

        for assessment in assessments:
            name = str(getattr(assessment, "name", "") or "").lower()
            if not any(marker in name for marker in TOOL_CALL_SCORER_NAMES):
                continue

            feedback = getattr(assessment, "feedback", None)
            value = getattr(feedback, "value", None) if feedback else None
            has_error = bool(getattr(assessment, "error", None))
            passed = bool(value) and not has_error
            if passed:
                continue

            rationale = str(getattr(assessment, "rationale", "") or "")
            category = _classify(rationale, has_error)
            buckets.setdefault(category, []).append(
                {"trace_id": str(trace_id), "rationale": rationale[:200]}
            )

    return buckets


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage MLflow evaluation run tool-call failures")
    parser.add_argument("--run-id", default=None, help="MLflow run id to triage")
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="Experiment id to triage the latest run from (used when --run-id is omitted)",
    )
    args = parser.parse_args()

    buckets = triage_run(args.run_id, args.experiment_id)
    if not buckets:
        print("No failing tool-call assessments found (or no traces available).")
        return

    counts = Counter({category: len(entries) for category, entries in buckets.items()})
    print("\n--- Triage summary ---")
    for category, count in counts.most_common():
        print(f"  {category}: {count}")

    print("\n--- Details ---")
    for category, entries in buckets.items():
        print(f"\n[{category}]")
        for entry in entries[:10]:
            print(f"  trace={entry['trace_id']}  rationale={entry['rationale']!r}")
        if len(entries) > 10:
            print(f"  ... ({len(entries) - 10} more)")


if __name__ == "__main__":
    main()
