# ADR 0001: Use Layered Backend Package Structure

## Status

Accepted

## Context

The backend started as a small set of top-level modules. As the application grew (hybrid auth, orchestration services, DI, message bus, evaluation gate), responsibilities became harder to discover and maintain in a flat layout.

## Decision

Adopt a four-layer package structure under `src/aiserver/`:

| Layer | Path | Responsibility |
|-------|------|---------------|
| `api` | `src/aiserver/api/` | HTTP handlers, MLflow Agent Server bootstrap, dependency composition root |
| `services` | `src/aiserver/services/` | Business logic — orchestration, policy, guardrails, auth, message bus |
| `domain` | `src/aiserver/domain/` | Typed domain models, subagent config validation, per-environment registries |
| `shared` | `src/aiserver/shared/` | Cross-cutting utilities — settings, identity helpers, request normalization |

Dependencies flow downward only: `api → services → domain → shared`. No upward imports.

## Alternatives Considered

- Keep a flat backend module layout and rely on naming conventions only.
- Split into separate deployable microservices instead of one layered codebase.
- Use a framework-imposed structure (e.g., Django apps).

## Consequences

### Positive

- Clear separation of concerns and ownership boundaries.
- Better testability — services are unit-testable without HTTP layer.
- Easier onboarding and code navigation for new contributors.
- Each layer can be reasoned about independently.

### Trade-offs

- More files and imports to manage.
- Requires discipline to preserve layer boundaries (no services importing from api).

## Implementation Notes

Current file inventory:

```
src/aiserver/
├── api/
│   ├── server.py                          # MLflow AgentServer bootstrap, hosted-port resolution, in-process UI serving
│   ├── handlers.py                        # @invoke / @stream pipeline stages
│   └── dependencies.py                    # Composition root
├── services/
│   ├── orchestrator_service.py            # Tools, MCP connectivity, agent assembly
│   ├── runtime_auth_service.py            # Request-scoped hybrid app/OBO authorization state
│   ├── policy_service.py                  # Governed routing policy evaluation
│   ├── guardrails_service.py              # Response guardrails for governed/sensitive outputs
│   ├── route_planner.py                   # Conservative pre-model route plans
│   ├── model_routing_service.py           # Per-task-type model selection
│   ├── agent_handoff_service.py           # Native agent handoffs as function tools
│   ├── agent_delegation_policy_service.py # Deny-by-default agent-to-agent delegation policy
│   ├── agent_task_bus.py                  # Durable task bus (in-memory + UC Delta-backed)
│   ├── agent_task_worker.py               # Bounded worker executing delegated tasks
│   ├── memory_service.py                  # Conversation/persona memory (Lakebase-backed, no-op fallback)
│   ├── message_bus.py                     # Lifecycle event publishing (log, async, Kafka, RabbitMQ, UC audit)
│   └── interfaces.py                      # Protocol-based contracts
├── domain/
│   ├── subagent_config.py                 # SubagentConfig dataclass + validation
│   ├── agent_messages.py                  # Typed contracts for agent-to-agent delegation
│   ├── execution_contracts.py             # Shared routing/execution/response-policy contracts
│   ├── subagents.dev.json
│   ├── subagents.qa.json
│   ├── subagents.stg.json
│   └── subagents.prd.json
└── shared/
    ├── settings.py                        # AppSettings from env vars
    ├── runtime_utils.py                   # Identity, MCP URL, stream normalization
    ├── request_utils.py                   # to_messages, extract_mcp_errors
    ├── lakebase_client.py                 # OAuth-authenticated Lakebase Postgres connections
    └── logging_config.py
```
