# Claude Skills Guide

## Purpose

This is the operator guide for using Claude skills in this repository.
It defines the active skill set, how to invoke selected skills in Claude Code, and the safest default execution flow.

## Scope

Applies only to active skills under `.claude/skills/` for this project:

- `environment-quickstart`
- `environment-run-local`
- `capability-discover`
- `capability-create`
- `capability-register`
- `behavior-modify`
- `release-deploy`
- `governance-routing`
- `governance-guardrails`
- `governance-auth-obo`
- `observability-audit`

## Start Here

Use this default sequence unless you have a specific reason to skip steps:

1. `environment-quickstart` (only when environment/auth is not ready)
2. `capability-discover`
3. `capability-create` (only if required resources do not exist)
4. `capability-register`
5. `behavior-modify`
6. `environment-run-local`
7. `release-deploy`

## Skill Matrix

| Skill | Use For | Primary Outputs |
| ---- | ---- | ---- |
| `environment-quickstart` | Local setup and auth bootstrap | working `.env`, profile, MLflow setup |
| `environment-run-local` | Local run, smoke tests, troubleshooting | healthy local app and `/invocations` checks |
| `capability-discover` | Identify available Databricks resources | Genie IDs, endpoint names, integration inventory |
| `capability-create` | Provision missing workspace resources | new Genie/endpoint/app resources to integrate |
| `capability-register` | Add routing + resource permissions | updated `src/aiserver/contracts/subagents.<target>.json` and `resources/multiagent_app.yml` |
| `behavior-modify` | Change orchestration behavior | updated backend orchestration/request logic |
| `release-deploy` | Validate, deploy, and restart by target | deployed app and runtime verification |
| `governance-routing` | Change orchestrator tool selection and policy-aware subagent targeting | updated route rules and route metadata |
| `governance-guardrails` | Change sensitive-output rules and evidence/citation enforcement | updated guardrail checks and blocked-output controls |
| `governance-auth-obo` | Change app vs OBO auth rules and forwarded-token handling | updated auth-mode enforcement and validation outcomes |
| `observability-audit` | Change message bus backend, event schemas, or async publish behavior | updated lifecycle auditing and observability checks |

## Claude Code Usage (Selected Skills)

Explicitly request selected skills in your prompt. This reduces ambiguity and keeps execution aligned with project conventions.

### Prompt Template

```text
Use selected skills: <skill-1>[, <skill-2>, ...]
Goal: <expected result>
Context: target=<target> profile=<profile> env/files=<optional details>
Constraints: <guardrails such as bind-not-delete, read-only, no deployment>
```

### Example Prompts

```text
Use selected skills: environment-quickstart
Goal: Initialize this repo and verify local startup.
Context: profile=dev
Constraints: Do not deploy.
```

```text
Use selected skills: capability-discover, capability-register, environment-run-local
Goal: Add a new serving endpoint subagent and validate locally.
Context: target=dev profile=dev
Constraints: Keep endpoint values in targets/dev.yml variables.
```

```text
Use selected skills: release-deploy
Goal: Deploy latest changes to qa and verify logs and status.
Context: target=qa profile=qa app=multiagent-app-qa
Constraints: If app exists, bind instead of delete.
```

## Skill Details

### environment-quickstart

- Command: `uv run assistant-bootstrap`
- Use when: first setup, auth/profile setup, missing `.env`, missing `MLFLOW_EXPERIMENT_ID`
- Verify:
  - `databricks auth profiles`
  - `uv run runtime-preflight`
  - `uv run runtime-serve-app`

### environment-run-local

- Commands:
  - `uv run runtime-serve-app`
  - `uv run runtime-serve-backend --reload`
  - `uv run runtime-preflight`
- API smoke test: `http://localhost:8000/invocations`

### capability-discover

- Command: `uv run assistant-discover-tools --profile <profile>`
- Capture:
  - Genie `space_id`
  - serving endpoint names
  - relevant UC resources

### capability-create

- Use when required resources are missing in the target workspace.
- Typical resources in this repo:
  - Genie Agent space
  - Responses-compatible serving endpoint
  - Databricks app endpoint for specialist routing

### capability-register

- Update routing in `src/aiserver/contracts/subagents.<target>.json`.
- Update app resource permissions in `resources/multiagent_app.yml`.
- Supported subagent types:
  - `genie` requires `space_id`
  - `serving_endpoint` requires `endpoint`
  - `app` requires `endpoint`
  - `mcp` requires `mcp_url`
  - `lakebase` requires `project_id`, `branch_id`, `endpoint_id`, `database`, `pg_host`, and an app identity with a matching Lakebase OAuth role

### behavior-modify

- Primary files:
  - `src/aiserver/api/invocations.py`
  - `src/aiserver/application/adapters/tools.py`
  - `src/aiserver/application/orchestration/agent.py`
  - `src/aiserver/application/auth/context.py`
  - `src/aiserver/contracts/subagents.py`
  - `src/aiserver/contracts/subagents.dev.json` (and other target variants)
  - `src/aiserver/application/runtime/requests.py`
  - `src/aiserver/application/runtime/identity.py`
- Validate:
  - `python -m py_compile src/aiserver/*.py src/operations/*.py`
  - `uv run runtime-preflight`

### release-deploy

- Standard flow: use the explicit DAB and Databricks Apps deployment sequence in the operations runbook.
- Targets: `dev`, `qa`, `stg`, `prd`
- Source-only fallback: `make build-app-source TARGET=<target>` if Terraform Registry is unavailable; successful bundle apply is still required for resource-grant changes

## Operating Guidelines

1. Always pass `--profile` on Databricks CLI commands.
2. Do not change routing without matching permission/resource updates.
3. Store environment-specific names and IDs in `targets/*.yml` variables.
4. Validate locally before deployment.
5. Keep direct function-tool changes in `application/adapters/tools.py`; MCP and Lakebase use dedicated builders in `application/orchestration/agent.py`, and delegation uses the task-bus handoff flow.
5. Use the explicit deployment sequence so validation, deployment, permissions, and verification remain visible.
6. Prefer app bind over delete when app-name conflicts occur.

## Quick Decision Map

- Cannot run locally: use `environment-quickstart`
- Need IDs/endpoints: use `capability-discover`
- Resource missing: use `capability-create`
- Resource exists but access fails: use `capability-register`
- Behavior change needed: use `behavior-modify`
- Need local verification: use `environment-run-local`
- Ready to ship: use `release-deploy`

## Related Docs

- `docs/architecture/high-level-architecture.md`
- `docs/architecture/runtime-behavior-and-implementation.md`
- `docs/operations/operations-runbook.md`
