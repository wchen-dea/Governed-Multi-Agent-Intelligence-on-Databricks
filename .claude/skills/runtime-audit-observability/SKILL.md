---
name: runtime-audit-observability
description: "Implement or update runtime lifecycle auditing and observability behavior for message bus backends, UC audit persistence, and deployment telemetry validation. Use when: changing event schemas, backend selection, async publish behavior, or observability checks."
---

# Runtime Audit Observability

Use this skill to update lifecycle audit emission and operational observability behavior.

## Scope

This skill covers:

- Message bus backend behavior (`structured_logging`, `noop`, `kafka`, `rabbitmq`, `uc_table`).
- Unity Catalog audit table integration and event persistence.
- Async publish behavior and observability checks.

This skill does not cover:

- Business routing rules (use runtime-routing).
- Guardrail policy logic (use runtime-guardrails).

## Preconditions

- Target selected and profile available.
- Audit warehouse/catalog/schema/table values are known for target.
- Monitoring/verification expectations are defined.

## Files Typically Changed

- `src/aiserver/infrastructure/messaging/bus.py`
- `src/aiserver/config/settings.py`
- `targets/<env>.yml`
- `resources/multiagent_app.yml`
- `tests/test_message_bus_backends.py`
- `tests/test_message_bus_integration.py`

## Workflow

### 1) Define observability contract

- Confirm required lifecycle and policy events.
- Define required fields and persistence behavior per backend.

### 2) Implement backend or schema updates

- Adjust message bus behavior and backend initialization.
- Preserve fail-open or fail-closed behavior explicitly.

### 3) Configure target settings

- Set target message bus backend and UC audit parameters.
- Ensure placeholders are removed before promotion.

### 4) Validate locally

- Validate backend initialization and publish paths.
- Validate async queue behavior where enabled.

### 5) Deploy and verify

```bash
databricks bundle validate -t <target> --profile <profile>
make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>
```

## Validation Commands

```bash
uv run pytest -q tests/test_message_bus_backends.py tests/test_message_bus_integration.py tests/test_api_handlers.py
uv run runtime-preflight
```

## Rollback and Fallback

- Revert backend/schema changes to known good state.
- Redeploy and verify event emission resumes.

## Related Assets

- `examples/message-bus-backend-matrix.md`
- `examples/uc-audit-config.md`
- `checklists/pre-deploy.md`
- `checklists/post-deploy.md`
