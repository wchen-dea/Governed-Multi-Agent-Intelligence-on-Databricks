"""Expose bounded native agent handoffs as OpenAI function tools."""

from collections.abc import Awaitable, Callable
from typing import Any

from agents import function_tool

from aiserver.domain.agent_messages import DelegationTask
from aiserver.domain.subagent_config import SubagentConfig
from aiserver.services.agent_task_worker import AgentTaskWorker
from aiserver.services.interfaces import AgentTaskBus, MessageBus

DelegationExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def execute_delegation(
    *,
    task_bus: AgentTaskBus,
    subagents: list[SubagentConfig],
    executors: dict[str, DelegationExecutor],
    message_bus: MessageBus,
    correlation_id: str,
    target_agent: str,
    intent: str,
    sql_query: str,
) -> str:
    """Submit and synchronously settle one bounded app-auth delegation task."""
    task = DelegationTask(
        source_agent="orchestrator",
        target_agent=target_agent,
        intent=intent,
        payload={"sql_query": sql_query},
        correlation_id=correlation_id,
        idempotency_key=f"{correlation_id}:{target_agent}:{intent}:{sql_query}",
    )
    record = await task_bus.submit(task)

    async def execute(task_to_execute: DelegationTask) -> dict[str, Any]:
        executor = executors.get(task_to_execute.target_agent)
        if executor is None:
            raise ValueError("delegation_target_unavailable")
        return await executor(task_to_execute.payload)

    worker = AgentTaskWorker(
        worker_id=f"handoff:{correlation_id}",
        task_bus=task_bus,
        subagents=subagents,
        executor=execute,
        message_bus=message_bus,
    )
    await worker.run_once()
    final_record = await task_bus.get(record.task.task_id)
    if final_record is None:
        return "DELEGATION_FAILED category=execution. Delegated task state was not found."
    if final_record.result and final_record.result.output is not None:
        return str(final_record.result.output.get("result", final_record.result.output))
    failure_code = final_record.failure_code or (
        final_record.result.error_code if final_record.result else "unknown"
    )
    return f"DELEGATION_FAILED category={final_record.status} code={failure_code}."


def build_delegation_tool(
    *,
    task_bus: AgentTaskBus,
    subagents: list[SubagentConfig],
    executors: dict[str, DelegationExecutor],
    message_bus: MessageBus,
    correlation_id: str,
) -> Any | None:
    """Build the native handoff tool when an approved target is executable."""
    eligible = [
        subagent
        for subagent in subagents
        if "orchestrator" in subagent.accepts_delegations_from
        and subagent.name in executors
        and subagent.allowed_task_intents
    ]
    if not eligible:
        return None

    async def delegate_to_agent(
        target_agent: str,
        intent: str,
        sql_query: str,
    ) -> str:
        """Delegate one approved app-auth task to a configured target agent.

        Args:
            target_agent: Approved target agent name.
            intent: Approved target task intent.
            sql_query: Read-only SQL required by the approved Lakebase target.
        """
        return await execute_delegation(
            task_bus=task_bus,
            subagents=subagents,
            executors=executors,
            message_bus=message_bus,
            correlation_id=correlation_id,
            target_agent=target_agent,
            intent=intent,
            sql_query=sql_query,
        )

    return function_tool(
        delegate_to_agent,
        name_override="delegate_to_agent",
        description_override=(
            "Delegate an approved app-auth task to another configured agent. "
            "Use only when the target and intent are explicitly configured."
        ),
    )
