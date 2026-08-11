---
name: add-tools
description: "Wire additional Databricks tools into this app and grant required app permissions. Use when: adding Genie/endpoint integrations or fixing runtime permission failures."
---

# Add Tools

This project routes tools through typed subagent config plus Databricks app resource grants.

## Step 1: Add Routing Configuration

Edit `backend/domain/subagents.<target>.json`:

```python
{
    "name": "sales_insights_agent",
    "type": "genie",
    "space_id": "<genie-space-id>",
    "description": "Sales analytics via Genie"
}
```

```python
{
    "name": "knowledge_assistant",
    "type": "serving_endpoint",
    "endpoint": "<serving-endpoint-name>",
    "description": "Knowledge Q&A"
}
```

```python
{
    "name": "specialist_app",
    "type": "app",
    "endpoint": "<databricks-app-name>",
    "description": "App-based specialist"
}
```

```python
{
  "name": "product_index_assistant",
  "type": "mcp",
  "mcp_url": "/api/2.0/mcp/ai-search/<catalog>/<schema>/<index>",
  "description": "AI Search MCP specialist"
}
```

## Step 2: Grant App Resource Access

Edit `resources/multiagent_app.yml` under `resources.apps.multiagent-app.resources`.

Genie example:

```yaml
- name: genie_space
  genie_space:
    name: Genie Agent Space
    space_id: ${var.genie_space_id}
    permission: CAN_RUN
```

Serving endpoint example:

```yaml
- name: knowledge_assistant_endpoint
  serving_endpoint:
    name: ${var.knowledge_assistant_endpoint_name}
    permission: CAN_QUERY
```

## Step 3: Validate and Deploy

```bash
databricks bundle validate -t <target> --profile <profile>
make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>
```

## Notes

- Add both routing config and resource permission config; either one alone is insufficient.
- Keep target-specific IDs/names in `targets/*.yml` variables where possible.
