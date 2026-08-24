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

- The MLflow stream handler normalizes stable item identifiers, buffers execution events, then finalizes source metadata and guardrails before user-visible output.
- Tool output items are retained as metadata events; they are not visible assistant content.
- The React client renders only `response.output_text.delta` as answer text and uses other events for governance hints.

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

## Delegation Status Contract

- `GET /delegations/{task_id}` returns a user-safe task lifecycle view for accepted agent handoffs.
- The response includes task ID, correlation ID, source/target agents, intent, state, retry count, and terminal failure code when available.
- The endpoint never returns the delegated SQL, task payload, credentials, or tool output.
- The React proxy exposes the same path to browser clients.
- A missing task returns HTTP `404`. Access requires the same Databricks Apps authentication boundary as other backend routes.

## Error Semantics

- Authorization or policy failures produce explicit user-facing errors
- MCP/tool backend failures can be reported as unavailable tool behavior
- Guardrail blocks return explicit block reason(s)

## Compatibility Rules

- Backward compatibility is expected for core input/output structure
- Breaking contract changes require ADR + release note

## Related Documents

- [Runtime technical specifications](runtime-technical-specs.md)
- [Prompt and policy controls](../governance/prompt-policy-controls.md)
- [Operations runbook](../operations/operations-runbook.md)
