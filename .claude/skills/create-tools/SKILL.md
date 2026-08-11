---
name: create-tools
description: "Create or prepare Databricks resources this app can route to. Use when: required Genie Agents/endpoints/resources do not exist yet."
---

# Create Tools

Use this skill when the target resource does not exist yet.

## Resource Types Typically Used by This Repo

- Genie Agent space (for `type: genie` routes)
- Model Serving endpoint with Responses API support (for `type: serving_endpoint` routes)
- Databricks App endpoint (for `type: app` routes)
- AI Search MCP route (for `type: mcp` routes)

## Workflow

1. Discover current resources:

```bash
uv run discover-tools --profile <profile>
```

2. Create missing resources in Databricks (UI or CLI/API based on org standard).

3. Capture final identifiers:
- Genie: `space_id`
- Serving endpoint: endpoint name
- App specialist: app name

4. Wire resources into project config:
- `backend/domain/subagents.<target>.json`
- `targets/<env>.yml` variables
- `resources/multiagent_app.yml` app resource permissions

5. Validate and deploy:

```bash
databricks bundle validate -t <target> --profile <profile>
databricks bundle deploy -t <target> --profile <profile>
```
