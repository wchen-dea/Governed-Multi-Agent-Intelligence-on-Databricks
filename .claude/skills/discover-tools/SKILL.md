---
name: discover-tools
description: "Discover Databricks resources available to this project. Use when: planning tool routing, finding Genie Agent space IDs, or checking serving endpoint names."
---

# Discover Tools

Run discovery before editing subagent/tool config.

## Command

```bash
uv run assistant-discover-tools
```

Useful options:

```bash
uv run assistant-discover-tools --profile <profile>
uv run assistant-discover-tools --catalog <catalog> --schema <schema>
uv run assistant-discover-tools --format json --output tools.json
```

## Typical Outputs to Capture

- Genie Agents (`space_id`)
- Serving endpoints (`endpoint` names)
- UC resources relevant to future tool integrations

## Next Step in This Repo

Update subagent configuration in `backend/domain/subagents.<target>.json` and required app resource grants in `resources/multiagent_app.yml`, then deploy.
