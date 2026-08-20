# API Contract Spec

Define external and internal request/response expectations for runtime handlers.

## Purpose

Document the stable contract for invoke and stream usage and expected error semantics.

## Endpoints

- `POST /invocations`
- Stream handler through MLflow agent server stream route
- `GET /health`

## Invoke Request Contract

Required fields:

- `input`: list of role/content messages

Optional fields:

- `custom_inputs`: persona, tool targeting, confidence, session metadata
- context conversation identifiers

Optional headers:

- `x-forwarded-access-token` for OBO tool execution
- `Authorization: Bearer <token>` for direct non-interactive Databricks Apps invocation tests

## Invoke Response Contract

- On success: response output item list
- On block/failure: typed error response with user-safe detail

## Stream Contract

- Stream events are normalized for stable output item identifiers
- Tool output items are converted into response output item events

## Error Semantics

- Authorization or policy failures produce explicit user-facing errors
- MCP/tool backend failures can be reported as unavailable tool behavior
- Guardrail blocks return explicit block reason(s)

## Compatibility Rules

- Backward compatibility is expected for core input/output structure
- Breaking contract changes require ADR + release note

## Related Documents

- runtime-technical-specs.md
- ../governance/prompt-policy-controls.md
- ../operations/operations-runbook.md
