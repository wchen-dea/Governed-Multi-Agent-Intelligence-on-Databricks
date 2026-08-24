# Databricks notebook source
# MAGIC %md
# MAGIC # Build fct_cdi_trusted_expert_score_metric_view
# MAGIC
# MAGIC Publishes the Unity Catalog Semantic Metric View backing the `cdi_agent` Genie
# MAGIC Agent. Mirrors the deployed definition of
# MAGIC `quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view`:
# MAGIC a base fact (`fct_cdi`) joined to daily rolling, total time score, and trusted
# MAGIC expert score assets. See the
# MAGIC [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint).
# MAGIC
# MAGIC Run as a Databricks Job (see `resources/semantics_jobs.yml`). Safe to re-run.

# COMMAND ----------

dbutils.widgets.text("catalog", "quickstart_catalog", "Unity Catalog catalog")
dbutils.widgets.text("schema", "multi_agent_schema", "Unity Catalog schema")
dbutils.widgets.text("source_table", "dt_prod_gold.dwh_dbx.fct_cdi", "Base CDI fact asset")
dbutils.widgets.text("cdi_daily_table", "cdi_daily", "Daily rolling aggregate join source (many_to_one)")
dbutils.widgets.text(
    "total_time_score_table", "total_time_score", "Total time score join source (one_to_many)"
)
dbutils.widgets.text(
    "trusted_expert_score_table", "trusted_expert_score", "Trusted expert score join source (one_to_many)"
)
dbutils.widgets.text(
    "metric_view", "fct_cdi_trusted_expert_score_metric_view", "Target metric view name"
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
source_table = dbutils.widgets.get("source_table")
cdi_daily_table = dbutils.widgets.get("cdi_daily_table")
total_time_score_table = dbutils.widgets.get("total_time_score_table")
trusted_expert_score_table = dbutils.widgets.get("trusted_expert_score_table")
metric_view = dbutils.widgets.get("metric_view")

full_metric_view = f"{catalog}.{schema}.{metric_view}"
full_cdi_daily_table = f"{catalog}.{schema}.{cdi_daily_table}"
full_total_time_score_table = f"{catalog}.{schema}.{total_time_score_table}"
full_trusted_expert_score_table = f"{catalog}.{schema}.{trusted_expert_score_table}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify the base fact asset and join sources exist

# COMMAND ----------

for full_name in (
    source_table,
    full_cdi_daily_table,
    full_total_time_score_table,
    full_trusted_expert_score_table,
):
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
# MAGIC `Avg Recommend Score`, `Avg Salesperson Score`, `Avg Time Score`,
# MAGIC `Avg Service Score`). `total_time_score` and `trusted_expert_score` are joined
# MAGIC in to support future measures from those assets.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {full_metric_view}
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {source_table}
joins:
  - name: cdi_daily
    source: {full_cdi_daily_table}
    on: source.store_code = cdi_daily.store_code AND source.activity_date = cdi_daily.activity_date
  - name: total_time_score
    source: {full_total_time_score_table}
    on: source.response_id = total_time_score.response_id
  - name: trusted_expert_score
    source: {full_trusted_expert_score_table}
    on: source.response_id = trusted_expert_score.response_id
dimensions:
  - name: store_code
    expr: source.store_code
    comment: Code assigned to the store location
  - name: activity_date
    expr: source.activity_date
    comment: Date of the service activity
  - name: appointment_indicator
    expr: source.appointment_indicator
    comment: Whether the service was by appointment
  - name: source_system_name
    expr: source.source_system_name
    comment: Origin system of the data
  - name: prior_period
    expr: cdi_daily.prior_period
    comment: Label identifying the prior comparison period
measures:
  - name: Response Count
    expr: COUNT(DISTINCT source.response_id)
    comment: Total distinct customer survey responses
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: Avg Recommend Score
    expr: AVG(source.recommend_delight)
    comment: Average customer recommendation delight score
    format:
      type: number
      decimal_places:
        type: exact
        places: 2
  - name: Avg Salesperson Score
    expr: AVG(source.salesperson_delight)
    comment: Average salesperson interaction delight score
    format:
      type: number
      decimal_places:
        type: exact
        places: 2
  - name: Avg Time Score
    expr: AVG(source.time_delight)
    comment: Average timeliness delight score
    format:
      type: number
      decimal_places:
        type: exact
        places: 2
  - name: Avg Service Score
    expr: AVG(source.service_delight)
    comment: Average service delight score
    format:
      type: number
      decimal_places:
        type: exact
        places: 2
$$
COMMENT 'CDI (Customer Delight Index) metrics combining individual survey responses, daily rolling aggregates, total time scores, and trusted expert scores.'
""")

print(f"Published metric view {full_metric_view} from {source_table}.")
