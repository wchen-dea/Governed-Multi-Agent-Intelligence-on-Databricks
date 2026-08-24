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
	- `src/backend/domain/subagents.dev.json`
	- `src/backend/domain/subagents.qa.json`
	- `src/backend/domain/subagents.stg.json`
	- `src/backend/domain/subagents.prod.json`

## Semantics Layer Build Automation

- Notebooks: `src/semantics/notebooks/` (see [src/semantics/README.md](../../src/semantics/README.md))
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
- Space ID source: `src/backend/domain/subagents.dev.json`
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
- Space ID source: `src/backend/domain/subagents.dev.json`
- Source: materialized view `quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view`
- Genie space created and owned by the Genie/analytics project; this project only registers the space id and routes to it via MCP.
- Auth mode: app
- Classification: confidential
- Owner: customer-experience
- Status: active

## Other Environments

- QA/STG/PROD define the same 5 subagents as dev (`sales_insights_agent`, `product_index_assistant`, `flink_support_agent`, `cdi_agent`, `lakebase_ods_agent`), aligned in shape and `auth_mode`/`requires_evidence` settings.
- `cdi_agent.space_id` and `lakebase_ods_agent`'s Lakebase connection fields (`project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host`, `pg_user`) remain placeholders in QA/STG/PROD until those resources are provisioned per environment.
- Entries with placeholder identifiers are skipped at runtime until concrete IDs are configured.

## Active Model Routes (Dev)

Model selection is deterministic and recorded with `routing.plan.selected`; it chooses a configured route before agent construction and is not proof that a downstream tool call succeeded.

| Task type | Configured model | Examples |
| --- | --- | --- |
| standard | `databricks-gpt-5-6-luna` | product lookups and ordinary conversation |
| reasoning | `databricks-gpt-5-6-luna` | appointments, orders, SQL, Flink, and troubleshooting |
| synthesis | `databricks-gpt-5-6-luna` | analysis, comparisons, summaries, and recommendations |

Promotion remains blocked until [ToolCallCorrectness](../quality/evaluation-spec.md) reaches `0.800`; the current measured value is `0.400`.

## Active Lakebase Agents (Dev)

### lakebase_ods_agent

- Type: lakebase
- Runtime name: `lakebase_ods_agent`
- Project: `ore` (resource path: `projects/ore`)
- Branch: `production` (resource path: `projects/ore/branches/production`)
- Endpoint: `primary` (host: `ep-falling-cake-d1j29nc5.database.us-west-2.cloud.databricks.com`)
- Database: `operationaldatastore`
- Database resource: `projects/ore/branches/production/databases/db-j7lf-e5xmy0cwq4` (runtime database name: `operationaldatastore`)
- Auth mode: app
- Credential source: Databricks Postgres credentials API, using the app identity's OAuth database role.
- Query contract: one optional schema-discovery query followed by one data query; `LAKEBASE_QUERY_FAILED` is not retried.
- Classification: confidential
- Owner: data-platform
- Status: active

## Maintenance Rules

- Registry updates are required whenever any `src/backend/domain/subagents.<target>.json` changes.
- Deprecated entries must include migration guidance and removal timeline.
- Runtime, bundle variables, and app permissions must remain consistent.

## Related Documents

- [Architecture guide](README.md)
- [Runtime technical specifications](runtime-technical-specs.md)
- [Business specifications](../product/business-specs.md)
- [High-level architecture](high-level-architecture.md)
