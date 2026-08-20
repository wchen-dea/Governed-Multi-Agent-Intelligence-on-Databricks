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

## Active Genie Agents (Dev)

Typical source pattern for Genie Agents:

- Use Unity Catalog Semantic Metric Views as the semantic source layer for business metrics and KPI queries.
- Blueprint reference: [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint)

### sales_insights_agent

- Type: genie
- Runtime name: `sales_insights_agent`
- Space ID source: `src/backend/domain/subagents.dev.json`
- Auth mode: app
- Classification: confidential
- Owner: sales-analytics
- Status: active

## Active MCP Routes (Dev)

### product_index_assistant

- Type: mcp
- Runtime name: `product_index_assistant`
- MCP URL: `/api/2.0/mcp/ai-search/quickstart_catalog/multi_agent_schema/dim_product_search_index`
- Backing AI Search endpoint: `knowledge-assistant-product-ep`
- Auth mode: app
- Classification: internal
- Owner: platform-docs
- Status: active

### flink_support_agent

- Type: mcp
- Runtime name: `flink_support_agent`
- MCP URL: `/api/2.0/mcp/ai-search/quickstart_catalog/multi_agent_schema/flink_support_search_index`
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
- Auth mode: app
- Classification: confidential
- Owner: customer-experience
- Status: active

## Other Environments

- QA/STG/PROD currently include additional placeholder and serving-endpoint entries.
- Entries with placeholder identifiers are skipped at runtime until concrete IDs are configured.

## Active Lakebase Agents (Dev)

### lakebase_ods_agent

- Type: lakebase
- Runtime name: `lakebase_ods_agent`
- Project: `ore` (uid: `3ab05603-06dc-4789-a7fb-234d22a71e4b`)
- Branch: `production` (uid: `br-fragrant-sea-d1h720m5`)
- Endpoint: `primary` (host: `ep-falling-cake-d1j29nc5.database.us-west-2.cloud.databricks.com`)
- Database: `operationaldatastore`
- Auth mode: app
- Classification: confidential
- Owner: data-platform
- Status: active

## Maintenance Rules

- Registry updates are required whenever any `src/backend/domain/subagents.<target>.json` changes.
- Deprecated entries must include migration guidance and removal timeline.
- Runtime, bundle variables, and app permissions must remain consistent.

## Related Documents

- runtime-technical-specs.md
- ../product/business-specs.md
- high-level-architecture.md
