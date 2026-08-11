# Multi-Agent App on Databricks

A production-oriented multi-agent AI application on Databricks for governed tool routing, hybrid authorization, and environment-aware deployment.

## Why This Project

Modern AI applications are moving from single-model chatbots to orchestrated systems that can:

- Route requests to specialized agents and tools
- Ground responses on governed business data
- Stream responses in real time for interactive UX
- Ship safely through multi-environment CI/CD

This repository provides an MVP foundation that can easily scale to enterprise use cases.

Key project strengths:

- Governed multi-agent routing with policy and guardrail enforcement before tool execution.
- Hybrid authorization support for both app identity and user identity (OBO) execution paths.
- Production-oriented quality gates using MLflow GenAI evaluation and KPI-based release blocking.
- Resilient deployment workflow with Terraform-free fallback, health checks, and smoke checks.
- Strong architecture and governance traceability through ADRs and domain-specific specifications.

## Introduction Dependencies

The current implementation depends on business semantics and AI metadata across governed tools and indexes.
Runtime integrations are environment-specific through `src/backend/domain/subagents.<target>.json`.

Current dev target examples:

- Genie Agent: `sales_insights_agent` (space id configured in `subagents.dev.json`)
- AI Search MCP index: `product_index_assistant` using `/api/2.0/mcp/ai-search/dt_dev_gold/dwh_dbx/dim_product_search_index`

## Backend UC Security and Governance Guidelines

Project guidelines and best practices for Unity Catalog-governed backend execution:

- Apply least privilege by default for both app identity and OBO identity, granting only required `USE CATALOG`, `USE SCHEMA`, and object-level permissions.
- Separate environment assets (dev, qa, stg, prod) with explicit catalog/schema boundaries and avoid cross-environment data access from runtime credentials.
- Enforce classification-aware routing in subagent metadata (`data_classification`, `allowed_personas`, `requires_evidence`) before tool execution.
- Require evidence-backed responses for governed or sensitive routes and block outputs that fail guardrail policy checks.
- Use Unity Catalog-governed audit persistence (`MESSAGE_BUS_BACKEND=uc_table`) for lifecycle, policy, auth, and guardrail events.
- Protect customer and regional-store datasets with row/column-level governance controls and avoid exposing restricted fields in tool responses.
- Keep backend-to-data contracts versioned and reviewed when adding new Genie Agents, AI Search indexes, or Lakebase ODS endpoints.

## Technology Perspective

This project uses a modern AI app stack on Databricks:

- Multi-agent orchestration: one orchestrator routes intent to specialist backends.
- Tool-augmented reasoning: Agents call tools instead of relying on model-only answers.
- Managed app runtime: Databricks Apps hosts the full stack.
- Agent-native serving runtime: MLflow Agent Server with ResponsesAgent handlers.
- OpenAI-compatible agent loop: OpenAI Agents SDK + Databricks OpenAI Responses API.
- MCP integration for enterprise context: Genie tool access through MCP.
- Governed data access: Unity Catalog permissions and SQL warehouse controls.
- Hybrid authorization model: per-tool app identity and user identity (OBO) routing.
- Deployment-as-code: Databricks Declarative Automation Bundles with target overlays.
- Streaming-first UX: React + TypeScript frontend with incremental token streaming.

## Functionality Perspective

The app provides:

- Unified endpoint: A single app endpoint for multi-tool, multi-agent interaction.
- Dynamic routing: Requests are routed to Genie Agents, serving endpoints, or app-based specialists.
- Real-time responses: Streaming responses for conversational latency.
- Configurable specialist set: Subagents can be added and validated through typed configuration.
- Auth-aware tool routing: each subagent declares `auth_mode` (`app` or `obo`).
- Governed routing policy: persona, tool-targeting, identity, and data-classification checks run before tool execution.
- Response guardrails: governed responses enforce evidence/citation requirements and sensitive-output safety checks.
- Environment isolation: dev, qa, stg, and prod with explicit target-specific settings.
- Operational fallback path: Direct apps deploy path when Terraform registry availability is degraded.

## 5-Minute Start

If your Databricks CLI profile is already configured, this is the fastest way to run and validate locally:

```bash
uv run quickstart
uv run preflight
uv run start-app
```

What this does:

- `quickstart`: prepares local environment and baseline config.
- `preflight`: validates local startup, health endpoint, and `/invocations` request path.
- `start-app`: runs backend and UI for interactive testing.

For deployment, continue with the standard bundle flow in Quick Start.

## Authorization Model

The runtime uses a hybrid authorization model:

- App Authorization: tools execute with the app service principal identity.
- User Authorization (OBO): tools execute with the forwarded user access token.

Subagent authorization is configured in target-specific files such as `src/backend/domain/subagents.dev.json` using `auth_mode`:

- `auth_mode: app`
- `auth_mode: obo`

Current defaults:

