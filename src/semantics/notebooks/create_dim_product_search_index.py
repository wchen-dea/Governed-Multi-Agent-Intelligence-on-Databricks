# Databricks notebook source
# MAGIC %md
# MAGIC # Build dim_product_search_index
# MAGIC
# MAGIC Curates the `dim_product` source table from the raw product catalog staging
# MAGIC table and creates/refreshes the `dim_product_search_index` Vector Search index
# MAGIC used by the `product_index_assistant` MCP tool.
# MAGIC
# MAGIC Run as a Databricks Job (see `resources/jobs.yml`). Safe to re-run.

# COMMAND ----------

dbutils.widgets.text("catalog", "quickstart_catalog", "Unity Catalog catalog")
dbutils.widgets.text("schema", "multi_agent_schema", "Unity Catalog schema")
dbutils.widgets.text("staging_table", "stg_product_catalog", "Raw product catalog staging table")
dbutils.widgets.text("source_table", "dim_product", "Curated source table for the index")
dbutils.widgets.text("index_name", "dim_product_search_index", "Vector Search index name")
dbutils.widgets.text("endpoint_name", "product_index_ep", "Vector Search endpoint name")
dbutils.widgets.text("embedding_model", "databricks-gte-large-en", "Embedding model endpoint")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
staging_table = dbutils.widgets.get("staging_table")
source_table = dbutils.widgets.get("source_table")
index_name = dbutils.widgets.get("index_name")
endpoint_name = dbutils.widgets.get("endpoint_name")
embedding_model = dbutils.widgets.get("embedding_model")

full_staging_table = f"{catalog}.{schema}.{staging_table}"
full_source_table = f"{catalog}.{schema}.{source_table}"
full_index_name = f"{catalog}.{schema}.{index_name}"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Curate `dim_product` from the raw staging table
# MAGIC
# MAGIC `staging_table` is populated upstream by the product catalog ingestion pipeline.
# MAGIC This step derives the searchable `search_text` column and enables Change Data
# MAGIC Feed so the Delta Sync index can track incremental updates.

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {full_source_table} (
    product_code STRING NOT NULL,
    product_description STRING,
    brand_code STRING,
    article_type STRING,
    search_text STRING
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")

if spark.catalog.tableExists(full_staging_table):
    spark.sql(f"""
    MERGE INTO {full_source_table} AS target
    USING (
        SELECT
            product_code,
            product_description,
            brand_code,
            article_type,
            concat_ws(' | ', product_code, product_description, brand_code, article_type) AS search_text
        FROM {full_staging_table}
    ) AS source
    ON target.product_code = source.product_code
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    """)
    print(f"Refreshed {full_source_table} from {full_staging_table}.")
else:
    print(f"WARNING: staging table {full_staging_table} not found; {full_source_table} left as-is.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Ensure the Vector Search endpoint and Delta Sync index

# COMMAND ----------

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    EndpointType,
    PipelineType,
    VectorIndexType,
)

w = WorkspaceClient()


def _wait_for_endpoint(name: str, timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        ep = w.vector_search_endpoints.get_endpoint(name)
        state = getattr(getattr(ep, "endpoint_status", None), "state", None)
        if state and state.value == "ONLINE":
            print(f"Endpoint {name!r} is ONLINE.")
            return
        time.sleep(15)
    print(f"WARNING: endpoint {name!r} did not reach ONLINE within {timeout}s.")


try:
    w.vector_search_endpoints.get_endpoint(endpoint_name)
    print(f"Endpoint {endpoint_name!r} already exists.")
except Exception:
    print(f"Creating endpoint {endpoint_name!r} …")
    w.vector_search_endpoints.create_endpoint(name=endpoint_name, endpoint_type=EndpointType.STANDARD)
    _wait_for_endpoint(endpoint_name)

try:
    w.vector_search_indexes.get_index(full_index_name)
    print(f"Index {full_index_name!r} already exists; triggering sync.")
    w.vector_search_indexes.sync_index(full_index_name)
except Exception:
    print(f"Creating Delta Sync index {full_index_name!r} …")
    w.vector_search_indexes.create_index(
        name=full_index_name,
        endpoint_name=endpoint_name,
        primary_key="product_code",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=full_source_table,
            embedding_source_columns=[
                EmbeddingSourceColumn(name="search_text", embedding_model_endpoint_name=embedding_model)
            ],
            pipeline_type=PipelineType.TRIGGERED,
        ),
    )

print(f"Done. Index target: {full_index_name}")
