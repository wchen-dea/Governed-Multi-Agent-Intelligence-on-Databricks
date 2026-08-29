"""Select the configured Databricks model for a request task type."""

import re
from dataclasses import dataclass
from typing import Literal

from aiserver.config.settings import AppSettings

TaskType = Literal["default", "standard", "reasoning", "synthesis"]


@dataclass(frozen=True)
class ModelSelection:
    """Describe a deterministic model decision for one user request."""

    model: str
    task_type: TaskType
    reason: str
    rationale: str


@dataclass(frozen=True)
class ModelRouteRule:
    """Define one deterministic model route and its operating rationale."""

    task_type: Literal["reasoning", "synthesis"]
    setting_name: Literal["model_routing_reasoning_model", "model_routing_quality_model"]
    reason: str
    terms: frozenset[str]
    rationale: str


MODEL_ROUTE_RULES: tuple[ModelRouteRule, ...] = (
    ModelRouteRule(
        task_type="synthesis",
        setting_name="model_routing_quality_model",
        reason="matched_analysis_or_synthesis_terms",
        terms=frozenset(
            {
                "analyze",
                "analysis",
                "compare",
                "comparison",
                "executive",
                "plan",
                "proposal",
                "recommend",
                "recommendation",
                "recommendations",
                "strategy",
                "summarize",
                "summary",
            }
        ),
        rationale=(
            "Prioritize answer quality for analysis, comparison, executive-summary, and recommendation "
            "tasks where synthesis quality matters more than minimum per-call cost."
        ),
    ),
    ModelRouteRule(
        task_type="reasoning",
        setting_name="model_routing_reasoning_model",
        reason="matched_operational_or_support_terms",
        terms=frozenset(
            {
                "appointment",
                "appointments",
                "configuration",
                "cause",
                "debug",
                "diagnose",
                "diagnosis",
                "flink",
                "incident",
                "invoice",
                "invoices",
                "lag",
                "order",
                "orders",
                "performance",
                "query",
                "root",
                "schema",
                "sql",
                "streaming",
                "troubleshoot",
            }
        ),
        rationale=(
            "Prioritize reasoning quality and task reliability for operational, SQL, support, "
            "and troubleshooting requests where a better plan can reduce retries and manual triage."
        ),
    ),
)

STANDARD_MODEL_RATIONALE = (
    "Use the balanced default model for ordinary lookups and conversational turns to keep "
    "latency and cost efficient while preserving adequate response quality."
)


def select_model(question: str, settings: AppSettings) -> ModelSelection:
    """Choose a model from configured routes without using an extra model call."""
    terms = set(re.findall(r"[a-z0-9_]+", question.lower()))
    if not settings.model_routing_enabled:
        return ModelSelection(
            settings.orchestrator_model,
            "default",
            "model_routing_disabled",
            "Use the configured orchestrator model for all requests when deterministic routing is disabled.",
        )
    for rule in MODEL_ROUTE_RULES:
        if not terms & rule.terms:
            continue
        return ModelSelection(
            getattr(settings, rule.setting_name),
            rule.task_type,
            rule.reason,
            rule.rationale,
        )
    return ModelSelection(
        settings.model_routing_default_model,
        "standard",
        "default_task_route",
        STANDARD_MODEL_RATIONALE,
    )
