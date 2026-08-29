---
name: modify-agent
description: "Modify orchestrator behavior, subagent routing, and request handling for this repository. Use when: changing model/instructions, adding subagents, or adjusting runtime flow."
---

# Modify Agent

## Primary Files (This Repo)

- `src/aiserver/api/invocations.py`: invoke/stream handlers and request orchestration pipeline
- `src/aiserver/api/server.py`: MLflow Agent Server bootstrap, app routes, and lifespan hooks
- `src/aiserver/application/orchestration/agent.py`: tool/server construction and orchestrator creation
- `src/aiserver/application/auth/context.py`: request-scoped hybrid auth context and trace metadata
- `src/aiserver/application/auth/policy.py`: persona, auth-mode, and classification policy checks
- `src/aiserver/contracts/subagents.py`: typed subagent definitions and config loading/validation
- `src/aiserver/contracts/subagents.<target>.json`: environment-specific subagent routing configuration
- `src/aiserver/application/runtime/requests.py`: request normalization and MCP error extraction
- `src/aiserver/application/runtime/identity.py`: workspace host, app identity, and OBO identity helpers
- `src/aiserver/application/runtime/streaming.py`: stream event normalization

## Common Changes

Change orchestrator behavior:

- Update prompts/model/orchestration logic in `src/aiserver/application/orchestration/agent.py` and `src/aiserver/application/orchestration/model.py`.

Add or edit subagents:

- Update entries in `src/aiserver/contracts/subagents.<target>.json`.
- Supported types: `genie`, `serving_endpoint`, `app`, `mcp`, `lakebase`.
- Required fields:
  - `genie`: `space_id`
  - `serving_endpoint` and `app`: `endpoint`
  - `mcp`: `mcp_url`

Adjust request/response shaping:

- `src/aiserver/application/runtime/requests.py` for input normalization and surfaced errors.

## Validate After Changes

```bash
python -m compileall -q src/aiserver src/operations scripts
uv run runtime-preflight
uv run runtime-serve-app
```
