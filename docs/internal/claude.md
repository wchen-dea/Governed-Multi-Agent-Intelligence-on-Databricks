# Claude Skills Guide

## Purpose

This is the operator guide for using Claude skills in this repository.
It defines the active skill set, how to invoke selected skills in Claude Code, and the safest default execution flow.

## Scope

Applies only to active skills under `.claude/skills/` for this project:

- `quickstart`
- `run-locally`
- `discover-tools`
- `create-tools`
- `add-tools`
- `modify-agent`
- `deploy`

## Start Here

Use this default sequence unless you have a specific reason to skip steps:

1. `quickstart` (only when environment/auth is not ready)
2. `discover-tools`
3. `create-tools` (only if required resources do not exist)
4. `add-tools`
5. `modify-agent`
6. `run-locally`
7. `deploy`

## Skill Matrix

| Skill | Use For | Primary Outputs |
| ---- | ---- | ---- |
| `quickstart` | Local setup and auth bootstrap | working `.env`, profile, MLflow setup |
| `run-locally` | Local run, smoke tests, troubleshooting | healthy local app and `/invocations` checks |
| `discover-tools` | Identify available Databricks resources | Genie IDs, endpoint names, integration inventory |
| `create-tools` | Provision missing workspace resources | new Genie/endpoint/app resources to integrate |
| `add-tools` | Add routing + resource permissions | updated `src/aiserver/domain/subagents.<target>.json` and `resources/multiagent_app.yml` |
| `modify-agent` | Change orchestration behavior | updated backend orchestration/request logic |
| `deploy` | Validate, deploy, and restart by target | deployed app and runtime verification |

## Claude Code Usage (Selected Skills)

Explicitly request selected skills in your prompt. This reduces ambiguity and keeps execution aligned with project conventions.

### Prompt Template

```text
Use selected skills: <skill-1>[, <skill-2>, ...]
Goal: <expected result>
Context: target=<target> profile=<profile> env/files=<optional details>
Constraints: <guardrails such as bind-not-delete, read-only, no deploy>
```

### Example Prompts

```text
Use selected skills: quickstart
Goal: Initialize this repo and verify local startup.
Context: profile=dev
Constraints: Do not deploy.
```

```text
Use selected skills: discover-tools, add-tools, run-locally
Goal: Add a new serving endpoint subagent and validate locally.
Context: target=dev profile=dev
Constraints: Keep endpoint values in targets/dev.yml variables.
```

```text
Use selected skills: deploy
Goal: Deploy latest changes to qa and verify logs and status.
Context: target=qa profile=qa app=multiagent-app-qa
Constraints: If app exists, bind instead of delete.
```

## Skill Details

### quickstart

- Command: `uv run assistant-bootstrap`
- Use when: first setup, auth/profile setup, missing `.env`, missing `MLFLOW_EXPERIMENT_ID`
- Verify:
  - `databricks auth profiles`
  - `uv run runtime-preflight`
  - `uv run runtime-serve-app`

### run-locally

- Commands:
  - `uv run runtime-serve-app`
  - `uv run runtime-serve-backend --reload`
  - `uv run runtime-preflight`
- API smoke test: `http://localhost:8000/invocations`

### discover-tools

- Command: `uv run assistant-discover-tools --profile <profile>`
- Capture:
  - Genie `space_id`
  - serving endpoint names
  - relevant UC resources

### create-tools

- Use when required resources are missing in the target workspace.
- Typical resources in this repo:
  - Genie Agent space
  - Responses-compatible serving endpoint
  - Databricks app endpoint for specialist routing

### add-tools

- Update routing in `src/aiserver/domain/subagents.<target>.json`.
- Update app resource permissions in `resources/multiagent_app.yml`.
- Supported subagent types:
  - `genie` requires `space_id`
  - `serving_endpoint` requires `endpoint`
  - `app` requires `endpoint`
  - `mcp` requires `mcp_url`
  - `lakebase` requires `project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host`, and an app identity with a matching Lakebase OAuth role

### modify-agent

- Primary files:
  - `src/aiserver/api/handlers.py`
  - `src/aiserver/services/orchestrator_service.py`
  - `src/aiserver/services/runtime_auth_service.py`
  - `src/aiserver/domain/subagent_config.py`
  - `src/aiserver/domain/subagents.dev.json` (and other target variants)
  - `src/aiserver/shared/request_utils.py`
  - `src/aiserver/shared/runtime_utils.py`
- Validate:
  - `python -m py_compile src/aiserver/*.py src/scripts/*.py src/frontend/*.py`
  - `uv run runtime-preflight`

### deploy

- Standard flow:
  - `make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>`
- Targets: `dev`, `qa`, `stg`, `prd`
- Source-only fallback: `make upload-wheel TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>` if Terraform Registry is unavailable; successful bundle apply is still required for resource-grant changes

## Operating Guidelines

1. Always pass `--profile` on Databricks CLI commands.
2. Do not change routing without matching permission/resource updates.
3. Store environment-specific names and IDs in `targets/*.yml` variables.
4. Validate locally before deployment.
5. Use `make redeploy` so validation, deploy, permissions, and smoke checks run in one flow.
6. Prefer app bind over delete when app-name conflicts occur.

## Quick Decision Map

- Cannot run locally: use `quickstart`
- Need IDs/endpoints: use `discover-tools`
- Resource missing: use `create-tools`
- Resource exists but access fails: use `add-tools`
- Behavior change needed: use `modify-agent`
- Need local verification: use `run-locally`
- Ready to ship: use `deploy`

## Related Docs

- `docs/architecture/high-level-architecture.md`
- `docs/architecture/low-level-design.md`
- `docs/operations/operations-runbook.md`
