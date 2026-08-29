# Backend Framework and Design

## Overview

The backend is a multi-agent orchestration runtime built on MLflow Agent Server (`mlflow.genai.agent_server`). It accepts Responses API requests, routes them through a governed pipeline of policy checks, tool assembly, LLM orchestration, and response guardrails, then returns structured output.

The runtime is deployed as a Databricks App and uses the OpenAI Agents SDK (`openai-agents`) for orchestration, with Databricks-native integrations for Genie spaces, AI Search (MCP), model serving endpoints, and Lakebase (PostgreSQL).

## Package Structure

```
src/aiserver/
├── api/                  ← HTTP delivery layer
│   ├── server.py         # MLflow AgentServer bootstrap
│   └── invocations.py   # @invoke / @stream request pipeline
├── application/          ← Request-time use cases and ports
│   ├── auth/             # Context and policy
│   ├── delegation/       # Handoff, policy, worker
│   ├── guardrails/       # Deterministic checks
│   ├── orchestration/    # Agent assembly, routing, model selection
│   ├── ports/            # Capability-specific protocols
│   └── runtime/          # Identity, requests, streaming
├── bootstrap/            ← Dependency composition root
│   └── container.py
├── config/               ← Environment settings
│   └── settings.py
├── contracts/            ← Typed cross-layer contracts and registries
│   ├── subagents.py      # SubagentConfig dataclass, validation, loading
│   ├── delegation.py     # Typed delegation contracts
│   ├── responses.py      # Routing, execution, response contracts
│   └── subagents.{env}.json      # Per-environment subagent registries
└── infrastructure/       ← Databricks, messaging, observability, persistence adapters
    ├── databricks/lakebase.py
    ├── messaging/bus.py
    ├── observability/{logging,tracing}.py
    └── persistence/{memory,tasks}.py
```

## Layer Responsibilities

| Layer | Responsibility | Depends On |
|-------|---------------|------------|
| **api** | HTTP lifecycle and request dispatch | application, bootstrap |
| **application** | Orchestration, policy, auth, guardrails, and request helpers | contracts, config, ports |
| **bootstrap** | Dependency composition | application, infrastructure |
| **contracts** | Typed execution, delegation, and subagent registry contracts | (no higher layers) |
| **config** | Environment settings | (no higher layers) |
| **infrastructure** | Databricks, messaging, tracing, and persistence adapters | application ports, contracts, config |

Dependencies flow inward: `api -> application -> contracts/config`; infrastructure implements application ports and bootstrap composes concrete dependencies.

## Request Pipeline

Both `@invoke` and `@stream` handlers share a staged pipeline:

```
Request → Prepare → Connect → Execute → Finalize → Response
```

### Stage 1: Prepare

- Resolve request identity (app identity + optional OBO from `x-forwarded-access-token`)
- Evaluate policy rules per subagent (persona, auth mode, data classification, confidence)
- Build `RuntimeAuthContext` with allowed tools, MCP servers, and unavailable reasons
- Normalize input messages to typed format

### Stage 2: Connect

- Connect MCP servers with parallel health checks (TTL-cached)
- Build orchestrator `Agent` instance with instructions, tools, MCP servers, and unavailable-tool warnings
- Select the configured Databricks model deterministically by task type before agent construction
- Publish `request.*.started` lifecycle event

### Stage 3: Execute

- **Invoke**: native `Runner.run()` function/MCP calls return output items
- **Stream**: native `Runner.run_streamed()` calls buffer events, track used subagents, and release user-visible text only after finalization

### Stage 4: Finalize

- Append governed source suffix (citing Genie spaces, freshness SLAs)
- Evaluate response guardrails (evidence, unsafe patterns, low-confidence blocking)
- Publish `response.guardrail.passed` or `response.guardrail.blocked`
- Return response or raise `UserError` on block

## Dependency Injection

The composition root (`bootstrap/container.py`) uses a frozen dataclass container pattern:

```
AppDependencyContainer
├── OrchestratorDependencies   → trace metadata, tool wrappers, MCP factory, message bus
├── RuntimeAuthDependencies    → identity, OBO client, tool/MCP builders, policy filter
└── HandlerDependencies        → composed callables consumed by handlers
```

Services are composed at import time via `build_dependency_container()`. Handlers receive a flat `HandlerDependencies` object — no service locator, no runtime DI framework.

## Subagent Types

| Type | Protocol | Auth Modes | Example |
|------|----------|-----------|---------|
| `genie` | Databricks Genie MCP | app, obo | Sales Insights, CDI Metrics |
| `mcp` | Databricks AI Search MCP | app, obo | Product Index, Flink Support |
| `lakebase` | PostgreSQL (psycopg2 + OAuth) | app | Lakebase ODS |
| `serving_endpoint` | HTTP (model serving) | app, obo | Custom model endpoints |
| `app` | HTTP (Databricks App) | app, obo | External agent apps |

