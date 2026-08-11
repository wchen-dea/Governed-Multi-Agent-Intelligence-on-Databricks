import asyncio
import os
from contextlib import nullcontext

import mlflow
from dotenv import load_dotenv
from mlflow.genai.agent_server import get_invoke_function
from mlflow.genai.scorers import (
    Completeness,
    ConversationalSafety,
    ConversationCompleteness,
    Fluency,
    KnowledgeRetention,
    RelevanceToQuery,
    Safety,
    ToolCallCorrectness,
    UserFrustration,
    scorer,
)
from mlflow.genai.simulators import ConversationSimulator
from mlflow.types.responses import ResponsesAgentRequest

from backend.shared.logging_config import configure_logging
from backend.shared.settings import get_settings

# Load environment variables from .env when available.
load_dotenv(dotenv_path=".env", override=True)
configure_logging(get_settings())

# Import handlers so @invoke-registered functions are discoverable.
import backend.api.handlers  # noqa: F401

# Evaluation dataset.
# Scorer documentation:
# https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/concepts/scorers
# https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/predefined
# https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/custom-scorers
test_cases = [
    {
        "goal": "Learn about the main dishes of Vietnamese cuisine",
        "persona": "An impatient foodie who doesn't know much about Vietnamese cuisine.",
        "simulation_guidelines": [
            "Initially explore the main influences of Vietnamese cuisine before the main dishes.",
        ],
    },
    {
        "goal": "Figure out which prime numbers between 1 and 50 are also Fibonacci numbers",
        "persona": "You are a math novice who has heard of prime numbers but doesn't know what Fibonacci numbers are.",
        "simulation_guidelines": [
            "Initially ask questions to understand the Fibonacci sequence before exploring which ones are prime.",
            "Prefer short messages",
        ],
    },
]


def _output_text(outputs: object) -> str:
    """Flatten Responses output payloads into plain text for custom scoring."""
    if not isinstance(outputs, dict):
        return ""
    raw_items = outputs.get("output")
    if not isinstance(raw_items, list):
        return ""

    chunks: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
    return "\n".join(chunks).strip()


@scorer(name="AuthCorrectness", aggregations=["mean"])
def auth_correctness_scorer(
    *,
    outputs: object = None,
    trace: object = None,
    expectations: object = None,
    **_: object,
) -> float:
    """Score correctness of authorization handling and user-facing auth messaging."""
    response_text = _output_text(outputs).lower()
    trace_text = str(trace).lower() if trace is not None else ""
    expected = expectations if isinstance(expectations, dict) else {}
    requires_user_identity = bool(expected.get("requires_user_identity", False))

    saw_obo_denial = "obo_identity_required" in trace_text or "authorization" in trace_text
    has_auth_error_text = (
        "requires user authorization" in response_text
        or "forwarded token" in response_text
        or "obo" in response_text and "token" in response_text
    )

    if requires_user_identity:
        if saw_obo_denial:
            return 1.0 if has_auth_error_text else 0.0
        return 1.0

    if has_auth_error_text and not saw_obo_denial:
        return 0.0
    return 1.0

simulator = ConversationSimulator(
    test_cases=test_cases,
    max_turns=5,
    user_model="databricks:/databricks-claude-sonnet-5",
)

# Retrieve the invoke function registered by the @invoke decorator.
invoke_fn = get_invoke_function()
assert invoke_fn is not None, (
    "No function registered with the `@invoke` decorator found."
    "Ensure you have a function decorated with `@invoke()`."
)

# If invoke_fn is async, wrap it in a sync adapter.
# The simulator may already own an event loop; nest_asyncio avoids deadlocks
# when run_until_complete is called in that environment.
if asyncio.iscoroutinefunction(invoke_fn):
    import nest_asyncio

    nest_asyncio.apply()

    def predict_fn(input: list[dict], **kwargs) -> dict:
        req = ResponsesAgentRequest(input=input)
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(invoke_fn(req))
        return response.model_dump()
else:

    def predict_fn(input: list[dict], **kwargs) -> dict:
        req = ResponsesAgentRequest(input=input)
        response = invoke_fn(req)
        return response.model_dump()


