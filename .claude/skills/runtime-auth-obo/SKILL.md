---
name: runtime-auth-obo
description: "Implement or update runtime on-behalf-of-user authorization behavior, token-forwarding requirements, and auth-mode enforcement. Use when: changing app vs obo auth rules, forwarded token handling, or auth validation outcomes."
---

# Runtime Auth OBO

Use this skill to change authentication and authorization runtime logic related to `app` and `obo` execution paths.

## Scope

This skill covers:

- Auth mode enforcement per subagent.
- Forwarded user token requirements for `obo` routes.
- Deterministic authorization error behavior.

This skill does not cover:

- New route design (use runtime-routing).
- New permission grant resources (use add-tools).

## Preconditions

- Target selected and profile available.
- Tool routes have explicit auth mode decisions.
- Required test personas and token scenarios are prepared.

## Files Typically Changed

- `src/aiserver/application/auth/context.py`
- `src/aiserver/application/orchestration/agent.py`
- `src/aiserver/domain/subagents.<target>.json`
- `tests/test_runtime_auth.py`
- `docs/governance/security-threat-model.md`

## Workflow

### 1) Define auth contract

- Decide which routes are `app` and which are `obo`.
- Define user-facing failure behavior for missing or invalid forwarded token.

### 2) Implement auth checks

- Enforce `obo` token presence before tool execution.
- Ensure no silent fallback from `obo` to `app`.

### 3) Validate route metadata

- Confirm each affected subagent has the intended `auth_mode`.

### 4) Validate behavior locally

- Positive path: `obo` route with forwarded token.
- Negative path: `obo` route without token.
- Control path: `app` route without forwarded token.

### 5) Deploy and verify

```bash
databricks bundle validate -t <target> --profile <profile>
make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>
```

## Validation Commands

```bash
uv run pytest -q tests/test_runtime_auth.py tests/test_orchestrator_service.py tests/test_subagent_config.py
uv run runtime-preflight
```

## Rollback and Fallback

- Revert auth behavior changes and subagent auth-mode edits.
- Redeploy via standard flow or runbook fallback if needed.

## Related Assets

- `examples/auth-mode-matrix.md`
- `examples/obo-validation-cases.md`
- `checklists/pre-deploy.md`
- `checklists/post-deploy.md`
