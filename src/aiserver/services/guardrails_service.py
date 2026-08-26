"""Apply response guardrails for governed or sensitive outputs."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from backend.domain.subagent_config import SubagentConfig


@dataclass(frozen=True)
class GuardrailResult:
    """Represent deterministic guardrail evaluation outcome.

    Attributes:
        blocked: True when response should be blocked.
        reasons: Stable reason codes explaining why response was blocked.
    """

    blocked: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class InputGuardrailResult:
    """Represent deterministic checks applied before model execution."""

    blocked: bool
    reasons: tuple[str, ...]
    character_count: int


_LOW_CONFIDENCE_PATTERNS = [
    r"\bnot sure\b",
    r"\buncertain\b",
    r"\bi think\b",
    r"\bmaybe\b",
    r"\bcould be\b",
    r"\bmight be\b",
]

_UNSAFE_PATTERNS = [
    r"\bssn\b",
    r"\bsocial security number\b",
    r"\bcredit card number\b",
    r"\bprivate key\b",
    r"\bapi key\b",
    r"\bpassword\b",
]

_INPUT_INJECTION_PATTERNS = [
    r"ignore (?:all|any|the) (?:previous|prior|above) instructions",
    r"reveal (?:the )?(?:system|developer) prompt",
    r"bypass (?:the )?(?:policy|guardrail|authorization)",
]


def _input_text(input_items: Iterable[Any]) -> str:
    """Extract user-visible text without retaining the original payload."""
    chunks: list[str] = []
    for item in input_items:
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if not isinstance(data, dict) or data.get("role") != "user":
            continue
        content = data.get("content", "")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            chunks.extend(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
    return "\n".join(chunks).strip()


def evaluate_input_guardrails(
    input_items: Iterable[Any],
    *,
    max_input_chars: int,
) -> InputGuardrailResult:
    """Check request size and common prompt-injection patterns before routing."""
    text = _input_text(input_items)
    reasons: list[str] = []
    if len(text) > max(max_input_chars, 1):
        reasons.append("input_too_large")
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _INPUT_INJECTION_PATTERNS):
        reasons.append("prompt_injection_detected")
    return InputGuardrailResult(
        blocked=bool(reasons),
        reasons=tuple(sorted(set(reasons))),
        character_count=len(text),
    )


def truncate_response_text(text: str, *, max_response_chars: int) -> tuple[str, bool]:
    """Apply a deterministic response budget and report whether truncation occurred."""
    limit = max(max_response_chars, 1)
    if len(text) <= limit:
        return text, False
    marker = "\n\n[Response truncated to fit the configured response budget.]"
    available = max(limit - len(marker), 0)
    return text[:available].rstrip() + marker, True


def _has_citation(text: str) -> bool:
    """Check whether response text includes an acceptable citation marker.

    Args:
        text: Candidate assistant response text.

    Returns:
        True when text contains bracket citations or a source/citation label.
    """
    return bool(
        re.search(r"\[[0-9]+\]", text)
        or re.search(r"\bsource:\b", text, flags=re.IGNORECASE)
        or re.search(r"\bcitation:\b", text, flags=re.IGNORECASE)
    )


def evaluate_response_guardrails(
    response_text: str,
    governed_subagents: list[SubagentConfig],
) -> GuardrailResult:
    """Apply deterministic guardrails to response text.

    Args:
        response_text: Candidate assistant response.
        governed_subagents: Subagents involved in tool execution for this
            response.

    Returns:
        Guardrail result including block decision and reason codes.

    Notes:
        Evidence is required when any participating subagent sets
        requires_evidence=true.
    """
    text = response_text.strip()
    lowered = text.lower()
    reasons: list[str] = []

    requires_evidence = any(s.requires_evidence for s in governed_subagents)
    has_sensitive_data = any(
        s.data_classification in {"confidential", "restricted"} for s in governed_subagents
    )

    if requires_evidence and text and not _has_citation(text):
        reasons.append("evidence_required")

    if any(re.search(pattern, lowered) for pattern in _UNSAFE_PATTERNS):
        reasons.append("unsafe_output")

    if has_sensitive_data and any(
        re.search(pattern, lowered) for pattern in _LOW_CONFIDENCE_PATTERNS
    ):
        reasons.append("low_confidence_sensitive")

    return GuardrailResult(blocked=bool(reasons), reasons=tuple(sorted(set(reasons))))
