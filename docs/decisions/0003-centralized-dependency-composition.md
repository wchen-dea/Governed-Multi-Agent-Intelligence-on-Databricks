# ADR 0003: Centralize Dependency Composition in Bootstrap

## Status

Accepted

## Context

As services gained protocol-based dependencies (runtime auth, orchestration, message bus, policy, guardrails), ad hoc wiring in multiple files increased coupling and made environment-specific overrides harder to reason about.

## Decision

Use `src/aiserver/bootstrap/container.py` as the single composition root. This
module builds infrastructure adapters and application services, then exposes a
single execution-service entrypoint to delivery handlers:

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
├── GovernedAgentService
│   └── GovernedAgentServiceDependencies
│       ├── runtime auth, routing, model selection, and orchestration factories
│       ├── input and response guardrails
│       ├── AgentRunner
│       ├── ConversationMemory
│       └── MessageBus
├── app_client: AsyncDatabricksOpenAI
├── message_bus: MessageBus
└── delegation_task_bus: AgentTaskBus
```

MLflow handlers translate delivery contracts and call `GovernedAgentService`;
they do not receive a parallel dependency container or own execution policy.

## Alternatives Considered

- Wire dependencies inline inside request handlers.
- Use implicit module globals for service singletons.
- Use a DI framework (e.g., dependency-injector, inject).

## Consequences

### Positive

- Single, explicit place to wire all application dependencies.
- Cleaner service modules focused on behavior rather than construction.
- Better integration testing — dependency containers can be overridden at test boundaries.
- Protocol-based contracts in `application/ports/` decouple implementations from consumers.

### Trade-offs

- Composition root can grow if not kept organized.
- Requires careful typing at boundaries (callables, protocols).
- Module-level construction means composition happens at import time.

## Implementation Notes

- Composition root: [src/aiserver/bootstrap/container.py](../../src/aiserver/bootstrap/container.py) (`build_dependency_container`, `get_execution_service`)
- Protocol contracts: [src/aiserver/application/ports/](../../src/aiserver/application/ports)
- Concrete direct-tool adapters and default registry: [src/aiserver/application/adapters/tools.py](../../src/aiserver/application/adapters/tools.py)
- Handler consumption: [src/aiserver/api/invocations.py](../../src/aiserver/api/invocations.py) (framework translation into `GovernedExecutionRequest`)
- All containers use frozen dataclasses — no runtime mutation after construction.

The default adapter registry is an application-level implementation of the `ToolAdapter` and `ToolRegistry` ports. `build_subagent_tools()` uses it for direct serving-endpoint and App function tools; MCP server construction, Lakebase tool construction, and task-bus delegation remain dedicated runtime paths.
