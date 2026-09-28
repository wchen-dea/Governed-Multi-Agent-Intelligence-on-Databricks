"""Application service for manager approval workflows."""

from dataclasses import replace
from typing import Any

from aiserver.application.delegation.policy import evaluate_delegation_policy
from aiserver.application.ports.audit import ApprovalRepository, MessageBus
from aiserver.application.ports.tasks import AgentTaskBus
from aiserver.config.settings import AppSettings
from aiserver.contracts.delegation import DelegationTask
from aiserver.contracts.responses import ApprovalDecisionRecord, ApprovalDecisionRequest
from aiserver.contracts.subagents import SubagentConfig


class ApprovalConflictError(RuntimeError):
    """Raised when an approved follow-up cannot pass delegation policy."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(f"Approved follow-up task rejected by delegation policy: {reason_code}")


class ApprovalService:
    """Coordinate approval persistence and optional planning-only delegation."""

    def __init__(
        self,
        repository: ApprovalRepository,
        task_bus: AgentTaskBus,
        message_bus: MessageBus,
        settings: AppSettings,
        subagents: list[SubagentConfig],
    ) -> None:
        self._repository = repository
        self._task_bus = task_bus
        self._message_bus = message_bus
        self._settings = settings
        self._subagents = subagents

    async def submit(self, request: ApprovalDecisionRequest) -> dict[str, object]:
        record = ApprovalDecisionRecord(
            request_id=request.request_id,
            agent_name=request.agent_name,
            store_id=request.store_id,
            approver=request.approver,
            decision=request.decision,
            reason=request.reason,
            notes=request.notes,
            status=request.decision,
        )
        existing = self._repository.get(record.request_id)
        if existing is not None:
            if existing == record:
                return await self._response(existing)
            raise ValueError("An approval decision already exists for this request ID")

        self._repository.save(record)
        return await self._response(record)

    def get(self, request_id: str) -> ApprovalDecisionRecord | None:
        return self._repository.get(request_id)

    async def _response(self, record: ApprovalDecisionRecord) -> dict[str, object]:
        delegation = await self._submit_post_approval_task(record)
        return {"status": "ok", "approval": _approval_payload(record), "delegation": delegation}

    async def _submit_post_approval_task(
        self, record: ApprovalDecisionRecord
    ) -> dict[str, object] | None:
        if record.decision != "approved" or not self._settings.approval_delegation_enabled:
            return None
        task = DelegationTask(
            source_agent=self._settings.approval_delegation_source_agent,
            target_agent=self._settings.approval_delegation_target_agent,
            intent=self._settings.approval_delegation_intent,
            payload={
                "approval_request_id": record.request_id,
                "agent_name": record.agent_name,
                "store_id": record.store_id,
                "approver": record.approver,
                "approval_reason": record.reason,
                "approval_notes": record.notes,
                "planning_only": True,
                "dispatch_authorized": False,
            },
            correlation_id=record.request_id,
            idempotency_key=(
                f"approval:{record.request_id}:{self._settings.approval_delegation_target_agent}:"
                f"{self._settings.approval_delegation_intent}"
            ),
            data_classification="confidential",
            auth_mode="app",
        )
        decision = evaluate_delegation_policy(task, self._policy_subagents(task))
        if not decision.allowed:
            self._message_bus.publish(
                "approval.delegation.rejected",
                {
                    "request_id": record.request_id,
                    "target_agent": task.target_agent,
                    "intent": task.intent,
                    "reason_code": decision.reason_code,
                },
            )
            return {
                **delegation_status_payload(
                    type(
                        "RejectedRecord",
                        (),
                        {
                            "task": task,
                            "status": "rejected",
                            "failure_code": decision.reason_code,
                            "result": None,
                        },
                    )()
                ),
                "task_id": task.task_id,
            }

        task_record = await self._task_bus.submit(task)
        payload = delegation_status_payload(task_record)
        self._message_bus.publish("approval.delegation.created", payload)
        return payload

    def _policy_subagents(self, task: DelegationTask) -> list[SubagentConfig]:
        """Resolve stable logical target names against catalog-qualified names."""
        if any(agent.name == task.target_agent for agent in self._subagents):
            return self._subagents
        matches = [
            agent
            for agent in self._subagents
            if _logical_agent_name(agent.name) == _logical_agent_name(task.target_agent)
        ]
        if len(matches) != 1:
            return self._subagents
        match = matches[0]
        return [
            replace(match, name=task.target_agent),
            *[agent for agent in self._subagents if agent is not match],
        ]


def _logical_agent_name(name: str) -> str:
    """Normalize catalog prefixes and role suffixes for configured agent names."""
    value = name.lower().replace("_", "-")
    for prefix in ("gmai-app-agent-", "gmai-agent-"):
        value = value.removeprefix(prefix)
    if value.endswith("-agent"):
        value = value.removesuffix("-agent")
    return value


def approval_payload(record: ApprovalDecisionRecord) -> dict[str, object]:
    """Return the public approval representation."""
    return _approval_payload(record)


def _approval_payload(record: ApprovalDecisionRecord) -> dict[str, object]:
    return {
        "request_id": record.request_id,
        "agent_name": record.agent_name,
        "store_id": record.store_id,
        "approver": record.approver,
        "decision": record.decision,
        "reason": record.reason,
        "notes": record.notes,
        "status": record.status,
    }


def delegation_status_payload(record: Any) -> dict[str, object]:
    """Return user-safe delegation status without exposing task input payloads."""
    result = record.result
    return {
        "task_id": record.task.task_id,
        "correlation_id": record.task.correlation_id,
        "source_agent": record.task.source_agent,
        "target_agent": record.task.target_agent,
        "intent": record.task.intent,
        "status": record.status,
        "attempt": record.task.attempt,
        "max_attempts": record.task.max_attempts,
        "failure_code": record.failure_code or (result.error_code if result else None),
        "completed": result is not None,
    }
