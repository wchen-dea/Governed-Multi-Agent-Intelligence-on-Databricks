# Governed Multi-Agent Intelligence on Databricks

**A governed agentic AI platform for operational decisions, not another generic chatbot.**

This repository is a production-oriented Databricks blueprint for AI executives, AI architects, and AI engineers building systems that select the right model, invoke the right governed tool, operate on live enterprise data, coordinate bounded agent work, and leave an auditable record of every consequential decision. It turns Databricks AI capabilities into a deployable operating model for business intelligence, operations, support, and data-driven workflows.

## Executive Summary

The next generation of enterprise AI will be judged by execution, controls, and measurable business outcomes, not conversational fluency alone. This implementation is designed for that standard.

| For AI executives | For AI architects | For AI engineers |
| --- | --- | --- |
| Move from isolated copilots to an accountable AI operating model with governed data access, release gates, and measurable quality. | Separate routing, model selection, authorization, delegation, guardrails, audit, and deployment into independently testable control planes. | Build and extend agents against typed contracts, a composed dependency root, and reproducible local/CI workflows instead of ad hoc scripts. |
| Expand AI by business domain without losing policy ownership, identity boundaries, or operational evidence. | Add agents, models, tools, and asynchronous workflows through typed contracts rather than bespoke point-to-point integrations. | Ship changes with confidence: unit tests, evaluation KPIs, lint/format tooling, and a documented deploy/rollback path cover every layer. |
| Make AI capability investable through explicit controls, evidence, and promotion criteria. | Build on Databricks Apps, MLflow Agent Server, MCP, Unity Catalog, Lakebase, and DAB target overlays. | Debug fast with lifecycle audit events, MLflow tracing, and a local 5-minute start path that mirrors production behavior. |

## Why This Matters

This platform operationalizes the AI patterns enterprises need now:

- **From answers to action:** native function calls orchestrate MCP, Genie, Vector Search, Lakebase, serving endpoints, and app tools.
- **Governed data intelligence:** Unity Catalog, app/OBO identity, persona policy, classifications, and guardrails are evaluated before tools execute.
- **Deliberate capability selection:** task-aware routing records the Databricks model selected for standard, reasoning, and synthesis work.
- **Bounded multi-agent coordination:** typed delegation uses correlation IDs, idempotency, leases, retries, dead-letter states, and Unity Catalog Delta task/event tables.
- **Production evidence:** lifecycle audit events, MLflow tracing, quality KPIs, release gates, and redacted delegation status replace opaque agent behavior.
- **Human-controlled action:** store-intervention recommendations produce an evidence-backed manager approval packet and remain non-dispatchable until an explicit decision is durably recorded.
- **Platform-grade delivery:** Databricks Apps, DAB overlays, versioned wheels, lifecycle gates, health checks, and source-only recovery support repeatable releases.

The operating principle is simple: use agents where tools add verified value, preserve enterprise controls where data and identity matter, and promote only what can be measured.

## Databricks AI Platform Features Used

This project currently uses the following Databricks AI platform features:

- Databricks Model Serving: specialist serving-endpoint integrations and model-access routing.
- Databricks Foundation Model APIs (OpenAI-compatible): orchestrator model calls through Databricks OpenAI APIs.
- Unity AI Gateway-ready configuration: optional base URL and timeout settings for gateway-based routing.
- Mosaic AI Agent Evaluation with MLflow: quality KPI scoring and release-gate checks.
- MLflow Agent Server: invoke and stream handlers for agent runtime execution.
- MLflow Tracing: execution traces and evaluation artifacts for observability and validation.
- Databricks MCP tool routes: managed MCP endpoints for Genie Agent and AI Search integrations.
- Genie Agents: natural-language access to governed structured business data.
- Unity Catalog Semantic Metric Views: recommended semantic source layer for Genie Agents and KPI-aligned business metrics.
- AI Search: retrieval integration via MCP route-backed index access.
- Lakebase PostgreSQL: optional conversation/persona memory persistence (`MEMORY_BACKEND=lakebase`, disabled by default).

Supporting platform infrastructure:

