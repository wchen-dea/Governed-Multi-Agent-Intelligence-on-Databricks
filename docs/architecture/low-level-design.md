# Multiagent App on Databricks: Design (Low Level)

## Purpose

Define implementation details, code structure, runtime behavior, and configuration model.

## Scope

This document covers low-level design and implementation details. See [high-level architecture](high-level-architecture.md) for system boundaries and the [operations runbook](../operations/operations-runbook.md) for procedures.

## Current Status

- Runtime uses an ownership-based backend package structure (`src/aiserver/api`, `src/aiserver/application`, `src/aiserver/bootstrap`, `src/aiserver/config`, `src/aiserver/contracts`, and `src/aiserver/infrastructure`).
- Dependency composition and protocol-driven DI are centralized in `src/aiserver/bootstrap/container.py` and focused modules under `src/aiserver/application/ports/`.
- Local and hosted-app startup resolves the bind port from `DATABRICKS_APP_PORT`/`PORT`/`CHAT_APP_PORT` in `src/aiserver/api/server.py` (`main()`, `_resolve_port()`), run via the `runtime-serve-app` entry point.

## Main Content

### Code-Level Components

#### Backend Runtime

- `src/aiserver/api/invocations.py`
  - Defines `invoke_handler` and `stream_handler`
  - Builds orchestrator agent at request time
  - Connects healthy MCP servers per request
  - Converts request payloads into normalized messages

- `src/aiserver/bootstrap/container.py`
  - Central composition root for API/service dependencies
  - Builds default dependency container for handlers, runtime auth, and orchestrator services
  - Provides single override point for environment-specific wiring

- `src/aiserver/api/server.py`
  - Loads `.env`
  - Initializes `AgentServer("ResponsesAgent", enable_chat_proxy=True)`
  - Exposes root route and application startup

- `src/aiserver/application/auth/context.py`
  - Builds request-scoped hybrid auth context (app + optional OBO user identity)
  - Applies request-time policy filtering before tool/MCP construction
  - Builds auth-aware subagent tools and MCP server definitions
  - Emits auth trace metadata for routing and tool execution
  - Accepts injectable typed dependencies for identity/session/trace/tool-server builders

- `src/aiserver/application/auth/policy.py`
  - Builds policy context from request metadata (persona, requested tool, confidence)
  - Enforces policy decisions by auth mode, identity presence, persona, and data classification
  - Returns explicit allow/deny decisions with reason codes

- `src/aiserver/application/guardrails/checks.py`
  - Applies deterministic response guardrails
  - Enforces evidence requirement for governed answers
  - Blocks unsafe output and low-confidence sensitive responses

- `src/aiserver/application/orchestration/agent.py`
  - Composes tool/server builders and creates the orchestrator agent
  - Builds Genie MCP server list with auth-aware workspace client selection
  - Caches static orchestrator instruction blocks by subagent metadata and appends request-scoped unavailable details dynamically
  - Connects MCP servers with parallel health checks and short TTL health caching
  - Supports injectable dependencies for trace updates, tool wrapping, and MCP server creation

- `src/aiserver/application/adapters/tools.py`
  - Implements the `ToolAdapter` port for MCP, Lakebase, app endpoint, and delegation subagents
  - Defines deterministic adapter precedence: MCP, Lakebase, app endpoint, then delegation
  - Encapsulates app/OBO client selection, function-tool lifecycle events, and Lakebase failure classification
  - Keeps MCP server connection and task-bus delegation as their own execution lifecycles rather than local function tools

- `src/aiserver/application/ports/`
  - Defines protocol-based service interfaces for dependency injection
  - Standardizes contracts for auth-context and tool/server builder dependencies

- `src/aiserver/infrastructure/messaging/bus.py`
  - Provides message bus implementations for lifecycle event publishing
  - Ships with no-op, structured-logging, Kafka, RabbitMQ, and UC audit-table bus implementations
  - Supports optional queue-backed async publish wrapper for request-path latency reduction
  - Serves as extension point for external queue/broker integrations

