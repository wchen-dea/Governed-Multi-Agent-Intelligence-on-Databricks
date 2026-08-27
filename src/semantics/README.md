# Semantics Layer

Databricks notebooks that build and refresh the governed data assets behind the
runtime tools registered in [`docs/architecture/tool-and-model-registry.md`](../../docs/architecture/tool-and-model-registry.md).

See [`docs/architecture/semantics-layer-design.md`](../../docs/architecture/semantics-layer-design.md)
for the semantics layer design and ownership boundaries (this project builds AI
Search indexes and Metric Views only; Genie Agent spaces and the Lakebase
project are owned by other projects).

Each notebook is idempotent and is intended to run as a Databricks Job (see
`resources/semantics_jobs.yml`), not interactively against production data.

## Notebooks

| Notebook | Produces | Backs |
| --- | --- | --- |
| [create_dim_product_search_index.py](create_dim_product_search_index.py) | `dim_product_search_index` Vector Search index | `product_index_assistant` MCP tool |
| [create_flink_support_index.py](create_flink_support_index.py) | `flink_support_index` Vector Search index | `flink_support_agent` MCP tool |
| [create_fct_cdi_trusted_expert_score_metric_view.py](create_fct_cdi_trusted_expert_score_metric_view.py) | `fct_cdi_trusted_expert_score_metric_view` Unity Catalog Semantic Metric View | `cdi_agent` Genie Agent |

## Conventions

- Notebooks take `catalog`/`schema` widgets and default to `quickstart_catalog.multi_agent_schema`, matching the bundle's `semantics_catalog`/`semantics_schema` variables.
- Source tables/views are expected to already exist upstream (raw ingestion or staging pipelines); these notebooks own curation, index creation, and metric view publication only.
- Re-running a notebook refreshes the existing index/table/view rather than failing.
