"""Bounded worker that executes one agent-delegation task at a time."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from backend.domain.agent_messages import DelegationResult, DelegationTask
from backend.domain.subagent_config import SubagentConfig
from backend.services.agent_delegation_policy_service import evaluate_delegation_policy
from backend.services.interfaces import AgentTaskBus, MessageBus


class AgentTaskWorker:
    """Claim, policy-check, execute, and settle delegated app-auth tasks."""

    def __init__(
        self,
        worker_id: str,
        task_bus: AgentTaskBus,
        subagents: list[SubagentConfig],
        executor: Callable[[DelegationTask], Awaitable[dict[str, Any]]],
        message_bus: MessageBus,
    ) -> None:
        self._worker_id = worker_id
        self._task_bus = task_bus
        self._subagents = subagents
        self._executor = executor
        self._message_bus = message_bus

    async def run_once(self) -> int:
        """Process one available task and return the number of claimed tasks."""
        claimed = await self._task_bus.claim(self._worker_id)
        for record in claimed:
            task = record.task
            self._message_bus.publish(
                "delegation.task.claimed",
                {"task_id": task.task_id, "correlation_id": task.correlation_id},
            )
            decision = evaluate_delegation_policy(task, self._subagents)
            if not decision.allowed:
                result = DelegationResult(
                    task_id=task.task_id,
                    correlation_id=task.correlation_id,
                    status="rejected",
                    error_code=decision.reason_code,
                )
                await self._task_bus.complete(result, self._worker_id)
                self._message_bus.publish(
                    "delegation.policy.rejected",
                    {"task_id": task.task_id, "reason_code": decision.reason_code},
                )
                continue
            await self._task_bus.mark_running(task.task_id, self._worker_id)
            try:
                output = await self._executor(task)
            except Exception as exc:
                record = await self._task_bus.fail(
                    task.task_id, self._worker_id, type(exc).__name__
                )
                event_type = (
                    "delegation.task.dead_lettered"
                    if record.status == "dead_letter"
                    else "delegation.task.failed"
                )
                self._message_bus.publish(
                    event_type, {"task_id": task.task_id, "error_type": type(exc).__name__}
                )
                continue
            result = DelegationResult(
                task_id=task.task_id,
                correlation_id=task.correlation_id,
                status="succeeded",
                output=output,
            )
            await self._task_bus.complete(result, self._worker_id)
            self._message_bus.publish(
                "delegation.task.completed",
                {"task_id": task.task_id, "correlation_id": task.correlation_id},
            )
        return len(claimed)

    async def run_forever(self, stop_event: asyncio.Event, poll_seconds: float = 1.0) -> None:
        """Continuously claim work until application shutdown signals cancellation."""
        while not stop_event.is_set():
            processed = await self.run_once()
            if processed == 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=max(poll_seconds, 0.1))
                except TimeoutError:
                    continue