- `src/aiserver/infrastructure/persistence/approvals.py`
  - Provides in-memory development and UC Delta approval repositories
  - Creates the configured approval table and upserts decisions by request ID
  - Reads persisted decisions for the approval-status API

- `src/aiserver/application/ports/audit.py`
  - Defines the `ApprovalRepository` protocol used by the API without coupling it to SQL

- `src/aiserver/contracts/subagents.py`
  - Typed `SubagentConfig` dataclass
  - Validation for subagent type-specific required fields, optional `system_prompt`, and `auth_mode`
  - Loads and validates canonical `SUBAGENTS` from external JSON config

- `src/aiserver/contracts/subagents.<target>.json`
  - Environment-specific subagent configuration data source (`dev`, `qa`, `stg`, `prd`)
  - Runtime can override path via `SUBAGENTS_CONFIG_PATH`

- `src/aiserver/application/runtime/requests.py`
  - Normalizes input items into plain role/content messages
  - Extracts MCP user-facing errors from exception structures

- `src/aiserver/application/runtime/identity.py`
  - Session ID extraction
  - Forwarded token extraction (`x-forwarded-access-token`)
  - Request identity context construction for hybrid auth
  - Workspace host and MCP URL construction

  - `src/aiserver/application/runtime/streaming.py`
    - Stream event normalization for stable item IDs

- `src/aiserver/infrastructure/observability/logging.py`
  - Centralized root logger configuration for backend entrypoints
  - Consistent level/format/date handling from runtime settings
  - Suppresses noisy MLflow autologging internals

#### Frontend Runtime

- `src/aiweb/src/App.tsx`
  - Main React chat UI flow for requests, command parsing, and response rendering
  - User-selectable background theme (deep ocean, sky blue, deep sky blue) persisted to `localStorage` and applied via `[data-theme]` on the document root

- `src/aiweb/src/api.ts`
  - Sends invocation payloads and manages stream/invoke behavior to backend routes

- `src/aiweb/src/stream.ts`
  - Parses stream metadata and renders only finalized `response.output_text.delta` answer text

- `src/aiserver/application/orchestration/model.py`
  - Selects configured Databricks model routes before orchestrator construction

- `src/aiserver/infrastructure/persistence/tasks.py`, `src/aiserver/application/delegation/worker.py`, `src/aiserver/application/delegation/handoff.py`
  - Persist, lease, execute, and inspect bounded UC-backed app-auth delegation tasks

- `src/aiweb/src/config.ts`
  - Loads typed runtime settings from frontend environment variables

- `src/aiserver/api/server.py`
  - Mounts built React static assets and SPA fallback directly on the backend FastAPI app; falls back to a JSON status payload if the UI isn't bundled

### Runtime Startup

