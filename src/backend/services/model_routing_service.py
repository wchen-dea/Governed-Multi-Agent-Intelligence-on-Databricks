"""Select the configured Databricks model for a request task type."""

import re
from dataclasses import dataclass

from backend.shared.settings import AppSettings


@dataclass(frozen=True)
class ModelSelection:
    """Describe a deterministic model decision for one user request."""

    model: str
    task_type: str
    reason: str


_REASONING_TERMS = {
    "appointment",
    "appointments",
    "order",
    "orders",
    "invoice",
    "invoices",
    "sql",
    "query",
    "schema",
    "flink",
    "streaming",
    "lag",
    "debug",
    "troubleshoot",
    "configuration",
    "root",
    "cause",
}
_SYNTHESIS_TERMS = {
    "summarize",
    "summary",
    "compare",
    "comparison",
    "strategy",
    "executive",
    "recommend",
    "recommendation",
    "plan",
    "proposal",
    "analyze",
    "analysis",
}


def select_model(question: str, settings: AppSettings) -> ModelSelection:
    """Choose a model from configured routes without using an extra model call."""
    terms = set(re.findall(r"[a-z0-9_]+", question.lower()))
    if not settings.model_routing_enabled:
        return ModelSelection(settings.orchestrator_model, "default", "model_routing_disabled")
    if terms & _REASONING_TERMS:
        return ModelSelection(
            settings.model_routing_reasoning_model,
            "reasoning",
            "matched_operational_or_support_terms",
        )
    if terms & _SYNTHESIS_TERMS:
        return ModelSelection(
            settings.model_routing_quality_model, "synthesis", "matched_analysis_or_synthesis_terms"
        )
    return ModelSelection(settings.model_routing_default_model, "standard", "default_task_route")