- Databricks Apps: hosts the deployed multi-agent application runtime.
- Databricks Declarative Automation Bundles (DAB): environment-aware deploy configuration and overlays.
- Unity Catalog: governed data access controls, metadata boundaries, and environment isolation.
- Databricks SQL Warehouse: backend execution path for UC-governed audit table writes.
- Databricks Apps telemetry export: application telemetry routing to a Unity Catalog table.

## AI Engineering Techniques Used

Beyond the Databricks platform features above, this project implements these AI engineering techniques:

- OpenAI Agents SDK (`openai-agents`): agent orchestration runtime (`Agent`, `Runner.run`/`Runner.run_streamed`, native function-calling tools).
- OpenAI-compatible Responses API contract: Databricks Foundation Model API and specialist serving-endpoint calls use one stable model/tool-call contract, with structured run metadata captured for audit and evaluation.
- Model Context Protocol (MCP): standardized tool-calling protocol for Genie and AI Search integrations, with health-checked, TTL-cached server connections.
- Task-aware model routing: deterministic selection between standard/reasoning/synthesis Databricks models per request, recorded via `routing.plan.selected` lifecycle events.
- Multi-agent delegation with typed contracts: bounded async agent-to-agent task handoff with correlation IDs, idempotency keys, leases, retries, and dead-letter states.
- LLM-as-judge evaluation: `ToolCallCorrectness`, `Safety`, and `ConversationalSafety` scorers plus custom `AuthCorrectness` and `DirectGroundedness` (evidence-marker-based) scorers.
- Deterministic response guardrails: evidence/citation enforcement and unsafe-pattern/low-confidence blocking applied post-generation, independent of the LLM judge path.
- Human-in-the-loop controls: manager-only store intervention review with pending, approved, rejected, and more-information states backed by a UC Delta approval table.
- Persona-based policy authorization: governed routing that filters candidate subagents by persona, auth mode, and data classification before tool execution.
- Streaming agent responses: token/tool-event streaming with mid-stream guardrail finalization for the chat UI.
- Structured response governance metadata: response envelopes record route plans, OpenAI run ids, selected models, selected tools, unavailable tool details, guardrail outcomes, source metadata, and approval state.
- RAG (retrieval-augmented generation): AI Search/Vector Search-backed retrieval for product knowledge and Flink support troubleshooting, with citation-grounded answers.

## Team Onboarding: Project Skills and Capabilities

