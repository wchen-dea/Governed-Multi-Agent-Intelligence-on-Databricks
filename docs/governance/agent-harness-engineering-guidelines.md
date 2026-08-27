# Agent Harness Engineering Guidelines

Hands-on conventions for the runtime scaffolding that executes, governs, and observes the agent — distinct from [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md) (what to tell the model) and [context-engineering-guidelines.md](context-engineering-guidelines.md) (what information to include). Harness engineering covers request handling, typed execution contracts, delegation/handoff bounds, model selection, and lifecycle observability.

## Scope

The harness is everything in `src/aiserver/api/` and `src/aiserver/services/` that runs independently of any single model call: request lifecycle, dependency composition, deterministic policy/guardrail enforcement points, bounded agent-to-agent delegation, task execution, and audit/tracing plumbing.

## Implemented Mechanisms and Rules

### 1. Layered request pipeline

- Source: `src/aiserver/api/handlers.py` (`@invoke`/`@stream`), `src/aiserver/api/dependencies.py` (DI wiring).
- Rule: request-time policy (`policy_service.py`) runs before any tool call; response-time guardrails (`guardrails_service.py`) run after the model produces output. Do not add ad hoc checks inside handlers — add them to the appropriate service so both invoke and stream paths get the same enforcement.
- Rule: keep handler functions thin (parse/normalize input, call services, shape output). Business/policy logic belongs in a `*_service.py` module (see naming convention documented in `src/aiserver/services/__init__.py`).

### 2. Typed execution contracts

- Source: `src/aiserver/domain/execution_contracts.py` (`RoutePlan`, `ToolExecutionResult`, `ResponseEnvelope`).
- Rule: any new tool-execution outcome must be representable as a `ToolExecutionResult` (status, latency, attempt count, auth mode, evidence ids) — never pass ad hoc dicts between routing, execution, and guardrail layers. This is what keeps traces, lifecycle events, and guardrail checks consistent across subagent types.
- Rule: `ExecutionStatus` is a closed literal (`succeeded`, `failed`, `blocked`, `truncated`). Map new failure modes onto one of these instead of inventing new statuses ad hoc.

### 3. Deterministic route planning before model orchestration

- Source: `route_planner.py` (`build_route_plan`, `MIN_ROUTE_CONFIDENCE`).
- Rule: route plans are conservative and inspectable — compute candidates and confidence deterministically before handing off to model-driven tool selection. Do not replace this with a pure model-decides-everything approach; the deterministic pre-check is what makes `route_plan.requires_evidence` and persona/auth filtering enforceable pre-execution.

### 4. Bounded agent-to-agent delegation

- Source: `agent_handoff_service.py`, `agent_delegation_policy_service.py`, `agent_task_bus.py`, `agent_task_worker.py`, `domain/agent_messages.py`.
- Rule: delegation is deny-by-default. A subagent only becomes an eligible delegation target when it has `accepts_delegations_from` including `"orchestrator"`, a registered executor, and non-empty `allowed_task_intents`. Do not bypass `build_delegation_tool`'s eligibility filter to wire a new delegation path.
- Rule: every delegated task carries a `correlation_id` and a deterministic `idempotency_key` (`{correlation_id}:{target_agent}:{intent}:{payload}`). Preserve this pattern for new delegation payload shapes so retried/duplicate delegations settle idempotently.
- Rule: delegation failures return a structured `DELEGATION_FAILED category=... code=...` string, not a raw exception or empty string — this is what lets the orchestrator prompt reason about failure category (see [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md)).

### 5. Deterministic model selection per task type

- Source: `model_routing_service.py` (`ModelSelection`, `_REASONING_TERMS`, `_SYNTHESIS_TERMS`).
- Rule: model choice is a deterministic, reason-coded decision (`ModelSelection.reason`), not implicit. When adding a new task-type heuristic, add it as a term set + reason code, not an inline conditional scattered in handlers.

### 6. Lifecycle audit and message bus

