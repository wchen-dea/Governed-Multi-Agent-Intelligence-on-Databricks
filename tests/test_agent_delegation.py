"""Tests for bounded agent-to-agent delegation primitives."""

import asyncio

from backend.domain.agent_messages import DelegationTask
from backend.domain.subagent_config import SubagentConfig
from backend.services.agent_delegation_policy_service import evaluate_delegation_policy
from backend.services.agent_handoff_service import build_delegation_tool, execute_delegation
from backend.services.agent_task_bus import InMemoryAgentTaskBus
from backend.services.agent_task_worker import AgentTaskWorker


class RecordingBus:
    def __init__(self) -> None:
        self.events: list[str] = []

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        del payload
        self.events.append(event_type)


def _agents() -> list[SubagentConfig]:
    return [
        SubagentConfig(
            name="operations_coordinator",
            kind="app",
            endpoint="operations",
            description="coordinates operations work",
            can_delegate_to=("lakebase_ods_agent",),
            max_delegation_depth=1,
        ),
        SubagentConfig(
            name="lakebase_ods_agent",
            kind="lakebase",
            project_id="ore",
            branch_id="production",
            database="operationaldatastore",
            pg_host="lakebase.example.com",
            endpoint_id="primary",
            description="appointment data",
            accepts_delegations_from=("operations_coordinator",),
            allowed_task_intents=("appointment_summary",),
        ),
    ]


def _task(**overrides: object) -> DelegationTask:
    values: dict[str, object] = {
        "source_agent": "operations_coordinator",
        "target_agent": "lakebase_ods_agent",
        "intent": "appointment_summary",
        "payload": {"date": "latest"},
        "correlation_id": "corr-1",
        "idempotency_key": "idem-1",
    }
    values.update(overrides)
    return DelegationTask(**values)  # type: ignore[arg-type]


def test_delegation_policy_is_deny_by_default_and_allows_explicit_pair():
    assert evaluate_delegation_policy(_task(), _agents()).allowed is True
    rejected = evaluate_delegation_policy(_task(intent="sales_summary"), _agents())
    assert rejected.reason_code == "intent_not_allowed"


def test_delegation_task_rejects_loops_and_obo():
    try:
        _task(ancestry=("lakebase_ods_agent",))
    except ValueError as exc:
        assert "loop" in str(exc)
    else:
        raise AssertionError("Expected loop validation failure")

    try:
        _task(auth_mode="obo")
    except ValueError as exc:
        assert "app auth only" in str(exc)
    else:
        raise AssertionError("Expected OBO delegation rejection")


def test_subagent_config_rejects_invalid_delegation_lists():
    try:
        SubagentConfig.from_dict(
            {
                "name": "invalid",
                "type": "app",
                "endpoint": "invalid",
                "description": "invalid",
                "data_classification": "internal",
                "owner": "platform",
                "freshness_sla": "1h",
                "allowed_personas": ["manager"],
                "requires_evidence": False,
                "can_delegate_to": "lakebase_ods_agent",
            }
        )
    except ValueError as exc:
        assert "can_delegate_to must be a list of strings" in str(exc)
    else:
        raise AssertionError("Expected delegation list validation failure")


def test_task_bus_is_idempotent_and_dead_letters_after_retry_budget():
    async def run() -> None:
        task_bus = InMemoryAgentTaskBus()
        task = _task(max_attempts=2)
        assert (await task_bus.submit(task)).task.task_id == task.task_id
        assert (await task_bus.submit(_task(task_id="different"))).task.task_id == task.task_id
        first = (await task_bus.claim("worker"))[0]
        assert first.task.attempt == 1
        assert (await task_bus.fail(task.task_id, "worker", "RuntimeError")).status == "pending"
        second = (await task_bus.claim("worker"))[0]
        assert second.task.attempt == 2
        assert (await task_bus.fail(task.task_id, "worker", "RuntimeError")).status == "dead_letter"

    asyncio.run(run())


def test_worker_executes_allowed_task_and_publishes_lifecycle_events():
    async def run() -> None:
        task_bus = InMemoryAgentTaskBus()
        audit_bus = RecordingBus()
        task = _task()
        await task_bus.submit(task)

        async def execute(received: DelegationTask) -> dict[str, object]:
            return {"target": received.target_agent, "count": 0}

        worker = AgentTaskWorker("worker-1", task_bus, _agents(), execute, audit_bus)
        assert await worker.run_once() == 1
        record = await task_bus.get(task.task_id)
        assert record is not None and record.status == "succeeded"
        assert record.result is not None and record.result.output == {"target": "lakebase_ods_agent", "count": 0}
        assert audit_bus.events == ["delegation.task.claimed", "delegation.task.completed"]

    asyncio.run(run())


def test_worker_loop_processes_task_until_executor_signals_shutdown():
    async def run() -> None:
        task_bus = InMemoryAgentTaskBus()
        audit_bus = RecordingBus()
        stop_event = asyncio.Event()
        task = _task()
        await task_bus.submit(task)

        async def execute(received: DelegationTask) -> dict[str, object]:
            stop_event.set()
            return {"target": received.target_agent}

        worker = AgentTaskWorker("worker-loop", task_bus, _agents(), execute, audit_bus)
        await worker.run_forever(stop_event, poll_seconds=0.1)

        record = await task_bus.get(task.task_id)
        assert record is not None and record.status == "succeeded"

    asyncio.run(run())


def test_native_handoff_executes_only_explicit_orchestrator_target():
    async def run() -> None:
        task_bus = InMemoryAgentTaskBus()
        audit_bus = RecordingBus()
        target = _agents()[1]
        target = SubagentConfig(
            **{
                **target.__dict__,
                "accepts_delegations_from": ("orchestrator",),
                "allowed_task_intents": ("appointment_summary",),
            }
        )

        async def execute(payload: dict[str, object]) -> dict[str, object]:
            return {"result": f"appointments={payload['sql_query']}"}

        tool = build_delegation_tool(
            task_bus=task_bus,
            subagents=[target],
            executors={"lakebase_ods_agent": execute},
            message_bus=audit_bus,
            correlation_id="corr-1",
        )
        assert tool is not None and tool.name == "delegate_to_agent"
        result = await execute_delegation(
            task_bus=task_bus,
            subagents=[target],
            executors={"lakebase_ods_agent": execute},
            message_bus=audit_bus,
            correlation_id="corr-1",
            target_agent="lakebase_ods_agent",
            intent="appointment_summary",
            sql_query="SELECT 1",
        )

        assert result == "appointments=SELECT 1"
        assert audit_bus.events == ["delegation.task.claimed", "delegation.task.completed"]

    asyncio.run(run())