The project provides skills for tool discovery and integration, agent changes, local setup, deployment, and governed runtime operations. See [Documentation guide: Team Onboarding](docs/README.md#team-onboarding-skills-and-capabilities) for the complete skill index and runtime playbooks.

HITL workflow details:

- [Human-in-the-loop approval](docs/governance/human-in-the-loop.md): canonical workflow, query examples, API contract, persistence settings, and operational verification.

## Semantic Data Dependencies

The current implementation depends on business semantics and AI metadata across governed tools and indexes.
Runtime integrations are environment-specific through `src/aiserver/contracts/subagents.<target>.json`.

Current dev target examples:

- Genie Agent: `sales_insights_agent` (space id configured in `subagents.dev.json`)
- Genie Agent: `cdi_agent` — Customer Delight Indicator analytics backed by UC Semantic Metric View `quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view`
- Vector Search MCP index: `product_index_assistant` using `/api/2.0/mcp/vector-search/quickstart_catalog/multi_agent_schema/dim_product_search_index`
- AI Search MCP index: `flink_support_agent` using `/api/2.0/mcp/ai-search/quickstart_catalog/multi_agent_schema/flink_support_index` (RAG over support KB volume)

Typical Genie Agent source pattern:

- Unity Catalog Semantic Metric Views are the recommended structured source layer for Genie Agents.
- Blueprint reference: [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint)

Semantics layer build automation:

- Notebooks under [src/semantics/](src/semantics) build/refresh `dim_product_search_index`, `flink_support_index`, and `fct_cdi_trusted_expert_score_metric_view`.
- Corresponding Databricks Jobs are declared in `resources/semantics_jobs.yml`; see [src/semantics/README.md](src/semantics/README.md).

## Backend UC Security and Governance Guidelines

Project guidelines and best practices for Unity Catalog-governed backend execution:

- Apply least privilege by default for both app identity and OBO identity, granting only required `USE CATALOG`, `USE SCHEMA`, and object-level permissions.
- Separate environment assets (dev, qa, stg, prd) with explicit catalog/schema boundaries and avoid cross-environment data access from runtime credentials.
- Enforce classification-aware routing in subagent metadata (`data_classification`, `allowed_personas`, `requires_evidence`) before tool execution.
- Require evidence-backed responses for governed or sensitive routes and block outputs that fail guardrail policy checks.
- Use Unity Catalog-governed audit persistence (`MESSAGE_BUS_BACKEND=uc_table`) for lifecycle, policy, auth, and guardrail events.
- Protect customer and regional-store datasets with row/column-level governance controls and avoid exposing restricted fields in tool responses.
- Keep backend-to-data contracts versioned and reviewed when adding new Genie Agents, AI Search indexes, or Lakebase ODS endpoints.

## Technology Stack

The application uses Databricks Apps, MLflow Agent Server, the OpenAI Agents SDK, the Databricks OpenAI-compatible Responses API, MCP, Unity Catalog, Lakebase, React, TypeScript, and Vite. See [AI technologies and patterns](docs/architecture/ai-technologies-and-patterns.md) for the canonical framework, pattern, tool, data-capability, and skill inventory.

## Core Capabilities

The app provides:

- Unified endpoint: A single app endpoint for multi-tool, multi-agent interaction.
- Dynamic routing: Requests are routed to Genie Agents, serving endpoints, or app-based specialists.
- Guardrailed streaming: buffered response events are finalized before visible text is emitted.
- Configurable specialist set: Subagents can be added and validated through typed configuration.
- Auth-aware tool routing: each subagent declares `auth_mode` (`app` or `obo`).
- Governed routing policy: persona, tool-targeting, identity, and data-classification checks run before tool execution.
- Response guardrails: governed responses enforce evidence/citation requirements and sensitive-output safety checks.
- Environment isolation: dev, qa, stg, and prd with explicit target-specific settings.
- Operational fallback path: Direct apps deploy path when Terraform registry availability is degraded.

## 5-Minute Start

If your Databricks CLI profile is already configured, this is the fastest way to run and validate locally:

```bash
uv run assistant-bootstrap
uv run runtime-preflight
uv run runtime-serve-app
```

What this does:

- `quickstart`: prepares local environment and baseline config.
- `preflight`: validates local startup, health endpoint, and `/invocations` request path.
- `runtime-serve-app`: runs the backend and UI together (single process) for interactive testing.

For deployment, continue with the standard bundle flow in Quick Start.

## Authorization Model

The runtime uses a hybrid authorization model:

- App Authorization: tools execute with the app service principal identity.
- User Authorization (OBO): tools execute with the forwarded user access token.

Subagent authorization is configured in target-specific files such as `src/aiserver/contracts/subagents.dev.json` using `auth_mode`:

- `auth_mode: app`
- `auth_mode: obo`

Current defaults:

- Genie Agent subagents default to `obo` when not explicitly set.
- Non-Genie subagents default to `app` when not explicitly set.

The backend loads an environment-specific file at startup and validates it with typed models in `src/aiserver/contracts/subagents.py`.
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

- `MESSAGE_BUS_ASYNC=true` (requires `MESSAGE_BUS_FAIL_OPEN=true`)
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
6. Governed responses are finalized with evidence, guardrail state, and a pending approval state when required.
7. For store interventions, a manager decision is recorded through the approval API before any future operational dispatcher can act.

For architecture diagrams, see [docs/architecture/high-level-architecture.md](docs/architecture/high-level-architecture.md).

## Project Layout

- [src/aiserver/](src/aiserver): orchestrator runtime, handlers, request normalization, server startup
- [src/hitl-agent/](src/hitl-agent): deployed `store-intervention-agent` specialist source and App configuration
- [src/aiserver/README.md](src/aiserver/README.md): backend-focused setup, runtime behavior, and operations guide
- [src/aiweb/](src/aiweb): primary React UI (TypeScript) client for chat, commands, and stream rendering
- [src/aiweb/README.md](src/aiweb/README.md): React UI setup, build, and local run guide
- [src/operations/](src/operations): quickstart, preflight, local start, discovery, and permission helpers
- [resources/multiagent_app.yml](resources/multiagent_app.yml): shared Databricks app resource definition
- [resources/hitl_app.yml](resources/hitl_app.yml): DAB-managed `store-intervention-agent` specialist App resource
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
uv run assistant-bootstrap
uv run runtime-serve-app
```

Validate and deploy:

```bash
make redeploy TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT
```

Lint Markdown documentation:

```bash
make lint-markdown
```

Run the unified code-quality check or apply formatting:

```bash
make lint
make format
```

The command uses the pinned `markdownlint-cli2` version through `scripts/lint_markdown.sh` and excludes generated app assets and dependency directories.

If bundle deploy fails due to Terraform provider registry availability, use the operational fallback documented in [docs/operations/operations-runbook.md](docs/operations/operations-runbook.md).

For a source-only deployment that does not contact Terraform Registry, run:

```bash
make upload-wheel TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT
```

This builds versioned wheel and React payloads, clears prior generated remote wheels, uploads the payload, creates the app only when it is missing, otherwise updates the existing app without changing its service principal, deploys through the Databricks Apps API, and checks health. It does not apply bundle-managed resource grants.

## Runtime Environment Variables

- `BACKEND_LOG_LEVEL`: backend log level (default `INFO`).
- `BACKEND_LOG_FORMAT`: Python logging format string for backend logs.
- `BACKEND_LOG_DATE_FORMAT`: datetime format used in backend logs.
- `BACKEND_UVICORN_WORKERS`: worker count for `runtime-serve-app`/`runtime-serve-backend` (fallback `WEB_CONCURRENCY`, default `1`).
- `MESSAGE_BUS_BACKEND`: `structured_logging` (default), `noop`, `kafka`, `rabbitmq`, or `uc_table`.
- `MESSAGE_BUS_TOPIC`: topic name used by message bus backends (default `agent-lifecycle-events`).
- `MESSAGE_BUS_FAIL_OPEN`: when `true`, fallback to structured logging if bus init fails.
- `MESSAGE_BUS_ASYNC`: when `true`, publish bus events through an internal async queue worker; requires `MESSAGE_BUS_FAIL_OPEN=true`.
- `MESSAGE_BUS_ASYNC_QUEUE_SIZE`: max async bus queue size before drop/error policy applies (default `1000`).
- `MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS`: shutdown join timeout for async bus worker (default `2.0`).
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (required for `MESSAGE_BUS_BACKEND=kafka`).
- `KAFKA_CLIENT_ID`: Kafka client id used by producer (default `multiagent-app`).
- `RABBITMQ_URL`: RabbitMQ AMQP URL (required for `MESSAGE_BUS_BACKEND=rabbitmq`).
- `UC_AUDIT_WAREHOUSE_ID`: SQL warehouse id used by `uc_table` message bus backend.
- `UC_AUDIT_CATALOG`: Unity Catalog catalog where audit events table is stored.
- `UC_AUDIT_SCHEMA`: Unity Catalog schema where audit events table is stored.
- `UC_AUDIT_TABLE`: Unity Catalog audit table name (default `agent_lifecycle_events`).
- `APPROVAL_BACKEND`: approval persistence backend, `memory` or `uc_table` (default `memory`; use `uc_table` for deployed workflows).
- `APPROVAL_WAREHOUSE_ID`: SQL warehouse used by the UC approval repository.
- `APPROVAL_CATALOG`: Unity Catalog catalog for approval decisions.
- `APPROVAL_SCHEMA`: Unity Catalog schema for approval decisions.
- `APPROVAL_TABLE`: approval Delta table name (default `agent_approval_decisions`).
- `APPROVAL_FAIL_OPEN`: whether approval writes may fail open (default `false`; keep false for production).
- `DATABRICKS_OPENAI_BASE_URL`: optional Databricks OpenAI base URL override (for example Unity AI Gateway URL).
- `DATABRICKS_OPENAI_TIMEOUT_SECONDS`: optional timeout in seconds for Databricks OpenAI calls (`0` keeps SDK defaults).
- `MODEL_ROUTING_ENABLED`: enable deterministic task-type model selection (default `true`).
- `MODEL_ROUTING_DEFAULT_MODEL`: model used for standard lookups and conversational requests.
- `MODEL_ROUTING_REASONING_MODEL`: model used for operational, SQL, support, and troubleshooting requests.
- `MODEL_ROUTING_QUALITY_MODEL`: model used for analysis, comparison, and recommendation requests.
- `EVAL_MIN_TOOL_CALL_ACCURACY`: release-gate threshold for tool call correctness (default `0.80`).
- `EVAL_MIN_AUTH_CORRECTNESS`: release-gate threshold for authorization correctness (default `0.90`).
- `EVAL_MIN_SAFETY`: release-gate threshold for safety KPI (default `0.95`).
- `EVAL_MIN_GROUNDEDNESS`: release-gate threshold for groundedness KPI (default `0.80`).
- `EVAL_REQUIRE_ALL_KPIS`: when `true`, fail release gate if any KPI metric is missing.
- `EVAL_JUDGE_MODEL`: model URI used by MLflow built-in LLM judge scorers (default `databricks:/databricks-claude-sonnet-5`).
- `EVAL_SIMULATOR_USER_MODEL`: model URI used by `ConversationSimulator` to generate simulated user turns (defaults to `EVAL_JUDGE_MODEL`).
- `AGENT_TASK_BACKEND`: delegation task backend; `memory` by default and `uc_table` for durable Delta-backed tasks.
- `AGENT_TASK_WAREHOUSE_ID`: SQL warehouse used by the UC task backend.
- `AGENT_TASK_CATALOG`: Unity Catalog catalog for durable delegation tables.
- `AGENT_TASK_SCHEMA`: Unity Catalog schema for durable delegation tables.
- `AGENT_TASK_TABLE`: task table name (default `agent_delegation_tasks`).
- `AGENT_TASK_EVENT_TABLE`: task event table name (default `agent_delegation_events`).
- `AGENT_TASK_WORKER_ENABLED`: starts the backend delegation worker when `true`.
- `AGENT_TASK_WORKER_POLL_SECONDS`: idle polling interval for the delegation worker (default `1.0`).

For the store intervention workflow, start with the [HITL approval guide](docs/governance/human-in-the-loop.md). It documents the discovery query, evidence requirement, approval states, API calls, UC persistence, and post-deployment verification.

The specialist App is also declared in DAB as `hitl-app-agent`; set `hitl_app_name`, `hitl_sql_warehouse_id`, and the `hitl_*_table` variables in the target overlay before bundle deployment.

Update the specialist App source or its data privileges with:

```bash
make update-hitl APP_NAME=hitl-app-agent PROFILE=DEFAULT
make grant-hitl-privileges APP_NAME=hitl-app-agent PROFILE=DEFAULT
```

MCP connect/probe performance controls:

- `MCP_CONNECT_TIMEOUT_SECONDS`: timeout for MCP async context connection (default `10`).
- `MCP_LIST_TOOLS_TIMEOUT_SECONDS`: timeout for MCP `list_tools` probe (default `30`).
- `MCP_HEALTH_TTL_SECONDS`: cached healthy MCP status TTL in seconds (default `30`).
- `MCP_HEALTH_FAILURE_TTL_SECONDS`: cached unhealthy MCP status TTL in seconds (default `10`).
- `ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE`: max in-memory cached static instruction variants (default `128`).

## Runtime Status

- Current package version: `1.0.0`.
- Lakebase uses an OAuth credential minted from the Databricks Postgres credentials API; the app service principal needs a matching Lakebase OAuth role and `postgres` app resource grant.
- The orchestrator selects a configured Databricks model by task type and records the selected model, task type, and reason in `routing.plan.selected` lifecycle metadata.
- The UI renders `response.output_text.delta` events and source/tool badges. It does not render raw function, MCP, or tool-output events.
- Local source deploys are lifecycle-gated, but bundle-managed resource changes still require a successful bundle apply.
- Dev uses the UC-backed delegation task store with `agent_delegation_tasks` and `agent_delegation_events`; the backend lifespan starts a bounded worker and exposes payload-redacted status at `GET /delegations/{task_id}`.
- The app deployment and durable-task round trip are verified. Direct authenticated endpoint probes still encounter the known platform `502` before backend responses are available.
- Auth correctness, safety, and groundedness block the evaluation release gate. Tool-call accuracy is monitored with `DataToolAttempt` and trace triage but remains non-blocking while MLflow cannot reliably score nested tool spans.

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow and project docstring standard.
- [COPYRIGHT](COPYRIGHT): project copyright notice and usage restrictions.
- [docs/product/business-specs.md](docs/product/business-specs.md): business requirements, constraints, and success metrics.
- [docs/architecture/runtime-technical-specs.md](docs/architecture/runtime-technical-specs.md): centralized technical implementation map and cross-space contracts.
- [docs/quality/evaluation-spec.md](docs/quality/evaluation-spec.md): datasets, scorers, KPI thresholds, and release-gate rules.
- [Proposed Model Experiment Matrix](docs/quality/evaluation-spec.md#proposed-model-experiment-matrix): environment-specific model profile guidance for dev, qa, stg, and prd release planning.
- [docs/governance/prompt-policy-controls.md](docs/governance/prompt-policy-controls.md): prompt layering and deterministic policy/guardrail behavior.
- [docs/architecture/tool-and-model-registry.md](docs/architecture/tool-and-model-registry.md): registry of active tools, endpoints, and Genie Agents.
- [docs/governance/data-contracts-lineage.md](docs/governance/data-contracts-lineage.md): data contracts, classification, and lineage requirements.
- [docs/governance/business-semantics-metadata.md](docs/governance/business-semantics-metadata.md): reliable business semantics and required AI metadata contract.
- [docs/governance/security-threat-model.md](docs/governance/security-threat-model.md): trust boundaries, threats, and controls.
- [docs/operations/cost-performance-budget.md](docs/operations/cost-performance-budget.md): latency/cost budget framework and operating signals.
- [docs/operations/mlflow-rollout-checklist.md](docs/operations/mlflow-rollout-checklist.md): one-page MLflow rollout checklist with owners, tasks, and acceptance criteria.
- [docs/operations/mlflow-rollout-tracker.md](docs/operations/mlflow-rollout-tracker.md): live execution tracker template for status, ownership, due dates, dependencies, and evidence.
- [docs/architecture/api-contracts.md](docs/architecture/api-contracts.md): invoke/stream API contract and error semantics.
- [docs/operations/postmortem-template.md](docs/operations/postmortem-template.md): incident and regression postmortem template.
- [docs/architecture/high-level-architecture.md](docs/architecture/high-level-architecture.md): high-level architecture and request flow
- [docs/architecture/runtime-behavior-and-implementation.md](docs/architecture/runtime-behavior-and-implementation.md): runtime module design and implementation behavior
- [docs/architecture/design-artifacts/README.md](docs/architecture/design-artifacts/README.md): centralized concept, logical, and deployment design diagrams
- [docs/operations/operations-runbook.md](docs/operations/operations-runbook.md): deployment, operations, incident handling, rollback

## Makefile Helpers

Useful operational commands:

- `make redeploy TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT`
- `make upload-wheel TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT`
- `make lint`
- `make format`
- `make grants TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT`
- `make query-dev TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT QUERY='top stores by revenue' QUERY_PERSONA=manager`

## Current Status

- Development environment is active and user-accessible.
- Multi-agent routing across Genie and serving endpoints is implemented.
- Governed routing policy, response guardrails, and lifecycle audit-table persistence are implemented.
- GitHub Actions pipeline supports PR CI and deployment automation for dev, qa, stg, and prd.
- Operational controls and troubleshooting guidance are documented in the runbook.
