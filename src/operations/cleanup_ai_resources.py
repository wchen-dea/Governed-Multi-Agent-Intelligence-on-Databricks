# Databricks notebook source
# MAGIC %md
# MAGIC # Clean up multiagent AI resources
# MAGIC
# MAGIC Removes the Genie Agent spaces and AI Search (Vector Search) endpoints/indexes
# MAGIC that back this app's subagents (see `src/aiserver/contracts/subagents.*.json`)
# MAGIC for a given environment.
# MAGIC
# MAGIC Run as a Databricks Job (see `resources/resource_cleanup_job.yml`). Defaults to
# MAGIC a dry run that only prints what would be removed — set `dry_run` to `false` to
# MAGIC actually delete resources.
# MAGIC
# MAGIC **Destructive**: disabling dry-run permanently removes live resources. Only
# MAGIC run with `dry_run=false` against an environment you intend to decommission.

# COMMAND ----------

dbutils.widgets.text("genie_space_ids", "", "Comma-separated Genie Agent space IDs to remove")
dbutils.widgets.text(
    "vector_search_endpoints",
    "",
    "Comma-separated Vector Search endpoint names to remove (with their indexes)",
)
dbutils.widgets.text(
    "dry_run", "true", "Dry run — print the removal plan without deleting anything"
)

genie_space_ids = [s.strip() for s in dbutils.widgets.get("genie_space_ids").split(",") if s.strip()]
vector_search_endpoints = [
    s.strip() for s in dbutils.widgets.get("vector_search_endpoints").split(",") if s.strip()
]
# Only an explicit "false" disables dry-run, so typos/blank values fail safe.
dry_run = dbutils.widgets.get("dry_run").strip().lower() != "false"

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

if dry_run:
    print("DRY RUN — no resources will be deleted. Re-run with dry_run=false to apply.\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Remove Genie Agent spaces

# COMMAND ----------

if not genie_space_ids:
    print("No genie_space_ids provided; skipping Genie Agent cleanup.")

for space_id in genie_space_ids:
    try:
        title = w.genie.get_space(space_id).title
    except Exception as exc:
        print(f"  Skipping Genie space {space_id!r}: not found ({exc}).")
        continue

    if dry_run:
        print(f"  Would trash Genie space {space_id!r} ({title!r}).")
        continue

    try:
        w.genie.trash_space(space_id)
        print(f"  Trashed Genie space {space_id!r} ({title!r}).")
    except Exception as exc:
        print(f"  WARNING: failed to trash Genie space {space_id!r}: {exc}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Remove AI Search indexes and endpoints

# COMMAND ----------

if not vector_search_endpoints:
    print("No vector_search_endpoints provided; skipping AI Search cleanup.")

for endpoint_name in vector_search_endpoints:
    try:
        w.vector_search_endpoints.get_endpoint(endpoint_name)
    except Exception as exc:
        print(f"  Skipping endpoint {endpoint_name!r}: not found ({exc}).")
        continue

    try:
        indexes = list(w.vector_search_indexes.list_indexes(endpoint_name=endpoint_name))
    except Exception as exc:
        print(f"  WARNING: could not list indexes for endpoint {endpoint_name!r}: {exc}")
        indexes = []

    for idx in indexes:
        if dry_run:
            print(f"  Would delete index {idx.name!r} on endpoint {endpoint_name!r}.")
            continue
        try:
            w.vector_search_indexes.delete_index(idx.name)
            print(f"  Deleted index {idx.name!r}.")
        except Exception as exc:
            print(f"  WARNING: failed to delete index {idx.name!r}: {exc}")

    if dry_run:
        print(f"  Would delete endpoint {endpoint_name!r}.")
        continue

    try:
        w.vector_search_endpoints.delete_endpoint(endpoint_name)
        print(f"  Deleted endpoint {endpoint_name!r}.")
    except Exception as exc:
        print(f"  WARNING: failed to delete endpoint {endpoint_name!r}: {exc}")

# COMMAND ----------

print("\nDone." + (" (dry run — nothing deleted)" if dry_run else ""))
