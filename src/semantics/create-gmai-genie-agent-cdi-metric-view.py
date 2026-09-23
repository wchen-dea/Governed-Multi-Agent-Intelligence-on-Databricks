# Databricks notebook source
# MAGIC %md
# MAGIC # Build fct_cdi_trusted_expert_score_metric_view
# MAGIC
# MAGIC Publishes the Unity Catalog Semantic Metric View backing the `cdi_agent` Genie
# MAGIC Agent. Mirrors the deployed definition of
# MAGIC `quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view`:
# MAGIC a base fact (`fct_cdi`) joined to the daily rolling aggregate asset. See the
# MAGIC [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint).
# MAGIC
# MAGIC Run as a Databricks Job (see `resources/semantics_jobs.yml`). Safe to re-run.

# COMMAND ----------

dbutils.widgets.text("catalog", "quickstart_catalog", "Unity Catalog catalog")
dbutils.widgets.text("schema", "multi_agent_schema", "Unity Catalog schema")
dbutils.widgets.text("source_table", "dt_prod_gold.dwh_dbx.fct_cdi", "Base CDI fact asset")
dbutils.widgets.text(
    "cdi_daily_table",
    "dt_prod_gold.dwh_dbx.fct_cdi_daily",
    "Daily rolling aggregate join source (store-level)",
)
dbutils.widgets.text(
    "metric_view", "gmai_genie_agent_cdi_metric_view", "Target metric view name"
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
source_table = dbutils.widgets.get("source_table")
cdi_daily_table = dbutils.widgets.get("cdi_daily_table")
metric_view = dbutils.widgets.get("metric_view")

full_metric_view = f"{catalog}.{schema}.{metric_view}"


def qualify_source_table(table_name: str) -> str:
    """Keep fully qualified upstream names intact; qualify short overrides locally."""
    if table_name.count(".") == 2:
        return table_name
    return f"{catalog}.{schema}.{table_name}"


full_cdi_daily_table = qualify_source_table(cdi_daily_table)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify the base fact asset and join sources exist

# COMMAND ----------

for full_name in (source_table, full_cdi_daily_table):
    if not spark.catalog.tableExists(full_name):
        raise ValueError(
            f"{full_name} not found. Create it upstream before publishing {full_metric_view}."
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Publish the metric view
# MAGIC
# MAGIC Dimensions and measures below mirror the live column list of
# MAGIC `fct_cdi_trusted_expert_score_metric_view` (`store_code`, `activity_date`,
# MAGIC `appointment_indicator`, `source_system_name`, `prior_period`, `Response Count`,
# MAGIC `Avg Recommend Score`, `Avg Salesperson Score`, `Avg Time Score`, and
# MAGIC `Avg Service Score`).

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {full_metric_view}
COMMENT 'CDI (Customer Delight Index) metrics combining individual survey responses and daily rolling aggregates.'
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {source_table}
joins:
  - name: cdi_daily
    source: {full_cdi_daily_table}
    on: source.store_code = cdi_daily.store_code
dimensions:
  - name: store_code
    expr: source.store_code
  - name: activity_date
    expr: source.activity_date
  - name: appointment_indicator
    expr: source.appointment_indicator
  - name: source_system_name
    expr: source.source_system_name
  - name: prior_period
    expr: cdi_daily.prior_period
measures:
  - name: Response Count
    expr: COUNT(DISTINCT source.response_id)
  - name: Avg Recommend Score
    expr: AVG(source.recommend_delight)
  - name: Avg Salesperson Score
    expr: AVG(source.salesperson_delight)
  - name: Avg Time Score
    expr: AVG(source.time_delight)
  - name: Avg Service Score
    expr: AVG(source.service_delight)
$$
""")

print(f"Published metric view {full_metric_view} from {source_table}.")
