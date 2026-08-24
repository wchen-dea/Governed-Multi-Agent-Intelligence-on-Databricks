---
name: runtime-routing
description: "Implement or modify runtime routing behavior for orchestrator tool selection, policy-aware subagent targeting, and auth-mode-aware execution. Use when: adding/changing route rules, route metadata, or routing validations."
---

# Runtime Routing

Use this skill to implement routing changes that affect how requests are mapped to subagents and tools at runtime.

## Scope

This skill covers:

- Subagent metadata and route definitions.
- Routing-policy and persona constraints.
- Auth-mode-aware selection (`app` vs `obo`).
- Runtime validation and deploy checks.

This skill does not cover:

- Creating missing Databricks resources (use `create-tools`).
- New permission grants in app resources (use `add-tools`).

## Preconditions

- Target is selected: `dev`, `qa`, `stg`, or `prod`.
- Databricks profile for target is available.
- Required resource IDs and endpoint names are known.

## Files Typically Changed

- `src/backend/domain/subagents.<target>.json`
- `src/backend/services/orchestrator_service.py`
- `src/backend/services/policy_service.py`
- `src/backend/services/runtime_auth.py`
- `docs/architecture/tool-and-model-registry.md`

## Workflow

### 1) Define routing contract

- Identify user intent, allowed personas, and required evidence behavior.
- Choose `type` (`genie`, `mcp`, `serving_endpoint`, `app`, or `lakebase`).
- Set `auth_mode` based on data sensitivity and user-context needs.

### 2) Update target subagent config

- Add or edit entries in `src/backend/domain/subagents.<target>.json`.
- Populate `name`, route target fields, `description`, `auth_mode`, and classification metadata.
- Avoid placeholders in promoted environments.

### 3) Update policy constraints (if required)

- Enforce persona restrictions and evidence requirements.
- Block disallowed route combinations before tool execution.

### 4) Validate routing behavior locally

- Run config and routing tests first.
- Test positive path: valid persona and valid auth mode.
- Test negative path: missing token for `obo`, disallowed persona, or blocked policy.

### 5) Validate and deploy by target

```bash
databricks bundle validate -t <target> --profile <profile>
make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>
```

### 6) Post-deploy checks

- Confirm invoke and stream behavior.
- Confirm route resolves to expected subagent.
- Confirm policy events and auth outcomes are emitted.

## Validation Commands

```bash
uv run pytest -q tests/test_subagent_config.py tests/test_orchestrator_service.py tests/test_policy_service.py tests/test_runtime_auth.py
uv run runtime-preflight
databricks apps get <app-name> --output json --profile <profile>
```

## Rollback and Fallback

- Revert subagent routing entry to last known good values.
- Re-deploy through standard flow.
- If bundle deploy is blocked by registry outage, use the runbook fallback deploy path.

## Related Assets

- `examples/subagent-routing.json`
- `examples/policy-scenarios.md`
- `checklists/pre-deploy.md`
- `checklists/post-deploy.md`
