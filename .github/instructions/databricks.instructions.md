---
description: "Databricks application, bundle, Unity Catalog, MCP, and deployment conventions."
applyTo: "databricks.yml,app.yml,targets/**,resources/**,src/semantics/**,src/operations/**,.databricks_app_source/**"
---

# Databricks

- Treat Unity Catalog, identity/OBO behavior, environment targets, and auditability as platform invariants.
- Keep target-specific configuration in `targets/` or the established contract/config files; do not hard-code workspace values.
- Preserve Databricks Apps, Asset Bundles, MLflow, MCP, Genie, AI Search, and Lakebase boundaries already documented by the repository.
- Validate bundle configuration before deployment and never claim deployment success without a real command result.
- Keep generated bundle artifacts and built frontend output out of hand-edited changes.