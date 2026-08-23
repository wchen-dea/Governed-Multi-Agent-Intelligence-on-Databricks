---
name: runtime-guardrails
description: "Implement or update runtime guardrail behavior for policy checks, evidence requirements, and blocked-output controls. Use when: changing sensitive-output rules, evidence/citation enforcement, or guardrail validation flows."
---

# Runtime Guardrails

Use this skill to modify or extend guardrails that run before and after tool/model execution.

## Scope

This skill covers:

- Guardrail policy evaluation and block conditions.
- Evidence and citation requirement enforcement.
- Sensitive output handling and deterministic fail behavior.

This skill does not cover:

- Routing metadata changes (use runtime-routing).
- New Databricks tool/resource creation (use create-tools/add-tools).

## Preconditions

- Target selected (`dev`, `qa`, `stg`, `prod`).
- Existing policy and metadata expectations are documented.
- Test scenarios are defined for both pass and block paths.

## Files Typically Changed

- `src/backend/services/guardrails_service.py`
- `src/backend/services/policy_service.py`
- `src/backend/domain/subagents.<target>.json`
- `tests/test_guardrails_service.py`
- `docs/governance/prompt-policy-controls.md`

## Workflow

### 1) Define guardrail contract

- Identify required evidence, disallowed outputs, and fail-closed conditions.
- Map conditions to deterministic checks and explicit block reasons.

### 2) Implement guardrail updates

- Add or adjust pre-response and post-response checks.
- Ensure block results include actionable and user-safe error messages.

### 3) Update subagent metadata usage

- Validate that route metadata supports required checks (for example `requires_evidence`).

### 4) Validate behavior locally

- Run pass and block test scenarios.
- Confirm stable behavior for streaming and non-streaming responses.

### 5) Deploy and verify

```bash
databricks bundle validate -t <target> --profile <profile>
make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>
```

## Validation Commands

```bash
uv run pytest -q tests/test_guardrails_service.py tests/test_policy_service.py tests/test_orchestrator_service.py
uv run runtime-preflight
```

## Rollback and Fallback

- Revert guardrail changes to last known good commit.
- Redeploy through standard path.
- If bundle deploy is blocked by registry outage, use runbook fallback deploy.

## Related Assets

- `examples/guardrail-scenarios.md`
- `examples/evidence-response-pattern.md`
- `checklists/pre-deploy.md`
- `checklists/post-deploy.md`