- Genie Agent subagents default to `obo` when not explicitly set.
- Non-Genie subagents default to `app` when not explicitly set.

The backend loads an environment-specific file at startup and validates it with typed models in `src/backend/domain/subagent_config.py`.
Override the path with `SUBAGENTS_CONFIG_PATH`.

If an OBO tool is selected and no forwarded token is present, the runtime raises a clear user-facing authorization error instead of falling back silently.

## Governance and Observability

Lifecycle and policy events are emitted through the message bus. Backend selection is environment-driven:

- `structured_logging` (default)
- `noop`
- `kafka`
- `rabbitmq`
- `uc_table` (Unity Catalog-governed Delta audit table)

Optional async publishing mode is available to move bus writes off the request path:

- `MESSAGE_BUS_ASYNC=true`
- `MESSAGE_BUS_ASYNC_QUEUE_SIZE=<int>`
- `MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS=<float>`

For governed execution, the runtime emits policy allow/deny decisions and response guardrail pass/block outcomes.

## UI Token Commands

The React UI supports session-scoped token commands for OBO testing:

- `/token <databricks_access_token>`: store a forwarded token for this chat session.
- `/clear-token`: clear the forwarded token from this chat session.

When set, the UI forwards the token to backend `/invocations` as the `x-forwarded-access-token` header.

For non-interactive CLI/API tests against Databricks Apps, use `Authorization: Bearer <token>`.

## Core Architecture

High-level request path:

1. User message enters React UI.
2. Request reaches Databricks App endpoint.
3. MLflow Agent Server dispatches invoke or stream handlers.
4. Orchestrator selects tools and specialist agents.
5. Tools query Genie Agent MCP routes, AI Search MCP indexes, or serving endpoints.
6. Unified response is returned to the client.

For architecture diagrams, see [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md).

## Project Layout

- [src/backend/](src/backend): orchestrator runtime, handlers, request normalization, server startup
- [src/backend/README.md](src/backend/README.md): backend-focused setup, runtime behavior, and operations guide
- [src/reactui/](src/reactui): primary React UI (TypeScript) client for chat, commands, and stream rendering
- [src/reactui/README.md](src/reactui/README.md): React UI setup, build, and local run guide
- [src/frontend/](src/frontend): legacy Chainlit frontend retained for compatibility and migration fallback
- [src/frontend/README.md](src/frontend/README.md): legacy Chainlit frontend guide
- [src/scripts/](src/scripts): quickstart, preflight, local start, discovery, and permission helpers
- [resources/multiagent_app.yml](resources/multiagent_app.yml): shared Databricks app resource definition
- [targets/](targets): target-specific deployment overlays
- [databricks.yml](databricks.yml): DAB bundle root configuration
- [docs/README.md](docs/README.md): architecture, design, and runbook documentation index

## Quick Start

Prerequisites:

- Python 3.11+
- uv
- Databricks CLI

Run locally:

```bash
uv run quickstart
uv run start-app
```

Validate and deploy:

```bash
make redeploy TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT
```

If bundle deploy fails due to Terraform provider registry availability, use the operational fallback documented in [docs/operations/runbook.md](docs/operations/runbook.md).

## Runtime Environment Variables

- `BACKEND_LOG_LEVEL`: backend log level (default `INFO`).
- `BACKEND_LOG_FORMAT`: Python logging format string for backend logs.
- `BACKEND_LOG_DATE_FORMAT`: datetime format used in backend logs.
- `BACKEND_UVICORN_WORKERS`: backend worker count for `start-app`/`start-server` launch (fallback `WEB_CONCURRENCY`, default `1`).
- `FRONTEND_UVICORN_WORKERS`: React UI proxy worker count for `start-app` frontend process (default `1`).
- `MESSAGE_BUS_BACKEND`: `structured_logging` (default), `noop`, `kafka`, `rabbitmq`, or `uc_table`.
- `MESSAGE_BUS_TOPIC`: topic name used by message bus backends (default `agent-lifecycle-events`).
- `MESSAGE_BUS_FAIL_OPEN`: when `true`, fallback to structured logging if bus init fails.
- `MESSAGE_BUS_ASYNC`: when `true`, publish bus events through an internal async queue worker.
- `MESSAGE_BUS_ASYNC_QUEUE_SIZE`: max async bus queue size before drop/error policy applies (default `1000`).
- `MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS`: shutdown join timeout for async bus worker (default `2.0`).
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (required for `MESSAGE_BUS_BACKEND=kafka`).
- `KAFKA_CLIENT_ID`: Kafka client id used by producer (default `multiagent-app`).
- `RABBITMQ_URL`: RabbitMQ AMQP URL (required for `MESSAGE_BUS_BACKEND=rabbitmq`).
- `UC_AUDIT_WAREHOUSE_ID`: SQL warehouse id used by `uc_table` message bus backend.
- `UC_AUDIT_CATALOG`: Unity Catalog catalog where audit events table is stored.
- `UC_AUDIT_SCHEMA`: Unity Catalog schema where audit events table is stored.
- `UC_AUDIT_TABLE`: Unity Catalog audit table name (default `agent_lifecycle_events`).
- `DATABRICKS_OPENAI_BASE_URL`: optional Databricks OpenAI base URL override (for example Unity AI Gateway URL).
- `DATABRICKS_OPENAI_TIMEOUT_SECONDS`: optional timeout in seconds for Databricks OpenAI calls (`0` keeps SDK defaults).
- `EVAL_MIN_TOOL_CALL_ACCURACY`: release-gate threshold for tool call correctness (default `0.80`).
- `EVAL_MIN_AUTH_CORRECTNESS`: release-gate threshold for authorization correctness (default `0.90`).
- `EVAL_MIN_SAFETY`: release-gate threshold for safety KPI (default `0.95`).
- `EVAL_MIN_GROUNDEDNESS`: release-gate threshold for groundedness KPI (default `0.80`).
- `EVAL_REQUIRE_ALL_KPIS`: when `true`, fail release gate if any KPI metric is missing.

