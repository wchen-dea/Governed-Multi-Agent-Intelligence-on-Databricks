"""Deny-by-default policy evaluation for agent-to-agent delegation."""

from dataclasses import dataclass

from backend.domain.agent_messages import DelegationTask
from backend.domain.subagent_config import SubagentConfig


@dataclass(frozen=True)
class DelegationPolicyDecision:
    """Explain whether a delegation task is safe to submit or execute."""

    allowed: bool
    reason_code: str
    reason: str


def evaluate_delegation_policy(
    task: DelegationTask,
    subagents: list[SubagentConfig],
) -> DelegationPolicyDecision:
    """Allow only explicitly configured app-auth delegations within depth bounds."""
    by_name = {subagent.name: subagent for subagent in subagents}
    source = by_name.get(task.source_agent)
    target = by_name.get(task.target_agent)
    if target is None:
        return DelegationPolicyDecision(False, "unknown_agent", "Target agent is not configured")
    if task.auth_mode != "app":
        return DelegationPolicyDecision(
            False, "obo_not_supported", "Delegation supports app auth only"
        )
    if source is not None and task.target_agent not in source.can_delegate_to:
        return DelegationPolicyDecision(
            False, "source_not_allowed", "Source agent may not delegate to target"
        )
    if task.source_agent not in target.accepts_delegations_from:
        return DelegationPolicyDecision(
            False, "target_not_allowed", "Target agent does not accept this source"
        )
    if task.intent not in target.allowed_task_intents:
        return DelegationPolicyDecision(
            False, "intent_not_allowed", "Target agent does not accept this task intent"
        )
    max_depth = source.max_delegation_depth if source is not None else 1
    if len(task.ancestry) >= max_depth:
        return DelegationPolicyDecision(
            False, "max_depth_exceeded", "Delegation depth exceeds source policy"
        )
    return DelegationPolicyDecision(True, "allowed", "Delegation policy allow")
