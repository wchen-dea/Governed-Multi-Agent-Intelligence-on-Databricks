# API Contract Spec

Define external and internal request/response expectations for runtime handlers.

## Purpose

Document the stable contract for invoke and stream usage and expected error semantics.

## Endpoints

- `POST /invocations`
- Stream handler through MLflow agent server stream route
- `GET /health`
- `POST /approval-decisions`
- `GET /approval-decisions/{request_id}`

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
- OpenAI-compatible agent execution metadata is carried through lifecycle events and stream governance events without changing the public assistant text contract.

## Stream Contract

- The MLflow stream handler emits non-content `response.progress` events for accepted, prepared, executing, and finalizing stages so long-running governed workflows keep the response body active.
- The handler normalizes stable item identifiers, buffers execution events, then finalizes source metadata and guardrails before user-visible answer output.
- Tool output items are retained as metadata events; they are not visible assistant content.
- The React client renders only `response.output_text.delta` as answer text and ignores progress events; progress never bypasses final-answer guardrails.
- `STREAM_EXECUTION_TIMEOUT_SECONDS` bounds the total backend stream lifecycle. On expiry, the handler emits a user-safe timeout response and records `request.stream.failed` with reason `stream_execution_timeout` before the frontend request timeout is reached.

## Governance Metadata Contract

The internal response envelope contains:

| Field | Meaning |
| --- | --- |
| `status` | `succeeded`, `failed`, `blocked`, or `truncated` |
| `answer_chars` | Character count evaluated by the response policy |
| `truncated` | Whether the configured response budget was exceeded |
| `route_plan` | Candidate tools, route reason, confidence, and evidence requirement |
| `tool_results` | Normalized tool execution outcomes |
| `openai_run` | Run id, Responses API marker, selected model, task type, route candidates, selected tools, unavailable tools, and AI Gateway routing flag |
| `guardrail_reasons` | Stable input or output policy reason codes |
| `source_metadata` | Source or freshness metadata used for governed answers |
| `approval_state` | Human-review requirement, approver role, decision status, and reason |

The public Responses API output structure remains backward-compatible; governance metadata is carried through lifecycle events and stream metadata.

## Human Approval Decision Contract

Store-intervention responses can require manager review before an operational recommendation is dispatched. The runtime returns an `approval_state` with `status=pending` and `required=true` when a participating subagent has `requires_human_approval=true`.

### Submit approval decision

`POST /approval-decisions`

Request body fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `request_id` | yes | Identifier correlating the decision to the pending review packet |
| `agent_name` | yes | Subagent that created the packet, such as `store-intervention-agent` |
| `store_id` | no | Verified store identifier under review |
| `approver` | no | Manager identity or approver principal |
| `decision` | yes | `approved`, `rejected`, or `more_info_requested` |
| `reason` | no | Rationale for the decision |
| `notes` | no | Additional review or dispatch constraints |

Example:

```json
{
	"request_id": "req-123",
	"agent_name": "store-intervention-agent",
	"store_id": "4567",
	"approver": "sam.manager",
	"decision": "approved",
	"reason": "Revenue remains strong while CDI has declined for two consecutive periods.",
	"notes": "Confirm district ownership before beginning the review."
}
```

The request is validated by the strict `ApprovalDecisionInput` Pydantic model before any persistence or delegation side effect. Missing or blank required fields, unsupported decisions, invalid field types, and unknown fields return FastAPI HTTP `422` validation errors. The decision is persisted through the configured approval repository before a successful response is returned.

### Retrieve approval decision

`GET /approval-decisions/{request_id}` returns the persisted approval record or HTTP `404` when no record exists. Approval records are payload-redacted and must not contain credentials, raw SQL, or unapproved tool output.

Recording `approved` is not an operational dispatch command. A dispatch integration must independently verify the stored approval, approver authorization, matching request and agent, and non-expired status.

## Delegation Status Contract

- `GET /delegations/{task_id}` returns a user-safe task lifecycle view for accepted agent handoffs.
- The response includes task ID, correlation ID, source/target agents, intent, state, retry count, and terminal failure code when available.
- The endpoint never returns the delegated SQL, task payload, credentials, or tool output.
- A missing task returns HTTP `404`. Access requires the same Databricks Apps authentication boundary as other backend routes.

## Error Semantics

- Authorization or policy failures produce explicit user-facing errors
- MCP/tool backend failures can be reported as unavailable tool behavior
- Guardrail blocks return explicit block reason(s)
- Approval-required recommendations return a pending state and remain non-dispatchable until an explicit manager decision is recorded.

## Compatibility Rules

- Backward compatibility is expected for core input/output structure
- Breaking contract changes require ADR + release note

## Related Documents

- [Runtime technical specifications](runtime-technical-specs.md)
- [Prompt and policy controls](../governance/prompt-policy-controls.md)
- [Operations runbook](../operations/operations-runbook.md)
