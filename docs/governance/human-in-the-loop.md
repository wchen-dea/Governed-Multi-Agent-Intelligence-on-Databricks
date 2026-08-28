# Human-in-the-Loop Approval

## Purpose

Define the implemented human-in-the-loop (HITL) workflow for business-impacting recommendations. HITL is a decision boundary: the agent may analyze governed data and prepare a recommendation packet, but it must not authorize or dispatch an operational action without an explicit manager decision.

## Current Use Case

The first implemented HITL use case is the store intervention workflow:

> Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.

The workflow is handled by `store_intervention_agent`, which is configured for the `manager` persona, app identity, confidential data, required evidence, and required human approval in `src/aiserver/contracts/subagents.<target>.json`.

`Store 123` is not a guaranteed real identifier. Use a store ID discovered from the connected sales and CDI sources, or ask the agent to identify all stores meeting the condition.

## Decision Boundary

The agent has permission to:

- Retrieve and compare store revenue and CDI/customer-experience signals.
- Identify material revenue-versus-experience risk.
- Compare the store with peer stores and a recent or rolling trend.
- Prepare a concise intervention packet with evidence and freshness information.
- Return a pending approval state.

The agent does not have permission to:

- Dispatch a field or store operation.
- Escalate a store or notify an operational team as an executed action.
- Claim that a recommendation was approved without a recorded decision.
- Continue from a pending packet to operational action based only on model output.

## Request Pattern

A discovery request should identify qualifying stores rather than assume a placeholder ID:

```text
Find stores with strong revenue but declining CDI scores. Compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.
```

A request for a known, verified store can use an explicit identifier:

```text
For store_id 4567, review revenue and CDI trends over the last 90 days. Prepare an evidence-backed customer-experience intervention packet and pause for manager approval before any operational dispatch.
```

The response must contain a citation marker or an explicit `Source:` line. The response guardrail blocks governed output that lacks evidence.

## Runtime States

The response envelope carries `approval_state` with these fields:

| Field | Meaning |
| --- | --- |
| `status` | `not_required`, `pending`, `approved`, `rejected`, `more_info_requested`, or `expired` |
| `required` | Whether a manager decision is required before action |
| `approver` | Required approver role, currently `manager` for store interventions |
| `decision` | Decision value when one has been recorded |
| `reason` | Human-readable explanation for the gate or decision |

A newly generated store intervention packet has `status=pending` and `required=true`. The runtime appends an approval notice to the response and does not authorize operational dispatch.

## Approval API

### Submit a decision

`POST /approval-decisions`

Example request:

```json
{
  "request_id": "req-123",
  "agent_name": "store_intervention_agent",
  "store_id": "4567",
  "approver": "sam.manager",
  "decision": "approved",
  "reason": "Revenue remains strong while CDI has declined for two consecutive periods.",
  "notes": "Begin the two-week customer-experience review after district confirmation."
}
```

Supported decision values:

- `approved`: the packet is approved for the separately controlled operational dispatch step.
- `rejected`: the recommendation is not approved and must not be dispatched.
- `more_info_requested`: the packet remains a review item until the requested evidence is supplied and a new decision is recorded.

`request_id` and `agent_name` are required. Invalid or missing values return HTTP `400`.

### Retrieve a decision

`GET /approval-decisions/{request_id}`

A found decision returns:

```json
{
  "status": "ok",
  "approval": {
    "request_id": "req-123",
    "agent_name": "store_intervention_agent",
    "store_id": "4567",
    "approver": "sam.manager",
    "decision": "approved",
    "reason": "Revenue remains strong while CDI has declined for two consecutive periods.",
    "notes": "Begin the two-week customer-experience review after district confirmation.",
    "status": "approved"
  }
}
```

A missing request returns HTTP `404`.

The approval endpoint uses the same Databricks Apps authentication boundary as the rest of the backend. The endpoint records the decision; operational dispatch must independently verify the persisted decision and its authorization before execution.

## Persistence

Approval records use the `ApprovalRepository` application port. The configured backend is selected through environment variables:

| Variable | Meaning | Default |
| --- | --- | --- |
| `APPROVAL_BACKEND` | `memory` for local development or `uc_table` for durable storage | `memory` |
| `APPROVAL_WAREHOUSE_ID` | SQL warehouse used by the UC repository | empty |
| `APPROVAL_CATALOG` | UC catalog for the approval table | empty |
| `APPROVAL_SCHEMA` | UC schema for the approval table | empty |
| `APPROVAL_TABLE` | Delta table name | `agent_approval_decisions` |
| `APPROVAL_FAIL_OPEN` | Whether a persistence failure may return the record without durable storage | `false` |

`APPROVAL_BACKEND=uc_table` creates the configured schema and Delta table if needed, then upserts decisions by `request_id`. The UC repository is fail-closed by default so a successful approval response is not returned when the durable write fails.

The in-memory repository is a development fallback only. It loses records when the process restarts and must not be used for production approval workflows.

## Governance Requirements

- Only a persona allowed to use the intervention agent may create the packet; the current registry allows `manager` only.
- `requires_human_approval=true` must remain aligned with the intervention agent prompt and response-envelope behavior.
- `requires_evidence=true` must remain aligned with the prompt's citation/source requirement.
- Approval records must include the request, agent, approver, decision, reason, and time of persistence in the durable table implementation.
- Approval and dispatch are separate responsibilities. Recording `approved` is not itself a dispatch command.
- Reject, more-information, persistence failure, and expired states must remain non-dispatchable.
- Lifecycle and guardrail events should remain enabled so the packet and decision can be correlated during audit and incident review.

## Testing and Verification

Focused tests cover:

- Pending approval state construction.
- Approval request serialization and API submission.
- Decision retrieval and record rehydration.
- UC table creation, keyed merge, and read behavior using a fake SQL client.
- Evidence guardrail behavior and source fallback for tool/function-call output events.

Run the focused suite:

```bash
uv run pytest -q tests/test_execution_contracts.py tests/test_api_handlers.py tests/test_guardrails_service.py tests/test_message_bus_backends.py
```

Before deployment:

```bash
databricks bundle validate -t TARGET --profile PROFILE
make redeploy TARGET=TARGET APP_NAME=APP_NAME PROFILE=PROFILE
```

After deployment, submit a test decision with a non-production request ID, retrieve it through `GET /approval-decisions/{request_id}`, and verify the corresponding row exists in the configured UC table.

## Related Documents

- [API contracts](../architecture/api-contracts.md)
- [Runtime technical specifications](../architecture/runtime-technical-specs.md)
- [Low-level design](../architecture/low-level-design.md)
- [Prompt and policy controls](prompt-policy-controls.md)
- [Operations runbook](../operations/operations-runbook.md)
- [Store intervention subagent configuration](../../src/aiserver/contracts/subagents.dev.json)