- `src/aiserver/api/server.py` `main()`
  - Resolves the bind port from `DATABRICKS_APP_PORT`/`PORT`/`CHAT_APP_PORT` (falls back to AgentServer's default of 8000) and the worker count from `BACKEND_UVICORN_WORKERS`/`WEB_CONCURRENCY`
  - Runs a single Uvicorn process serving both the API and the UI — no separate frontend process or proxy layer

### Design Patterns

- Orchestrator pattern: a central orchestrator routes user intent to specialist tools and subagents.
- Strategy pattern: `ToolAdapter` implementations vary by subagent type (`genie`, `mcp`, `lakebase`, `serving_endpoint`, `app`) behind a unified interface.
- Registry pattern: `ToolRegistry` resolves the first matching adapter in the fixed MCP, Lakebase, app endpoint, delegation order.
- Policy/strategy blend: runtime auth selection varies by subagent `auth_mode` (`app`, `obo`) under a unified tool interface.
- Configuration object pattern: typed subagent configuration with centralized validation reduces runtime misconfiguration.
- Factory/builder pattern: tool and server construction is encapsulated in dedicated builder functions.
- Dependency injection pattern: handlers/services support typed dependency containers for testability and decoupling.
- Event bus pattern: lifecycle events are published through an abstract message bus interface.
- Adapter pattern: request and error normalization provides a stable internal payload shape.
- Environment overlay pattern: shared bundle config plus per-target overrides (`dev`, `qa`, `stg`, `prd`).

## Request Lifecycle

Reference diagram: [request execution pipeline](design-artifacts/07-request-execution-flow-class-diagram.md)

1. UI sends request to the Databricks App endpoint.
2. MLflow Agent Server receives and dispatches to invoke/stream handler.
3. Runtime auth context is built, policy decisions are evaluated, and auth/policy events are published.
4. Handler opens async context and health-checks MCP servers.
5. Orchestrator agent is created with available tools.
6. Runner executes model/tool loop while tool lifecycle bus events are emitted.
7. Stream execution buffers events; source metadata and guardrails finalize before user-visible text is released.
8. If an approval-required subagent participated, finalization appends evidence/source metadata and a pending manager-review notice before guardrails run.
9. The UI renders `response.output_text.delta` only; tool events remain metadata.
10. A manager submits a decision through `/approval-decisions`; the repository persists it before returning success.
11. Any future operational dispatcher independently reads and validates the approval record before acting.

## Tool Routing Model

Supported subagent types:

- `genie` via MCP (`space_id` required)
- `serving_endpoint` via Databricks Responses API (`endpoint` required)
- `app` via Databricks Responses API using `apps/<endpoint>` model mapping
- `mcp` via generic Databricks MCP route (`mcp_url` required)
- `lakebase` via PostgreSQL wire protocol and OAuth credentials (`project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host` required)

Supported auth modes:

- `app`: use app identity for tool calls.
- `obo`: use user identity from forwarded request token.

The `store-intervention-agent` is app-authenticated and available only to the manager persona. It is an analysis and approval-packet generator, not an autonomous dispatch worker.

Default auth mode behavior:

- `genie` defaults to `obo` if not explicitly configured.
- non-Genie defaults to `app` if not explicitly configured.

For non-Genie tools, function tool names are generated as:

- `query_<subagent_name>`

Adapter selection is separate from execution assembly: MCP subagents are registered as MCP servers, Lakebase subagents receive request-scoped database execution, and delegation is submitted through the bounded task bus. The registry currently selects direct Responses API function tools for serving-endpoint and app subagents; MCP and Lakebase retain their dedicated builders pending migration to the shared registry.

If an OBO tool is invoked without a forwarded token, the runtime returns a clear authorization error and does not silently fall back to app auth.

## Configuration Model

### Bundle Layout

- `databricks.yml`: bundle root config, shared variables, includes, and the `multiagent_wheel` artifact (built via `uv build --wheel`)
- `resources/multiagent_app.yml`: shared app defaults and baseline resource permissions
- `resources/semantics_jobs.yml`: semantics-layer Databricks Jobs that build/refresh `dim_product_search_index`, `flink_support_index`, and `fct_cdi_trusted_expert_score_metric_view` from `src/semantics/`
- `resources/evaluation_job.yml`: Databricks Job that runs `operations.evaluate_agent.evaluate()` on workspace compute (`src/evaluation/run_evaluation.py`) so the release-gate evaluation reaches MLflow tracking and Lakebase over the private network, followed by a `triage_evaluation` task that runs `assistant-triage-evaluation` against the same experiment regardless of gate outcome
- `targets/*.yml`: target-specific host, state path, variables, and resource overrides

### Frequently Used Variables

- `app_name`
- `genie_space_id`
- `knowledge_assistant_endpoint_name`
- `product_index_ep`
- `flink_support_ep`
- `semantics_catalog`
- `semantics_schema`
- `memory_backend`
- `target_app_name`
- `mlflow_experiment_id`
- `approval_backend`
- `approval_warehouse_id`
- `approval_catalog`
- `approval_schema`
- `approval_table`

### Runtime Environment Variables

Used by local and hosted startup:

- `API_PROXY`
- `CHAT_GREETING`
- `CHAT_PROXY_TIMEOUT_SECONDS`
- `DATABRICKS_APP_NAME`
- `DATABRICKS_APP_PORT`
- `PORT`
- `BACKEND_LOG_LEVEL`
- `BACKEND_LOG_FORMAT`
- `BACKEND_LOG_DATE_FORMAT`
- `BACKEND_UVICORN_WORKERS` (backend worker count, fallback to `WEB_CONCURRENCY`)
- `MESSAGE_BUS_BACKEND`
- `MESSAGE_BUS_TOPIC`
- `MESSAGE_BUS_FAIL_OPEN`
- `MESSAGE_BUS_ASYNC`
- `MESSAGE_BUS_ASYNC_QUEUE_SIZE`
- `MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS`
- `MCP_CONNECT_TIMEOUT_SECONDS`
- `MCP_LIST_TOOLS_TIMEOUT_SECONDS`
- `MCP_HEALTH_TTL_SECONDS`
- `MCP_HEALTH_FAILURE_TTL_SECONDS`
- `ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_CLIENT_ID`
- `RABBITMQ_URL`
- `UC_AUDIT_WAREHOUSE_ID`
- `UC_AUDIT_CATALOG`
- `UC_AUDIT_SCHEMA`
- `UC_AUDIT_TABLE`
- `APPROVAL_BACKEND`
- `APPROVAL_WAREHOUSE_ID`
- `APPROVAL_CATALOG`
- `APPROVAL_SCHEMA`
- `APPROVAL_TABLE`
- `APPROVAL_FAIL_OPEN`
- `EVAL_MIN_TOOL_CALL_ACCURACY`
- `EVAL_MIN_AUTH_CORRECTNESS`
- `EVAL_MIN_SAFETY`
- `EVAL_MIN_GROUNDEDNESS`
- `EVAL_REQUIRE_ALL_KPIS`

Request header used at runtime for OBO:

- `x-forwarded-access-token`

Direct non-interactive Databricks Apps invocation tests should use:

- `Authorization: Bearer <token>`

## Operational Constraints in Design

- MCP health checks run in parallel with timeout controls and short TTL caching for healthy/unhealthy outcomes.
- `make upload-wheel` provides the lifecycle-gated source deployment path for Terraform registry outages; it does not apply bundle-managed resources or grants.
- Genie-backed queries require SQL warehouse and Unity Catalog grants for both user and app service principal.

## Key Files Quick Map

| File | Responsibility |
| ---- | -------------- |
| `src/aiserver/api/invocations.py` | Handler entrypoints and orchestration wiring |
| `src/aiserver/application/orchestration/agent.py` | Tool/server construction and orchestrator assembly |
| `src/aiserver/application/adapters/tools.py` | Concrete tool adapters and default registry |
| `src/aiserver/application/ports/tools.py` | Tool adapter and registry protocol contracts |
| `src/aiserver/contracts/subagents.py` | Typed subagent definitions and validation |
| `src/aiserver/api/server.py` | MLflow Agent Server bootstrap, hosted-port resolution |
| `src/aiserver/infrastructure/persistence/memory.py` | No-op and Lakebase-backed conversation/persona memory |
| `src/aiweb/src/App.tsx` | Primary chat UI and command flow |

## Related Docs

- [Architecture guide](README.md): authority map and role-based reading paths
- [Business specifications](../product/business-specs.md): business goals and requirements
- [Runtime technical specifications](runtime-technical-specs.md): centralized technical domain map
- [High-level architecture](high-level-architecture.md): system boundaries and request flow
- [Design artifacts](design-artifacts/README.md): concept, logical, deployment, and runtime diagrams
- [Backend class diagrams](design-artifacts/08-backend-class-diagram-as-is.md): current service composition
- [Operations runbook](../operations/operations-runbook.md): deployment and incident handling
