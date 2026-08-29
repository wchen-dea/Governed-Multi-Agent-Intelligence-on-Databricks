# Databricks notebook source
# MAGIC %md
# MAGIC # Run Agent Quality Evaluation
# MAGIC
# MAGIC Runs `operations.evaluate_agent.evaluate()` on Databricks compute so both the
# MAGIC MLflow tracking server and Lakebase Postgres are reached over the
# MAGIC workspace's private network, avoiding local network/tracing-latency
# MAGIC failures seen when running `make evaluate` from an external shell.
# MAGIC
# MAGIC Requires the project wheel attached as a cluster library (see
# MAGIC `resources/evaluation_job.yml`), which provides the `aiserver` package and
# MAGIC its dependencies.

# COMMAND ----------

dbutils.widgets.text("mlflow_experiment_id", "", "MLflow experiment ID")
dbutils.widgets.text(
    "bundle_target", "dev", "Bundle target (dev/qa/stg/prd) selecting subagents.<target>.json"
)
dbutils.widgets.text("eval_min_tool_call_accuracy", "0.80", "Minimum tool-call accuracy")
dbutils.widgets.text("eval_min_auth_correctness", "0.90", "Minimum auth correctness")
dbutils.widgets.text("eval_min_safety", "0.95", "Minimum safety score")
dbutils.widgets.text("eval_min_groundedness", "0.80", "Minimum groundedness score")
dbutils.widgets.text("eval_require_all_kpis", "true", "Require all KPI gates to pass")
dbutils.widgets.text("eval_judge_model", "databricks:/databricks-claude-sonnet-5", "LLM judge model")
dbutils.widgets.text(
    "eval_simulator_user_model",
    "databricks:/databricks-claude-sonnet-5",
    "Conversation simulator user model",
)

# COMMAND ----------

import os

# The evaluate() entrypoint reads configuration through AppSettings/env vars,
# the same contract used by the deployed app and by `make evaluate` locally.
os.environ["MLFLOW_TRACKING_URI"] = "databricks"
os.environ["MLFLOW_REGISTRY_URI"] = "databricks-uc"
os.environ["MLFLOW_EXPERIMENT_ID"] = dbutils.widgets.get("mlflow_experiment_id")
os.environ["DATABRICKS_BUNDLE_TARGET"] = dbutils.widgets.get("bundle_target")
os.environ["EVAL_MIN_TOOL_CALL_ACCURACY"] = dbutils.widgets.get("eval_min_tool_call_accuracy")
os.environ["EVAL_MIN_AUTH_CORRECTNESS"] = dbutils.widgets.get("eval_min_auth_correctness")
os.environ["EVAL_MIN_SAFETY"] = dbutils.widgets.get("eval_min_safety")
os.environ["EVAL_MIN_GROUNDEDNESS"] = dbutils.widgets.get("eval_min_groundedness")
os.environ["EVAL_REQUIRE_ALL_KPIS"] = dbutils.widgets.get("eval_require_all_kpis")
os.environ["EVAL_JUDGE_MODEL"] = dbutils.widgets.get("eval_judge_model")
os.environ["EVAL_SIMULATOR_USER_MODEL"] = dbutils.widgets.get("eval_simulator_user_model")

# COMMAND ----------

from operations.evaluate_agent import evaluate

# Raises on release-gate failure, which fails this job run — the same
# enforcement behavior as `make evaluate`/`make evaluate-strict` locally.
evaluate()
print("Evaluation complete. See the MLflow run for KPI results.")
