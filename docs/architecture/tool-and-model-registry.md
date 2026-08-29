# Model and Tool Registry

Inventory of active model endpoints, tools, Genie Agents, and MCP routes.

## Purpose

Provide an auditable and maintainable registry for runtime integrations and ownership.

## Registry Fields

- id
- type (genie, serving_endpoint, app, mcp, lakebase, model)
- runtime name
- owner
- auth mode
- data classification
- freshness SLA
- environment availability
- status (active, deprecated, disabled)

## Configuration Source

- Runtime subagent config is environment-specific:
	- `src/aiserver/contracts/subagents.dev.json`
	- `src/aiserver/contracts/subagents.qa.json`
	- `src/aiserver/contracts/subagents.stg.json`
	- `src/aiserver/contracts/subagents.prd.json`

## Semantics Layer Build Automation

- Notebooks: `src/semantics/` (see [src/semantics/README.md](../../src/semantics/README.md))
- Design and ownership boundaries: [Semantics layer design](semantics-layer-design.md) — this project builds AI Search indexes and Metric Views only; Genie Agent spaces and the Lakebase project are owned by other projects.
- Jobs: `resources/semantics_jobs.yml` (one Databricks Job per notebook, run on demand or scheduled per target)
- `create_dim_product_search_index.py` curates `dim_product` and builds/refreshes the `dim_product_search_index` Vector Search index.
- `create_flink_support_index.py` extracts the support KB volume into `flink_support_kb` and builds/refreshes the `flink_support_index` Vector Search index.
- `create_fct_cdi_trusted_expert_score_metric_view.py` publishes the `fct_cdi_trusted_expert_score_metric_view` Unity Catalog Semantic Metric View from `dt_prod_gold.dwh_dbx.fct_cdi` and its `cdi_daily`/`total_time_score`/`trusted_expert_score` joins.

## Active Genie Agents (Dev)

Typical source pattern for Genie Agents:

- Use Unity Catalog Semantic Metric Views as the semantic source layer for business metrics and KPI queries.
- Blueprint reference: [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint)

### sales_insights_agent

- Type: genie
- Runtime name: `sales_insights_agent`
- Space ID source: `src/aiserver/contracts/subagents.dev.json`
- Genie space created and owned by the Genie/analytics project; this project only registers the space id and routes to it via MCP.
- Auth mode: app
- Classification: confidential
- Owner: sales-analytics
- Status: active

## Active MCP Routes (Dev)

### product_index_assistant

- Type: mcp
- Runtime name: `product_index_assistant`
- MCP URL: `/api/2.0/mcp/vector-search/quickstart_catalog/multi_agent_schema/dim_product_search_index`
- Backing AI Search endpoint: `product_index_ep`
- Auth mode: app
- Classification: internal
- Owner: platform-docs
- Status: active

### flink_support_agent

- Type: mcp
- Runtime name: `flink_support_agent`
- MCP URL: `/api/2.0/mcp/ai-search/quickstart_catalog/multi_agent_schema/flink_support_index`
- Source: RAG over `/Volumes/quickstart_catalog/multi_agent_schema/support_kb`
- Auth mode: app
- Classification: internal
- Owner: platform-support
- Status: active

## Active Genie Agents (Dev) — CDI

### cdi_agent

- Type: genie
- Runtime name: `cdi_agent`
- Space ID source: `src/aiserver/contracts/subagents.dev.json`
- Source: materialized view `quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view`
- Genie space created and owned by the Genie/analytics project; this project only registers the space id and routes to it via MCP.
- Auth mode: app
- Classification: confidential
- Owner: customer-experience
- Status: active

## Active Approval Agent (Dev)

### store-intervention-agent

- Type: app
- Runtime name: `store-intervention-agent`
- Endpoint: `store-intervention-agent`
- Auth mode: app
- Allowed persona: manager
- Classification: confidential
- Owner: sales-operations
- Evidence: required; responses must contain a citation or `Source:` line
- Human approval: required before any operational recommendation or dispatch
- Persistence: `APPROVAL_BACKEND=uc_table` in dev, table `quickstart_catalog.multi_agent_schema.agent_approval_decisions`
- Specialist source: `src/hitl-agent/` (update with `make update-hitl`)
- Specialist privileges: `make grant-hitl-privileges` grants warehouse `CAN_USE`, UC catalog/schema use, and table-level `SELECT`
- Status: active

This agent prepares an approval packet from revenue and CDI signals. It is not a dispatch executor. See [Human-in-the-loop approval](../governance/human-in-the-loop.md).

