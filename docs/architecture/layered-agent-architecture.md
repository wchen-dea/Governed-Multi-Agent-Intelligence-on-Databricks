# Layered Agentic Architecture

## Purpose

The backend separates request delivery, agent use cases, business concepts,
external-system adapters, and dependency composition. This keeps orchestration
logic independent of concrete Databricks, MLflow, persistence, and messaging
implementations.

## Package Structure

```text
src/aiserver/
├── api/                       # HTTP and AgentServer delivery handlers
├── application/               # Agent use cases and application ports
│   ├── adapters/               # Concrete tool adapter registry and strategies
│   ├── auth/                  # Runtime identity and policy evaluation
│   ├── delegation/            # Agent handoff and durable task processing
│   ├── guardrails/            # Input and response governance controls
│   ├── orchestration/         # Routing, tool assembly, and model selection
│   └── ports/                 # Execution, routing, persistence, and adapter interfaces
├── bootstrap/                 # Composition root for concrete dependencies
├── config/                    # Dependency-neutral environment settings
├── contracts/                 # Framework-neutral execution and cross-layer contracts
├── infrastructure/            # Concrete external-system adapters
│   ├── databricks/            # Lakebase OAuth and PostgreSQL connectivity
│   ├── messaging/             # Lifecycle event publishers
│   ├── observability/         # MLflow trace integration
│   └── persistence/           # Lakebase memory and UC task persistence
```

## Dependency Direction

```mermaid
flowchart LR
    API[api] --> APP[application]
    API --> BOOT[bootstrap]
    APP --> DOMAIN[contracts and config]
    APP --> PORTS[application ports]
    ADAPTERS[application adapters] --> PORTS
    APP --> ADAPTERS
    INFRA[infrastructure] --> PORTS
    INFRA --> DOMAIN
    BOOT --> APP
    BOOT --> INFRA
```

`application` must not import `api`, `bootstrap`, or `infrastructure`.
Application use cases depend on ports such as `MessageBus`, `ConversationMemory`,
`TraceMetadataUpdater`, `AgentExecutionService`, `AgentRunner`,
`RouteAffinityStore`, `ToolAdapter`, and `ToolRegistry`. Execution requests,
results, stream events, and route-affinity records are defined in
`aiserver.contracts.execution` without FastAPI, MLflow Agent Server, or Starlette
types. The concrete tool adapter registry is application code: it resolves direct
function-tool strategies without coupling orchestration to a particular subagent
kind. The composition root in `aiserver.bootstrap.container` constructs concrete
MLflow, messaging, and persistence implementations and injects them into those use
cases.

`contracts` and `config` are foundational and must not import higher layers.
`infrastructure` can implement application ports but must not import `api` or
`bootstrap`.

## Architectural Verification

`tests/test_layer_isolation.py` statically checks these import boundaries. Run
the full validation suite with:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```