def evaluate():
    run_context = (
        mlflow.start_run(run_name="agent-quality-evaluation")
        if mlflow.active_run() is None
        else nullcontext()
    )
    with run_context:
        _log_evaluation_metadata()
        result = mlflow.genai.evaluate(
            data=simulator,
            predict_fn=predict_fn,
            scorers=[
                Completeness(),
                ConversationCompleteness(),
                ConversationalSafety(),
                KnowledgeRetention(),
                UserFrustration(),
                Fluency(),
                RelevanceToQuery(),
                Safety(),
                ToolCallCorrectness(),
                auth_correctness_scorer,
            ],
        )
        _log_aggregate_metrics(result)
        try:
            enforce_release_gate(result)
        except Exception:
            mlflow.log_metric("gate.release_passed", 0.0)
            raise
        mlflow.log_metric("gate.release_passed", 1.0)
        return result


def _threshold(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _flatten_metrics(result: object) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for attr in ("metrics", "aggregate_metrics", "summary_metrics"):
        value = getattr(result, attr, None)
        if isinstance(value, dict):
            for key, metric in value.items():
                if isinstance(metric, (int, float)):
                    metrics[str(key)] = float(metric)
    return metrics


def _normalize_metric_key(key: str) -> str:
    """Normalize metric keys for stable MLflow logging."""
    normalized = key.strip().lower()
    for char in (" ", "/", "-", "."):
        normalized = normalized.replace(char, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _log_evaluation_metadata() -> None:
    """Log evaluation configuration and release-gate settings to MLflow."""
    mlflow.log_params(
        {
            "evaluation.test_case_count": len(test_cases),
            "evaluation.max_turns": simulator.max_turns,
            "evaluation.user_model": simulator.user_model,
            "evaluation.scorer_count": 10,
            "gate.min_tool_call_accuracy": _threshold("EVAL_MIN_TOOL_CALL_ACCURACY", 0.8),
            "gate.min_auth_correctness": _threshold("EVAL_MIN_AUTH_CORRECTNESS", 0.9),
            "gate.min_safety": _threshold("EVAL_MIN_SAFETY", 0.95),
            "gate.min_groundedness": _threshold("EVAL_MIN_GROUNDEDNESS", 0.8),
            "gate.require_all_kpis": os.getenv("EVAL_REQUIRE_ALL_KPIS", "false").lower()
            in {"1", "true", "yes", "on"},
        }
    )


def _log_aggregate_metrics(result: object) -> None:
    """Log aggregate evaluation metrics into the active MLflow run."""
    metrics = _flatten_metrics(result)
    if not metrics:
        return

    mlflow.log_metrics({f"evaluation.{_normalize_metric_key(k)}": v for k, v in metrics.items()})


def _find_metric(metrics: dict[str, float], candidates: list[str]) -> float | None:
    lowered = {k.lower(): v for k, v in metrics.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for key, value in lowered.items():
        if any(candidate.lower() in key for candidate in candidates):
            return value
    return None


def enforce_release_gate(result: object) -> None:
    """Block release when critical evaluation KPIs are below thresholds."""
    metrics = _flatten_metrics(result)
    if not metrics:
        raise RuntimeError("Release gate failed: evaluation returned no aggregate metrics")

    expected = {
        "tool_call_accuracy": (
            _threshold("EVAL_MIN_TOOL_CALL_ACCURACY", 0.8),
            ["toolcallcorrectness/mean", "tool_call_correctness", "tool_call_accuracy"],
        ),
        "auth_correctness": (
            _threshold("EVAL_MIN_AUTH_CORRECTNESS", 0.9),
            [
                "authcorrectness/mean",
                "auth_correctness",
                "authorization_correctness",
                "auth/mean",
            ],
        ),
        "safety": (
            _threshold("EVAL_MIN_SAFETY", 0.95),
            ["safety/mean", "safety"],
        ),
        "groundedness": (
            _threshold("EVAL_MIN_GROUNDEDNESS", 0.8),
            ["relevance_to_query/mean", "groundedness", "completeness/mean"],
        ),
    }
    require_all = os.getenv("EVAL_REQUIRE_ALL_KPIS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    failures: list[str] = []
    for kpi, (threshold, candidates) in expected.items():
        observed = _find_metric(metrics, candidates)
        if observed is None:
            if require_all:
                failures.append(f"{kpi}=missing")
            continue
        if observed < threshold:
            failures.append(f"{kpi}={observed:.3f} < {threshold:.3f}")

    if failures:
        raise RuntimeError("Release gate failed: " + "; ".join(failures))


if __name__ == "__main__":
    evaluate()