The App specialist is deployed as the existing Databricks App `store-intervention-agent`; its source is exported under `src/hitl-agent/`. Follow the [creation procedure](../governance/human-in-the-loop.md#create-store-intervention-agent) for a new environment and use the update/grant helpers for ongoing changes.

## Other Environments

- QA/STG/PRD define the same 6 subagents as dev (`sales_insights_agent`, `product_index_assistant`, `flink_support_agent`, `cdi_agent`, `store-intervention-agent`, `lakebase_ods_agent`), aligned in shape and `auth_mode`/`requires_evidence` settings.
- `cdi_agent.space_id` and `lakebase_ods_agent`'s Lakebase connection fields (`project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host`, `pg_user`) remain placeholders in QA/STG/PRD until those resources are provisioned per environment.
- Entries with placeholder identifiers are skipped at runtime until concrete IDs are configured.

## Active Model Routes (Dev)

Model selection is deterministic and recorded with `routing.plan.selected`; it chooses a configured route before agent construction and is not proof that a downstream tool call succeeded.

Routes are evaluated through one ordered rule set. Synthesis has precedence over reasoning when both match, so mixed recommendation/analysis prompts use the quality route instead of the operational route.

| Task type | Configured model | Examples |
| --- | --- | --- |
| standard | `databricks-gpt-5-6-luna` | product lookups and ordinary conversation |
| reasoning | `databricks-claude-sonnet-5` | appointments, orders, SQL, Flink, and troubleshooting |
| synthesis | `databricks-claude-sonnet-5` | analysis, comparisons, summaries, and recommendations |

Selection rationale:

| Route | Quality | Cost | Efficiency |
| --- | --- | --- | --- |
| standard | Good enough for conversational and lookup turns, especially when answers are tool-grounded. | Keeps lower-cost traffic on the balanced default route. | Minimizes latency for common requests. |
| reasoning | Better fit for multi-step planning, SQL generation, and troubleshooting. | Higher cost is justified when it reduces failed tool attempts and support triage. | Improves first-pass task completion on operational questions. |
| synthesis | Better fit for comparative analysis, executive summaries, and recommendations. | Reserved for requests where quality affects decisions or approval packets. | Reduces back-and-forth on complex summary work. |

Auth correctness, safety, and groundedness remain blocking promotion KPIs. [ToolCallCorrectness](../quality/evaluation-spec.md) is monitored but non-blocking while the MLflow scorer cannot reliably assess nested tool spans.

## Environment Model Profiles

Model route values are target-specific because each environment has a different SLA and promotion purpose.

| Target | SLA posture | Standard route | Reasoning route | Synthesis route |
| --- | --- | --- | --- | --- |
| dev | Fast iteration and cost control | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| qa | Production-parity regression checks | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| stg | Quality-first pre-production validation | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| prd | Balanced user-facing latency, cost, and quality | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |

## Active Lakebase Agents (Dev)

### lakebase_ods_agent

- Type: lakebase
- Runtime name: `lakebase_ods_agent`
- Project: `ore` (resource path: `projects/ore`)
- Branch: `production` (resource path: `projects/ore/branches/production`)
- Endpoint: `primary` (host: `ep-falling-cake-d1j29nc5.database.us-west-2.cloud.databricks.com`)
- Database: `operations`
- Database resource: `projects/ore/branches/production/databases/db-j7lf-e5xmy0cwq4` (runtime database name: `operations`)
- Auth mode: app
- Credential source: Databricks Postgres credentials API, using the app identity's OAuth database role.
- Query contract: one optional schema-discovery query followed by one data query; `LAKEBASE_QUERY_FAILED` is not retried.
- Classification: confidential
- Owner: data-platform
- Status: active

### Conversation memory (Lakebase, not a subagent)

Conversation/persona memory (`MEMORY_BACKEND=lakebase`) uses a separate Lakebase database from `lakebase_ods_agent`, dedicated to agent memory only:

- Project: `ore`, Branch: `production`, Endpoint: `primary` (same Lakebase Autoscaling instance as `lakebase_ods_agent`)
- Database: `agent_memory` (distinct from the `operations` database used by `lakebase_ods_agent`)
- Tables: `agent_conversations`, `agent_preferences` (auto-created via `CREATE TABLE IF NOT EXISTS` on first connect; configurable via `MEMORY_CONVERSATION_TABLE`/`MEMORY_PREFERENCE_TABLE`)
- Configured via `memory_*` variables in `targets/<target>.yml`, propagated to the app through `resources/multiagent_app.yml`
- Disabled by default (`MEMORY_BACKEND=disabled`); review data classification before enabling persistence of conversation content.

## Maintenance Rules

- Registry updates are required whenever any `src/aiserver/contracts/subagents.<target>.json` changes.
- Deprecated entries must include migration guidance and removal timeline.
- Runtime, bundle variables, and app permissions must remain consistent.

## Related Documents

- [Architecture guide](README.md)
- [Runtime technical specifications](runtime-technical-specs.md)
- [Business specifications](../product/business-specs.md)
- [High-level architecture](high-level-architecture.md)
