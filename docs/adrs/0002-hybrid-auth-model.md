# ADR 0002: Use Hybrid App Plus OBO Authorization Model

## Status

Accepted

## Context

The orchestrator routes requests to tools with different access requirements. Some tools (Genie spaces, AI Search indexes, Lakebase) run with the app's service principal identity. Others may need to operate with the end-user's identity for governed data access and per-user audit trails.

## Decision

Adopt per-subagent auth mode selection via `auth_mode` field in subagent config:

- `app` — execute with the Databricks App service principal (WorkspaceClient from app environment).
- `obo` — execute with the user's forwarded token (user WorkspaceClient from `x-forwarded-access-token` header).

Identity resolution happens per-request in `build_request_identity_context()`:

1. App identity is always available (from the app's service principal).
2. User identity is available only when the request carries `x-forwarded-access-token`.
3. Policy service blocks `obo`-mode subagents when no user token is present (reason code: `obo_identity_required`).

Current state: all 5 configured subagents use `auth_mode=app`. OBO paths are wired and tested but not yet active in production subagent configs.

## Alternatives Considered

- App-only auth for all tools — rejected because it prevents user-scoped governance when needed.
- OBO-only auth for all tools — rejected because operational friction (token forwarding) and availability concerns for app-managed tools.
- Per-request global auth selection instead of per-subagent — rejected because tools have different trust requirements.

## Consequences

### Positive

- Supports least-privilege access per tool at the subagent config level.
- Enables user-scoped governance and auditability when activated.
- Blocks missing-token OBO paths with clear reason codes before tool execution.
- Auth mode is declarative per subagent — no code changes needed to switch a tool from app to OBO.

### Trade-offs

- Runtime auth branching and additional error paths.
- UX guidance required for users to understand token forwarding via `/token` command.
- OBO clients add per-request WorkspaceClient construction overhead.

## Implementation Notes

- Identity resolution: [src/aiserver/shared/runtime_utils.py](../../src/aiserver/shared/runtime_utils.py) (`RequestIdentityContext`, `build_request_identity_context`)
- Auth context assembly: [src/aiserver/services/runtime_auth_service.py](../../src/aiserver/services/runtime_auth_service.py) (`build_runtime_auth_context`)
- Policy enforcement: [src/aiserver/services/policy_service.py](../../src/aiserver/services/policy_service.py) (`obo_identity_required` reason code)
- Token forwarding UX: React UI `/token <databricks_access_token>` command sets `x-forwarded-access-token` header
- Auth mode config: `auth_mode` field in [src/aiserver/domain/subagents.dev.json](../../src/aiserver/domain/subagents.dev.json)
