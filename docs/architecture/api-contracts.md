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
- Lifecycle success events include a typed response envelope with status, answer length, truncation state, guardrail reasons, and source metadata.

## Stream Contract

- Stream events are normalized for stable output item identifiers
- Tool output items are converted into response output item events
- The React client receives text deltas incrementally and may receive governance metadata in `response_envelope` or `governance` events.

## Governance Metadata Contract

The internal response envelope contains:

| Field | Meaning |
| --- | --- |
| `status` | `succeeded`, `failed`, `blocked`, or `truncated` |
| `answer_chars` | Character count evaluated by the response policy |
| `truncated` | Whether the configured response budget was exceeded |
| `route_plan` | Candidate tools, route reason, confidence, and evidence requirement |
| `tool_results` | Normalized tool execution outcomes |
| `guardrail_reasons` | Stable input or output policy reason codes |
| `source_metadata` | Source or freshness metadata used for governed answers |

The public Responses API output structure remains backward-compatible; governance metadata is carried through lifecycle events and stream metadata.

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
