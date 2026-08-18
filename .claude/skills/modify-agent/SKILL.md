---
name: modify-agent
description: "Modify orchestrator behavior, subagent routing, and request handling for this repository. Use when: changing model/instructions, adding subagents, or adjusting runtime flow."
---

# Modify Agent

## Primary Files (This Repo)

- `backend/api/handlers.py`: invoke/stream handlers and request orchestration wiring
- `backend/services/orchestrator_service.py`: tool/server construction and orchestrator creation
- `backend/services/runtime_auth_service.py`: request-scoped hybrid auth context and trace metadata
- `backend/domain/subagent_config.py`: typed subagent definitions and config loading/validation
- `backend/domain/subagents.<target>.json`: environment-specific subagent routing configuration
- `backend/shared/request_utils.py`: request normalization and MCP error extraction
- `backend/shared/runtime_utils.py`: runtime helpers (workspace host, ids, stream normalization)

## Common Changes

Change orchestrator behavior:

- Update prompts/model/orchestration logic in `backend/services/orchestrator_service.py`.

Add or edit subagents:

- Update entries in `backend/domain/subagents.<target>.json`.
- Supported types: `genie`, `serving_endpoint`, `app`, `mcp`, `lakebase`.
- Required fields:
  - `genie`: `space_id`
  - `serving_endpoint` and `app`: `endpoint`
  - `mcp`: `mcp_url`

Adjust request/response shaping:

- `backend/shared/request_utils.py` for input normalization and surfaced errors.

## Validate After Changes

```bash
python -m py_compile backend/**/*.py scripts/*.py frontend/*.py
uv run preflight
uv run start-app
```
