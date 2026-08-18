# Multiagent App on Databricks: Design (Low Level)

## Purpose

Define implementation details, code structure, runtime behavior, and configuration model.

## Scope

This document covers low-level design and implementation details. High-level architecture is in `docs/architecture/system-architecture.md`, and operations guidance is in `docs/operations/runbook.md`.

## Current Status

- Runtime uses a layered backend package structure (`src/backend/api`, `src/backend/services`, `src/backend/domain`, `src/backend/shared`).
- Dependency composition and protocol-driven DI are centralized in `src/backend/api/dependencies.py` and `src/backend/services/interfaces.py`.
- Local startup orchestration handles hosted-port conflicts in `src/scripts/start_app.py`.

## Main Content

### Code-Level Components

#### Backend Runtime

- `src/backend/api/handlers.py`
  - Defines `invoke_handler` and `stream_handler`
  - Builds orchestrator agent at request time
  - Connects healthy MCP servers per request
  - Converts request payloads into normalized messages

- `src/backend/api/dependencies.py`
  - Central composition root for API/service dependencies
  - Builds default dependency container for handlers, runtime auth, and orchestrator services
  - Provides single override point for environment-specific wiring

- `src/backend/api/server.py`
  - Loads `.env`
  - Initializes `AgentServer("ResponsesAgent", enable_chat_proxy=True)`
  - Exposes root route and application startup

- `src/backend/services/runtime_auth_service.py`
  - Builds request-scoped hybrid auth context (app + optional OBO user identity)
  - Applies request-time policy filtering before tool/MCP construction
  - Builds auth-aware subagent tools and MCP server definitions
  - Emits auth trace metadata for routing and tool execution
  - Accepts injectable typed dependencies for identity/session/trace/tool-server builders

- `src/backend/services/policy_service.py`
  - Builds policy context from request metadata (persona, requested tool, confidence)
  - Enforces policy decisions by auth mode, identity presence, persona, and data classification
  - Returns explicit allow/deny decisions with reason codes

- `src/backend/services/guardrails_service.py`
  - Applies deterministic response guardrails
  - Enforces evidence requirement for governed answers
  - Blocks unsafe output and low-confidence sensitive responses

- `src/backend/services/orchestrator_service.py`
  - Creates callable tools for configured subagents
  - Selects app vs OBO client per subagent tool call
  - Builds Genie MCP server list with auth-aware workspace client selection
  - Caches static orchestrator instruction blocks by subagent metadata and appends request-scoped unavailable details dynamically
  - Connects MCP servers with parallel health checks and short TTL health caching
  - Supports injectable dependencies for trace updates, tool wrapping, and MCP server creation

- `src/backend/services/interfaces.py`
  - Defines protocol-based service interfaces for dependency injection
  - Standardizes contracts for auth-context and tool/server builder dependencies

- `src/backend/services/message_bus.py`
  - Provides message bus implementations for lifecycle event publishing
  - Ships with no-op, structured-logging, Kafka, RabbitMQ, and UC audit-table bus implementations
  - Supports optional queue-backed async publish wrapper for request-path latency reduction
  - Serves as extension point for external queue/broker integrations

- `src/backend/domain/subagent_config.py`
  - Typed `SubagentConfig` dataclass
  - Validation for subagent type-specific required fields, optional `system_prompt`, and `auth_mode`
  - Loads and validates canonical `SUBAGENTS` from external JSON config

- `src/backend/domain/subagents.<target>.json`
  - Environment-specific subagent configuration data source (`dev`, `qa`, `stg`, `prod`)
  - Runtime can override path via `SUBAGENTS_CONFIG_PATH`

- `src/backend/shared/request_utils.py`
  - Normalizes input items into plain role/content messages
  - Extracts MCP user-facing errors from exception structures

- `src/backend/shared/runtime_utils.py`
  - Session ID extraction
  - Forwarded token extraction (`x-forwarded-access-token`)
  - Request identity context construction for hybrid auth
  - Workspace host and MCP URL construction
  - Stream event normalization for stable item IDs

- `src/backend/shared/logging_config.py`
  - Centralized root logger configuration for backend entrypoints
  - Consistent level/format/date handling from runtime settings
  - Suppresses noisy MLflow autologging internals

#### Frontend Runtime

- `src/reactui/src/App.tsx`
  - Main React chat UI flow for requests, command parsing, and response rendering

- `src/reactui/src/api.ts`
  - Sends invocation payloads and manages stream/invoke behavior to backend routes

- `src/reactui/src/stream.ts`
  - Parses streaming events, text deltas, and source/tool provenance hints

- `src/reactui/src/config.ts`
  - Loads typed runtime settings from frontend environment variables

- `src/scripts/react_ui_server.py`
  - Serves built React assets and proxies `/invocations` to backend runtime

- `src/frontend/`
  - Legacy Chainlit frontend retained for compatibility and fallback use