Each subagent is defined in `subagents.{env}.json` with typed metadata: auth mode, data classification, allowed personas, evidence requirements, freshness SLA.

## Policy Enforcement

Request-time policy rules (evaluated per subagent before tool assembly):

| Rule | Blocks When |
|------|------------|
| `persona_required` | No persona set and subagent has persona restrictions |
| `persona_not_allowed` | Active persona not in subagent's `allowed_personas` |
| `obo_identity_required` | `auth_mode=obo` but no forwarded token present |
| `tool_not_requested` | Explicit tool routing miss (when confidence routing is active) |
| `low_confidence_sensitive` | Confidence < 0.75 for confidential/restricted data |

Denied subagents are excluded from tool assembly and reported as unavailable.

## Response Guardrails

Post-execution checks before returning content:

| Check | Blocks When |
|-------|------------|
| Evidence required | `requires_evidence=true` subagent contributed but response lacks `[1]`, `Source:`, or `Citation:` |
| Unsafe patterns | Response contains SSN, credit card, private key, API key, or password patterns |
| Low-confidence sensitive | Hedging language detected for confidential/restricted data context |

Blocked responses raise `UserError` (invoke) or emit a guardrail block message (stream).

## Lifecycle Events

All request stages publish structured events via a pluggable message bus:

```
request.invoke.started → request.invoke.succeeded / request.invoke.failed
request.stream.started → request.stream.succeeded / request.stream.failed
response.guardrail.passed / response.guardrail.blocked
auth.identity.resolved / auth.context.built / auth.trace.metadata.updated
policy.subagent.decision (result: allow | deny)
```

Supported backends: `noop`, `structured_logging`, `kafka`, `rabbitmq`, `uc_table` (Unity Catalog Delta table via SQL Statement API).

Delegation task state is separate from the fail-open lifecycle bus: `AgentTaskBus` persists bounded app-auth handoffs with correlation IDs, idempotency, leases, retries, and dead-letter states. Dev uses Unity Catalog Delta task/event tables and a lifespan-managed worker.

## Auth Model

Hybrid app + on-behalf-of-user (OBO):

- **App identity**: Default. The Databricks App's service principal accesses resources.
- **OBO identity**: When subagent declares `auth_mode=obo` and the request carries `x-forwarded-access-token`. Uses the end-user's Databricks token for downstream calls.

Both identities are resolved per-request in `RuntimeAuthContext`. Tools and MCP servers receive the appropriate client based on their declared auth mode.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `openai-agents` | Agent orchestration (Runner, Agent, tools, streaming) |
| `databricks-openai` | `AsyncDatabricksOpenAI` client for model serving |
| `databricks-agents` | Genie/MCP integration, deployment utilities |
| `mlflow` | Agent Server, tracing, evaluation framework |
| `fastapi` / `uvicorn` | HTTP server underlying Agent Server |
| `psycopg2-binary` | Lakebase PostgreSQL connectivity |

## Configuration

All runtime behavior is driven by environment variables (see `shared/settings.py`):

| Variable | Purpose |
|----------|---------|
| `ORCHESTRATOR_MODEL` | Target-configured foundation model for the orchestrator |
| `MODEL_ROUTING_*` | Deterministic standard, reasoning, and synthesis model routes; dev uses `databricks-gpt-5-6-luna` for standard turns and `databricks-claude-sonnet-5` for reasoning/synthesis turns |
| `AGENT_TASK_*` | UC delegation task store and bounded worker configuration |
| `DATABRICKS_OPENAI_BASE_URL` | Optional AI Gateway override URL |
| `DATABRICKS_OPENAI_TIMEOUT_SECONDS` | Client timeout for gateway-routed calls |
| `MESSAGE_BUS_BACKEND` | Event bus backend selection |
| `SUBAGENTS_CONFIG_PATH` | Override path to subagent registry JSON |
| `DEFAULT_REQUEST_PERSONA` | Fallback persona when none provided |

Per-environment values are managed via Databricks Asset Bundle variables in `targets/{env}.yml`.

## Related ADRs

- [ADR 0001: Ownership-based backend architecture](../adrs/0001-ownership-based-backend-architecture.md)
- [ADR 0002: Hybrid app plus OBO authorization](../adrs/0002-hybrid-auth-model.md)
- [ADR 0003: Centralized dependency composition](../adrs/0003-centralized-dependency-composition.md)
- [ADR 0004: Lifecycle message bus](../adrs/0004-lifecycle-message-bus.md)
- [ADR 0005: Governed routing policy and response guardrails](../adrs/0005-governed-routing-policy-and-response-guardrails.md)
- [ADR 0009: Unity AI Gateway for LLM traffic](../adrs/0009-unity-ai-gateway-for-llm-traffic.md)
- [ADR 0007: Evaluation KPI release gate](../adrs/0007-evaluation-kpi-release-gate.md)
