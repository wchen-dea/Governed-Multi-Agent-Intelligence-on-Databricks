"""Build inspectable, conservative route plans before model orchestration."""

from dataclasses import replace
import re

from backend.domain.execution_contracts import RoutePlan
from backend.domain.subagent_config import SubagentConfig


def build_route_plan(
    question: str,
    subagents: list[SubagentConfig],
) -> tuple[RoutePlan, list[SubagentConfig]]:
    """Select capability-matching subagents, or retain all on ambiguity."""
    terms = set(re.findall(r"[a-z0-9_]+", question.lower()))
    scored = []
    for subagent in subagents:
        description_terms = set(re.findall(r"[a-z0-9_]+", subagent.description.lower()))
        name_terms = set(re.findall(r"[a-z0-9_]+", subagent.name.lower()))
        score = len(terms & (description_terms | name_terms))
        if score:
            scored.append((score, subagent))

    if not scored:
        return RoutePlan(
            candidates=tuple(subagent.name for subagent in subagents),
            reason="ambiguous_fallback",
        ), subagents

    best_score = max(score for score, _ in scored)
    candidates = [subagent for score, subagent in scored if score == best_score]
    plan = RoutePlan(
        candidates=tuple(subagent.name for subagent in candidates),
        reason="capability_match",
        confidence=min(best_score / max(len(terms), 1), 1.0),
        requires_evidence=any(subagent.requires_evidence for subagent in candidates),
    )
    return plan, candidates