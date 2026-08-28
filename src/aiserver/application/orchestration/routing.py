"""Build inspectable, conservative route plans before model orchestration."""

import re
import threading
import time

from aiserver.contracts.responses import RoutePlan
from aiserver.contracts.subagents import SubagentConfig

MIN_ROUTE_CONFIDENCE = 0.60
ROUTE_STICKINESS_TTL_SECONDS = 600.0

# Per-conversation memory of the last confidently matched route. This lets
# follow-up turns ("follow up on promoter vs detractor counts") that lack
# strong lexical overlap with any subagent stay routed to the same subagent
# instead of broadening to every candidate (or picking the wrong one).
_sticky_routes: dict[str, tuple[float, tuple[str, ...]]] = {}
_sticky_lock = threading.Lock()


def _remember_sticky_route(conversation_id: str | None, candidate_names: tuple[str, ...]) -> None:
    """Record the last confidently matched route for a conversation."""
    if not conversation_id:
        return
    with _sticky_lock:
        _sticky_routes[conversation_id] = (
            time.monotonic() + ROUTE_STICKINESS_TTL_SECONDS,
            candidate_names,
        )


def _recall_sticky_route(conversation_id: str | None, allowed_names: set[str]) -> tuple[str, ...]:
    """Return the previously matched route for a conversation, if still valid."""
    if not conversation_id:
        return ()
    with _sticky_lock:
        entry = _sticky_routes.get(conversation_id)
        if not entry:
            return ()
        expires_at, candidate_names = entry
        if expires_at < time.monotonic():
            del _sticky_routes[conversation_id]
            return ()
    return tuple(name for name in candidate_names if name in allowed_names)


def build_route_plan(
    question: str,
    subagents: list[SubagentConfig],
    conversation_id: str | None = None,
) -> tuple[RoutePlan, list[SubagentConfig]]:
    """Select capability-matching subagents, or retain all on ambiguity.

    Args:
        question: Latest user question text.
        subagents: Policy-allowed subagents eligible for this request.
        conversation_id: Optional session id used to keep follow-up turns
            routed to the same subagent when lexical matching is weak.
    """
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "ask",
        "about",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "with",
        "you",
        "matching",
        "asking",
        "type",
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
        term: sum(term in capability for capability in capabilities) for term in terms
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
        allowed_names = {subagent.name for subagent in subagents}
        sticky = _recall_sticky_route(conversation_id, allowed_names)
        if sticky:
            sticky_candidates = [subagent for subagent in subagents if subagent.name in sticky]
            return RoutePlan(
                candidates=sticky,
                reason="sticky_route",
                requires_evidence=any(subagent.requires_evidence for subagent in sticky_candidates),
            ), sticky_candidates
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
        allowed_names = {subagent.name for subagent in subagents}
        sticky = _recall_sticky_route(conversation_id, allowed_names)
        if sticky:
            sticky_candidates = [subagent for subagent in subagents if subagent.name in sticky]
            return RoutePlan(
                candidates=sticky,
                reason="sticky_route",
                confidence=plan.confidence,
                requires_evidence=any(subagent.requires_evidence for subagent in sticky_candidates),
            ), sticky_candidates
        return RoutePlan(
            candidates=tuple(subagent.name for subagent in subagents),
            reason="low_confidence_fallback",
            confidence=plan.confidence,
            requires_evidence=any(subagent.requires_evidence for subagent in subagents),
        ), subagents

    _remember_sticky_route(conversation_id, plan.candidates)
    return plan, candidates
