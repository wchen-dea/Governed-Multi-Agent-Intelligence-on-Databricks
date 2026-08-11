# Model and Tool Registry

Inventory of active model endpoints, tools, Genie Agents, and MCP routes.

## Purpose

Provide an auditable and maintainable registry for runtime integrations and ownership.

## Registry Fields

- id
- type (genie, serving_endpoint, app, mcp, model)
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
- MCP URL: `/api/2.0/mcp/ai-search/dt_dev_gold/dwh_dbx/dim_product_search_index`
- Backing AI Search endpoint: `knowledge-assistant-product-ep`
- Auth mode: app
- Classification: internal
- Owner: platform-docs
- Status: active

## Other Environments

- QA/STG/PROD currently include additional placeholder and serving-endpoint entries.
- Entries with placeholder identifiers are skipped at runtime until concrete IDs are configured.

## Maintenance Rules

- Registry updates are required whenever any `src/backend/domain/subagents.<target>.json` changes.
- Deprecated entries must include migration guidance and removal timeline.
- Runtime, bundle variables, and app permissions must remain consistent.

## Related Documents

- technical-specs.md
- ../product/business-specs.md
- system-architecture.md