#### Local Process Orchestration

- `src/scripts/start_app.py`
  - Starts backend and optional frontend in parallel
  - Supports env-driven backend/frontend worker tuning for Uvicorn process fan-out
  - Tracks readiness patterns from logs
  - Detects first failure and exits with failing process code
  - In Databricks hosted runtime, remaps backend to internal port when UI shares app port

### Design Patterns

- Orchestrator pattern: a central orchestrator routes user intent to specialist tools and subagents.
- Strategy pattern: routing behavior varies by subagent type (`genie`, `serving_endpoint`, `app`) behind a unified interface.
- Strategy pattern: routing behavior varies by subagent type (`genie`, `serving_endpoint`, `app`, `mcp`) behind a unified interface.
- Policy/strategy blend: runtime auth selection varies by subagent `auth_mode` (`app`, `obo`) under a unified tool interface.
- Configuration object pattern: typed subagent configuration with centralized validation reduces runtime misconfiguration.
- Factory/builder pattern: tool and server construction is encapsulated in dedicated builder functions.
- Dependency injection pattern: handlers/services support typed dependency containers for testability and decoupling.
- Event bus pattern: lifecycle events are published through an abstract message bus interface.
- Adapter pattern: request and error normalization provides a stable internal payload shape.
- Proxy pattern: React UI server proxies browser-origin requests to backend invocation handlers.
- Environment overlay pattern: shared bundle config plus per-target overrides (`dev`, `qa`, `stg`, `prod`).

## Request Lifecycle

Reference diagram: `docs/architecture/design-artifacts/07-request-execution-flow-class-diagram.md`

1. UI sends request to the Databricks App endpoint.
2. MLflow Agent Server receives and dispatches to invoke/stream handler.
3. Runtime auth context is built, policy decisions are evaluated, and auth/policy events are published.
4. Handler opens async context and health-checks MCP servers.
5. Orchestrator agent is created with available tools.
6. Runner executes model/tool loop while tool lifecycle bus events are emitted.
7. Response guardrails evaluate output against governed constraints before returning content.
8. Response items/events are normalized and returned to client.

## Tool Routing Model

Supported subagent types:

- `genie` via MCP (`space_id` required)
- `serving_endpoint` via Databricks Responses API (`endpoint` required)
- `app` via Databricks Responses API using `apps/<endpoint>` model mapping
- `mcp` via generic Databricks MCP route (`mcp_url` required)
- `lakebase` via PostgreSQL wire protocol with OAuth credentials (`project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host` required)

Supported auth modes:

- `app`: use app identity for tool calls.
- `obo`: use user identity from forwarded request token.

Default auth mode behavior:

- `genie` defaults to `obo` if not explicitly configured.
- non-Genie defaults to `app` if not explicitly configured.

For non-Genie tools, function tool names are generated as:

- `query_<subagent_name>`

If an OBO tool is invoked without a forwarded token, the runtime returns a clear authorization error and does not silently fall back to app auth.

## Configuration Model

### Bundle Layout

- `databricks.yml`: bundle root config, shared variables, includes
- `resources/multiagent_app.yml`: shared app defaults and baseline resource permissions
- `targets/*.yml`: target-specific host, state path, variables, and resource overrides

### Frequently Used Variables

- `app_name`
- `genie_space_id`
- `knowledge_assistant_endpoint_name`
- `serving_endpoint_name`
- `target_app_name`
- `mlflow_experiment_id`

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
- `FRONTEND_UVICORN_WORKERS` (React UI proxy worker count; values >1 use Uvicorn multi-worker mode)
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
- Fallback deployment path exists for Terraform registry outages (`bundle sync` + `apps deploy`).
- Genie-backed queries require SQL warehouse and Unity Catalog grants for both user and app service principal.

## Key Files Quick Map

| File | Responsibility |
| ---- | -------------- |
| `src/backend/api/handlers.py` | Handler entrypoints and orchestration wiring |
| `src/backend/services/orchestrator_service.py` | Tool/server construction and orchestrator assembly |
| `src/backend/domain/subagent_config.py` | Typed subagent definitions and validation |
| `src/backend/api/server.py` | MLflow Agent Server bootstrap |
| `src/reactui/src/App.tsx` | Primary chat UI and command flow |
| `src/scripts/start_app.py` | Local process supervision |

## Related Docs

- `docs/product/business-specs.md`: business goals and requirements
- `docs/architecture/technical-specs.md`: centralized technical domain map
- `docs/architecture/system-architecture.md`: high-level architecture and request flow
- `docs/architecture/design-artifacts/README.md`: centralized full design diagram set across concept, logical, and deployment phases
- `docs/architecture/design-artifacts/08-backend-class-diagram-as-is.md`: concrete as-is backend class diagram
- `docs/operations/runbook.md`: operations and incident handling
