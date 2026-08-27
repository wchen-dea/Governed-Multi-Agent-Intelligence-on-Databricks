# ADR 0003: Centralize Dependency Composition in API Layer

## Status

Accepted

## Context

As services gained protocol-based dependencies (runtime auth, orchestration, message bus, policy, guardrails), ad hoc wiring in multiple files increased coupling and made environment-specific overrides harder to reason about.

## Decision

Use `src/aiserver/api/dependencies.py` as the single composition root. This module builds three nested dependency containers and exposes a single entrypoint for handler consumption:

```
AppDependencyContainer
├── OrchestratorDependencies
│   ├── trace_metadata_updater: TraceMetadataUpdater
│   ├── function_tool_wrapper: FunctionToolWrapper
│   ├── mcp_server_factory: McpServerFactory
│   └── message_bus: MessageBus
├── RuntimeAuthDependencies
│   ├── identity_context_provider: IdentityContextProvider
│   ├── session_id_provider: SessionIdProvider
│   ├── trace_metadata_updater: TraceMetadataUpdater
│   ├── obo_client_factory: OboClientFactory
│   ├── subagent_tools_builder: SubagentToolsBuilder
│   ├── mcp_servers_builder: McpServersBuilder
│   ├── lakebase_tools_builder: LakebaseToolsBuilder
│   ├── policy_context_builder
│   ├── subagent_policy_filter
│   ├── message_bus: MessageBus
│   └── delegation_task_bus: AgentTaskBus | None
├── HandlerDependencies
│   ├── runtime_auth_builder
│   ├── mcp_connector
│   ├── orchestrator_factory
│   ├── guardrails_evaluator
│   ├── input_guardrails_evaluator
│   ├── message_bus: MessageBus
│   └── memory: ConversationMemory
└── delegation_task_bus: AgentTaskBus
```

Handlers receive only `HandlerDependencies` — a flat, frozen dataclass of composed callables.

## Alternatives Considered

- Wire dependencies inline inside request handlers.
- Use implicit module globals for service singletons.
- Use a DI framework (e.g., dependency-injector, inject).

## Consequences

### Positive

- Single, explicit place to wire all application dependencies.
- Cleaner service modules focused on behavior rather than construction.
- Better integration testing — dependency containers can be overridden at test boundaries.
- Protocol-based contracts (in `interfaces.py`) decouple implementations from consumers.

### Trade-offs

- Composition root can grow if not kept organized.
- Requires careful typing at boundaries (callables, protocols).
- Module-level construction means composition happens at import time.

## Implementation Notes

- Composition root: [src/aiserver/api/dependencies.py](../../src/aiserver/api/dependencies.py) (`build_dependency_container`, `get_handler_dependencies`)
- Protocol contracts: [src/aiserver/services/interfaces.py](../../src/aiserver/services/interfaces.py)
- Handler consumption: [src/aiserver/api/handlers.py](../../src/aiserver/api/handlers.py) (`HANDLER_DEPS = get_handler_dependencies()`)
- All containers use frozen dataclasses — no runtime mutation after construction.
