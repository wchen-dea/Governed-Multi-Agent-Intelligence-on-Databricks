"""Response attribution, approval, truncation, and guardrail helpers."""

from typing import Any

from aiserver.application.guardrails.checks import truncate_response_text
from aiserver.contracts.responses import HumanApprovalState
from aiserver.contracts.subagents import SubagentConfig

APPROVAL_MESSAGE = (
    "\n\nApproval required: this recommendation is pending manager review before any "
    "operational action or dispatch recommendation is sent."
)


def response_text_from_items(items: list[Any]) -> str:
    """Extract plain text from normalized runner output items."""
    chunks: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            chunks.extend(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
    return "\n".join(chunks).strip()


def text_from_stream_event(event: dict[str, Any]) -> str:
    """Extract answer text from one normalized runner event."""
    if event.get("type") == "response.output_text.delta":
        delta = event.get("delta")
        return delta if isinstance(delta, str) else ""
    item = event.get("item")
    if not isinstance(item, dict):
        return ""
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


def approval_state_for_subagents(subagents: list[SubagentConfig]) -> HumanApprovalState:
    """Return pending manager approval for action-oriented subagents."""
    if not any(subagent.requires_human_approval for subagent in subagents):
        return HumanApprovalState(status="not_required", required=False)
    return HumanApprovalState(
        status="pending",
        required=True,
        approver="manager",
        reason=(
            "Human approval required before any operational action can be recommended. "
            "Prepare the intervention packet and wait for manager sign-off."
        ),
    )


def append_approval_message(
    output_items: list[dict[str, Any]],
    approval: HumanApprovalState,
) -> list[dict[str, Any]]:
    """Append manager-review guidance to the last assistant output."""
    if not approval.required or approval.status != "pending":
        return output_items
    return append_text_to_last_assistant(output_items, APPROVAL_MESSAGE)


def guardrail_block_message(reasons: tuple[str, ...]) -> str:
    """Format a safe explanation for a blocked response."""
    reason_list = ", ".join(reasons) if reasons else "policy_check_failed"
    return (
        "I couldn't return the answer because the response was blocked by a guardrail "
        f"({reason_list}). For `evidence_required`, ask the agent to include a citation "
        "such as `[1]` or an explicit `Source:` line."
    )


def candidate_tool_names(data: dict[str, Any]) -> list[str]:
    """Extract candidate tool identifiers from event or output-item data."""
    candidates = [
        value.strip()
        for key in ("name", "tool_name")
        if isinstance((value := data.get(key)), str) and value.strip()
    ]
    item = data.get("item")
    if isinstance(item, dict):
        candidates.extend(
            value.strip()
            for key in ("name", "tool_name")
            if isinstance((value := item.get(key)), str) and value.strip()
        )
    return candidates


def resolve_subagent(
    candidate: str,
    subagents: list[SubagentConfig],
) -> SubagentConfig | None:
    """Map a runtime tool identifier to its configured subagent."""
    normalized = candidate.strip()
    for prefix in ("query_", "Genie:", "MCP:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return next(
        (
            subagent
            for subagent in subagents
            if normalized in {subagent.name, subagent.tool_name}
        ),
        None,
    )


def used_subagents_from_payloads(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Collect distinct configured subagents referenced by runtime payloads."""
    ordered: list[SubagentConfig] = []
    seen: set[str] = set()
    for payload in payloads:
        for candidate in candidate_tool_names(payload):
            subagent = resolve_subagent(candidate, subagents)
            if subagent is not None and subagent.name not in seen:
                seen.add(subagent.name)
                ordered.append(subagent)
    return ordered


def governed_source_suffix(used_subagents: list[SubagentConfig]) -> str:
    """Build deterministic evidence metadata for governed tool-backed output."""
    governed = [subagent for subagent in used_subagents if subagent.requires_evidence]
    if not governed:
        return ""
    parts = [
        (
            f"{subagent.name} "
            f"({'Genie MCP' if subagent.is_genie else subagent.kind.replace('_', ' ')}, "
            f"freshness {subagent.freshness_sla or 'unknown freshness'})"
        )
        for subagent in governed
    ]
    return "\n\nSource: " + "; ".join(parts)


def payload_has_tool_activity(payload: dict[str, Any]) -> bool:
    """Return whether a runtime payload represents tool execution."""
    event_type = payload.get("type")
    item = payload.get("item")
    item_type = item.get("type") if isinstance(item, dict) else None
    return any(
        isinstance(value, str)
        and any(marker in value for marker in ("tool", "mcp", "function_call"))
        for value in (event_type, item_type)
    )


def event_has_tool_activity(payloads: list[dict[str, Any]]) -> bool:
    """Return whether any runtime payload represents tool execution."""
    return any(payload_has_tool_activity(payload) for payload in payloads)


def governed_source_suffix_with_fallback(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> str:
    """Build evidence metadata with safe fallbacks for unlabelled tool output."""
    suffix = governed_source_suffix(used_subagents_from_payloads(payloads, subagents))
    if suffix:
        return suffix
    governed = [subagent for subagent in subagents if subagent.requires_evidence]
    if governed and event_has_tool_activity(payloads):
        return "\n\nSource: tool-backed governed response."
    if governed:
        return "\n\nSource: governed response; source metadata was unavailable in the final output item."
    return ""


def guardrail_scope_subagents(
    payloads: list[dict[str, Any]],
    subagents: list[SubagentConfig],
) -> list[SubagentConfig]:
    """Limit guardrails to subagents that contributed to an answer."""
    used = used_subagents_from_payloads(payloads, subagents)
    if used:
        return used
    if event_has_tool_activity(payloads):
        return [subagent for subagent in subagents if subagent.requires_evidence]
    return []


def append_text_to_last_assistant(
    output_items: list[dict[str, Any]],
    text: str,
) -> list[dict[str, Any]]:
    """Append text to the last assistant item without mutating the input list."""
    updated = [dict(item) for item in output_items]
    for item in reversed(updated):
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, str):
            item["content"] = content + text
            return updated
        if isinstance(content, list):
            blocks = [dict(block) if isinstance(block, dict) else block for block in content]
            for block in reversed(blocks):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"] += text
                    item["content"] = blocks
                    return updated
            blocks.append({"type": "output_text", "text": text.strip()})
            item["content"] = blocks
            return updated
    updated.append({"role": "assistant", "content": text.strip()})
    return updated


def truncate_output_items(
    output_items: list[dict[str, Any]],
    *,
    max_response_chars: int,
) -> list[dict[str, Any]]:
    """Apply the response budget to the final assistant content."""
    updated = [dict(item) for item in output_items]
    for item in reversed(updated):
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, str):
            item["content"], _ = truncate_response_text(
                content,
                max_response_chars=max_response_chars,
            )
            return updated
        if isinstance(content, list):
            blocks = [dict(block) if isinstance(block, dict) else block for block in content]
            for block in reversed(blocks):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    block["text"], _ = truncate_response_text(
                        block["text"],
                        max_response_chars=max_response_chars,
                    )
                    item["content"] = blocks
                    return updated
    return output_items