MCP connect/probe performance controls:

- `MCP_CONNECT_TIMEOUT_SECONDS`: timeout for MCP async context connection (default `10`).
- `MCP_LIST_TOOLS_TIMEOUT_SECONDS`: timeout for MCP `list_tools` probe (default `10`).
- `MCP_HEALTH_TTL_SECONDS`: cached healthy MCP status TTL in seconds (default `30`).
- `MCP_HEALTH_FAILURE_TTL_SECONDS`: cached unhealthy MCP status TTL in seconds (default `10`).
- `ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE`: max in-memory cached static instruction variants (default `128`).

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow and project docstring standard.
- [COPYRIGHT](COPYRIGHT): project copyright notice and usage restrictions.
- [docs/product/business-specs.md](docs/product/business-specs.md): business requirements, constraints, and success metrics.
- [docs/architecture/technical-specs.md](docs/architecture/technical-specs.md): centralized technical implementation map and cross-space contracts.
- [docs/quality/evaluation-spec.md](docs/quality/evaluation-spec.md): datasets, scorers, KPI thresholds, and release-gate rules.
- [Model Matrix and Environment Recommendations](docs/quality/evaluation-spec.md#model-matrix-and-environment-recommendations): environment-specific model profile guidance for dev, qa, stg, and prod release planning.
- [docs/governance/prompt-and-policy-spec.md](docs/governance/prompt-and-policy-spec.md): prompt layering and deterministic policy/guardrail behavior.
- [docs/architecture/model-and-tool-registry.md](docs/architecture/model-and-tool-registry.md): registry of active tools, endpoints, and Genie Agents.
- [docs/governance/data-contract-and-lineage-spec.md](docs/governance/data-contract-and-lineage-spec.md): data contracts, classification, and lineage requirements.
- [docs/governance/business-semantics-and-ai-metadata-spec.md](docs/governance/business-semantics-and-ai-metadata-spec.md): reliable business semantics and required AI metadata contract.
- [docs/governance/security-and-threat-model.md](docs/governance/security-and-threat-model.md): trust boundaries, threats, and controls.
- [docs/operations/cost-and-performance-budget.md](docs/operations/cost-and-performance-budget.md): latency/cost budget framework and operating signals.
- [docs/operations/mlflow-implementation-checklist.md](docs/operations/mlflow-implementation-checklist.md): one-page MLflow rollout checklist with owners, tasks, and acceptance criteria.
- [docs/operations/mlflow-execution-tracker.md](docs/operations/mlflow-execution-tracker.md): live execution tracker template for status, ownership, due dates, dependencies, and evidence.
- [docs/architecture/api-contract-spec.md](docs/architecture/api-contract-spec.md): invoke/stream API contract and error semantics.
- [docs/operations/postmortem-template.md](docs/operations/postmortem-template.md): incident and regression postmortem template.
- [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md): high-level architecture and request flow
- [docs/architecture/system-design.md](docs/architecture/system-design.md): low-level module design and runtime behavior
- [docs/architecture/design-artifacts/README.md](docs/architecture/design-artifacts/README.md): centralized concept, logical, and deployment design diagrams
- [docs/operations/runbook.md](docs/operations/runbook.md): deployment, operations, incident handling, rollback

## Makefile Helpers

Useful operational commands:

- `make redeploy TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT`
- `make grant-runtime-permissions TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT`
- `make query-dev TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT QUERY='top stores by revenue' QUERY_PERSONA=manager`

## Current Status

- Development environment is active and user-accessible.
- Multi-agent routing across Genie and serving endpoints is implemented.
- Governed routing policy, response guardrails, and lifecycle audit-table persistence are implemented.
- GitHub Actions pipeline supports PR CI and deployment automation for dev, qa, stg, and prod.
- Operational controls and troubleshooting guidance are documented in the runbook.
