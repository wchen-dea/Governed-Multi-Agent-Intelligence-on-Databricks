"""Build inspectable, conservative route plans before model orchestration."""

import re

from backend.domain.execution_contracts import RoutePlan
from backend.domain.subagent_config import SubagentConfig


MIN_ROUTE_CONFIDENCE = 0.60


def build_route_plan(
    question: str,
    subagents: list[SubagentConfig],
) -> tuple[RoutePlan, list[SubagentConfig]]:
    """Select capability-matching subagents, or retain all on ambiguity."""
    stop_words = {
        "a", "an", "and", "are", "ask", "about", "by", "for", "from", "how",
        "in", "is", "it", "of", "on", "or", "the", "to", "what", "with", "you",
        "matching", "asking", "type",
    }
    terms = {
        normalized
        for term in re.findall(r"[a-z0-9_]+", question.lower())
        for normalized in [term.rstrip("s") if term.endswith("s") else term]
        if normalized not in stop_words and len(normalized) > 2
    }
    capabilities: list[dict[str, float]] = []
    for subagent in subagents:
        primary = f"{subagent.name} {subagent.description}".lower()
        secondary = (subagent.system_prompt or "").lower()
        weights: dict[str, float] = {}
        for term in re.findall(r"[a-z0-9_]+", primary):
            normalized = term.rstrip("s") if term.endswith("s") else term
            weights[normalized] = 1.0
        for term in re.findall(r"[a-z0-9_]+", secondary):
            normalized = term.rstrip("s") if term.endswith("s") else term
            weights.setdefault(normalized, 0.25)
        capabilities.append(weights)

    document_frequency = {
            term: sum(term in capability for capability in capabilities)
        for term in terms
    }
    scored: list[tuple[float, SubagentConfig]] = []
    for index, subagent in enumerate(subagents):
        capability = capabilities[index]
        score = sum(
            capability[term] / document_frequency[term]
            for term in terms
            if term in capability and document_frequency[term]
        )
        if score:
            scored.append((score, subagent))

    if not scored:
        return RoutePlan(
            candidates=tuple(subagent.name for subagent in subagents),
            reason="ambiguous_fallback",
        ), subagents

    best_score = max(score for score, _ in scored)
    candidates = [subagent for score, subagent in scored if score == best_score]
    next_score = max(
        (score for score, _ in scored if score < best_score),
        default=0.0,
    )
    confidence = best_score / max(best_score + next_score, 1e-9)
    plan = RoutePlan(
        candidates=tuple(subagent.name for subagent in candidates),
        reason="capability_match",
        confidence=confidence,
        requires_evidence=any(subagent.requires_evidence for subagent in candidates),
    )
    if plan.confidence < MIN_ROUTE_CONFIDENCE:
        return RoutePlan(
            candidates=tuple(subagent.name for subagent in subagents),
            reason="low_confidence_fallback",
            confidence=plan.confidence,
            requires_evidence=any(subagent.requires_evidence for subagent in subagents),
        ), subagents
    return plan, candidates