- Source: `message_bus.py` (structured logging, noop, Kafka, RabbitMQ, UC table backends), `MESSAGE_BUS_*` settings.
- Rule: every service that changes execution/delegation/guardrail outcomes should be able to publish a lifecycle event through the injected `MessageBus`, not write directly to a specific backend (Kafka/RabbitMQ/UC). This keeps backend selection swappable via config only (`MESSAGE_BUS_BACKEND`).
- Rule: respect `MESSAGE_BUS_FAIL_OPEN` semantics — audit/event publishing failures must not block the user-facing response unless the project has explicitly decided otherwise for a given event type.

### 7. Auth-mode-aware execution

- Source: `runtime_auth_service.py`, subagent `auth_mode` field (`app` vs `obo`).
- Rule: a tool's availability and delegation eligibility must be derived from the request-scoped auth context, not assumed. Never hardcode an auth mode inside a tool wrapper; read it from `SubagentConfig.auth_mode` and the current request identity context.

### 8. MLflow tracing as harness observability, not prompt content

- Source: `mlflow.update_current_trace` calls in `orchestrator_service.py`.
- Rule: trace metadata (routing decisions, subagent names, auth mode) is attached to the MLflow trace, never embedded into the model-visible prompt. Keep observability data and model context separate.

## What Not to Do

- Do not let handler code call a subagent's tool directly — always go through the orchestrator/tool-construction path so policy, guardrails, and tracing wrap the call.
- Do not add a new delegation target without both an `allowed_task_intents` entry and an executor registered in `executors`; an eligible-looking config with no executor will silently produce `delegation_target_unavailable`.
- Do not swallow tool execution errors before they reach `ToolExecutionResult`/lifecycle events — downstream guardrails and audits depend on accurate status codes.
- Do not couple model selection or delegation eligibility to prompt text; keep these decisions in typed config and service logic so they are testable without invoking the model.

## Validation After Any Harness Change

```bash
uv run pytest tests/test_agent_delegation.py tests/test_agent_task_bus.py tests/test_delegation_status.py \
  tests/test_execution_contracts.py tests/test_model_routing_service.py tests/test_orchestrator_service.py \
  tests/test_policy_service.py tests/test_route_planner.py tests/test_runtime_auth.py \
  tests/test_message_bus_backends.py tests/test_message_bus_integration.py -q
```

## Possible Improvements to Level Up

- **Retry/backoff policy for delegation and tool calls.** `ToolExecutionResult.attempt_count` exists but there's no documented, centralized retry/backoff policy for transient failures (MCP timeouts, Lakebase connection errors); formalizing one would reduce ad hoc retry logic per subagent type.
- **Circuit breaker for unhealthy subagents.** MCP health caching exists (`_MCP_HEALTH_CACHE`), but there's no equivalent breaker for Genie/Lakebase/app subagents; extending the pattern would give consistent fast-fail behavior across all subagent types.
- **Idempotency conflict testing.** Add tests that submit two delegation tasks with the same `idempotency_key` concurrently to confirm the task bus settles them consistently, not just sequentially.
- **Load/backpressure handling on the task bus.** `agent_task_bus.py`/`agent_task_worker.py` bound a single worker per handoff; document and test behavior under many concurrent delegations (queueing, rejection, or backpressure signal) before this becomes a production incident.
- **Model routing evaluation.** `model_routing_service.py`'s term-set heuristics (`_REASONING_TERMS`, `_SYNTHESIS_TERMS`) aren't currently covered by the KPI release gate; add model-selection accuracy as an explicit eval dimension so heuristic changes are measured, not just unit-tested.
- **Unified harness dashboard.** Lifecycle events already flow through `MessageBus` backends; adding a single operational dashboard (latency, failure category, delegation success rate per subagent) would close the loop between audit events and actionable observability.

## Related Documents

- [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md)
- [context-engineering-guidelines.md](context-engineering-guidelines.md)
- [../adrs/0001-layered-backend-architecture.md](../adrs/0001-layered-backend-architecture.md)
- [../adrs/0004-lifecycle-message-bus.md](../adrs/0004-lifecycle-message-bus.md)
- [../architecture/backend-framework-design.md](../architecture/backend-framework-design.md)
- [../../.claude/skills/runtime-routing/SKILL.md](../../.claude/skills/runtime-routing/SKILL.md)
