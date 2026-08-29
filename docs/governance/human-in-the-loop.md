# Human-in-the-Loop Approval

## Purpose

Define the implemented human-in-the-loop (HITL) workflow for business-impacting recommendations. HITL is a decision boundary: the agent may analyze governed data and prepare a recommendation packet, but it must not authorize or dispatch an operational action without an explicit manager decision.

## Current Use Case

The first implemented HITL use case is the active `store-intervention-agent` workflow:

> Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.

The workflow is handled by `store-intervention-agent`, which is configured for the `manager` persona, app identity, confidential data, required evidence, and required human approval in `src/aiserver/contracts/subagents.<target>.json`.

`Store 123` is not a guaranteed real identifier. Use a store ID discovered from the connected sales and CDI sources, or ask the agent to identify all stores meeting the condition.

## Create `store-intervention-agent`

`store-intervention-agent` is a Databricks App specialist. Its source is maintained locally in `src/hitl-agent/` and is declared in the bundle as `resources.apps.hitl-app-agent` in `resources/hitl_app.yml`. Create or bind it once per environment, then keep its App name aligned with `hitl_app_name` and the orchestrator subagent endpoint.

### 1. Define the specialist contract

The specialist App must expose a Responses API-compatible endpoint that accepts a user question and returns `output_text`. Its implementation must:

- Query or orchestrate the approved sales and CDI data sources.
- Find stores with strong revenue and declining CDI when the request is a discovery query.
- Compare each candidate with an explicitly defined peer set and recent or rolling trend.
- Return an evidence-backed packet with metric definitions, time windows, freshness, source identifiers, risk, proposed options, and success measures.
- Include a citation marker or an explicit `Source:` line in every governed response.
- Treat intervention and dispatch language as proposals only.
- Stop at a pending manager review state and never perform operational dispatch.

Minimum response content for each candidate store:

| Section | Required content |
| --- | --- |
| Store identity | Verified store ID and any non-sensitive display label |
| Revenue signal | Metric, period, value, peer position, and trend |
| CDI signal | CDI dimension, period, value, peer position, and trend |
| Materiality | Why the revenue-versus-CDI pattern merits review |
| Evidence | Citation or `Source:` line with freshness |
| Proposal | Non-executing intervention options, scope, risk, and success measure |
| Approval state | Pending manager review; no dispatch performed |

The App must not accept an `approved` value from model text as authorization. Authorization is established only by the orchestrator's approval API and the persisted approval record.

### 2. Create and deploy the App

Use the organization-approved Databricks Apps creation path. In dev the App is named `hitl-app-agent`; other targets should set `hitl_app_name` in `targets/<target>.yml`. The source must include the specialist's Responses API server and its dependency/configuration files.

If the App already exists, bind it to the DAB resource key before deploying:

```bash
databricks bundle deployment bind hitl-app-agent hitl-app-agent \
  --target dev \
  --profile PROFILE \
  --auto-approve
```

Deploy it with the rest of the bundle:

```bash
databricks bundle deploy -t dev --profile PROFILE
```

For manual source-only refreshes, deploy it with the repository helper:

```bash
make update-hitl APP_NAME=hitl-app-agent PROFILE=PROFILE
```

The helper imports `src/hitl-agent`, creates the App only when it does not already exist, and otherwise performs an update-only `databricks apps deploy` against the existing App. On update, it verifies the App service principal client ID did not change.

Confirm the deployment and capture the App service principal:

```bash
databricks apps get hitl-app-agent --profile PROFILE --output json
APP_SP=$(databricks apps get hitl-app-agent --profile PROFILE --output json \
  | jq -r '.service_principal_name // .service_principal_client_id')
```

The App must be `RUNNING` with an active successful deployment before it is registered in the orchestrator subagent configuration. The current dev App is `hitl-app-agent`.

### Grant specialist data privileges

The current specialist implementation uses Databricks SQL Statement Execution against the gold and platinum tables configured in `src/hitl-agent/app.yaml`. Grant its App service principal only the warehouse and UC privileges required for those queries:

```bash
make grant-hitl-privileges APP_NAME=hitl-app-agent PROFILE=PROFILE
```

The helper resolves the specialist service principal and grants:

- `CAN_USE` on the configured SQL warehouse
- `USE_CATALOG` and `USE_SCHEMA` for the configured environment's platinum and gold source schemas, such as `dt_${TARGET}_platinum.enterprise` and `dt_${TARGET}_gold.dwh`
- `SELECT` on the platinum revenue table and gold CDI, peer-set, and store-dimension tables

Review the generated grants first with:

```bash
DRY_RUN=true make grant-hitl-privileges APP_NAME=hitl-app-agent PROFILE=PROFILE
```

Override the current dev data sources when promoting to another environment:

```bash
HITL_WAREHOUSE_ID=<warehouse-id> \
HITL_REVENUE_TABLE=<catalog>.<schema>.<table> \
HITL_CDI_TABLE=<catalog>.<schema>.<table> \
HITL_PEER_SET_TABLE=<catalog>.<schema>.<table> \
HITL_STORE_DIMENSION_TABLE=<catalog>.<schema>.<table> \
make grant-hitl-privileges APP_NAME=hitl-app-agent PROFILE=PROFILE
```

If explicit `HITL_*_TABLE` values are omitted, the helper derives conventional defaults from `TARGET` or `HITL_ENV`, for example `TARGET=qa` maps to `dt_qa_platinum.enterprise.store_sales_performance` and `dt_qa_gold.dwh.*`.

The script does not grant `MODIFY`, `CREATE TABLE`, broad schema access, or operational dispatch permissions.

### Post-approval follow-up task

When a manager submits an approval decision through `POST /approval-decisions`, the runtime persists the decision first. If and only if `decision=approved`, the approval API then creates an idempotent, durable delegation task with:

- Source agent: `approval-api`
- Target agent: `store-intervention-agent`
- Intent: `store_intervention_planning`
- Payload flags: `planning_only=true`, `dispatch_authorized=false`

The approval response includes the created delegation task summary so the UI can display the follow-up task id. `rejected` and `more_info_requested` decisions do not create delegation tasks. The follow-up task is a planning record only; it is not an operational dispatch authorization.

Operators can disable or retarget this behavior with `APPROVAL_DELEGATION_ENABLED`, `APPROVAL_DELEGATION_SOURCE_AGENT`, `APPROVAL_DELEGATION_TARGET_AGENT`, and `APPROVAL_DELEGATION_INTENT`. The target subagent must explicitly accept the source and intent in `src/aiserver/contracts/subagents.<target>.json` or the API rejects the follow-up task before submitting it.

For subsequent source updates, use the repository helper from the project root:

```bash
make update-hitl APP_NAME=hitl-app-agent PROFILE=PROFILE
```

The helper imports `src/hitl-agent` into the current user's workspace path, creates or updates the App from that workspace source, and prints the resulting deployment status. Override the defaults when needed:

```bash
HITL_SOURCE_DIR=/path/to/source \
HITL_WORKSPACE_PATH=/Workspace/Users/owner/hitl-app-agent \
make update-hitl APP_NAME=hitl-app-agent PROFILE=PROFILE
```

The script requires `app.py`, `app.yaml`, and `requirements.txt` in the source directory. It creates the App only when missing, updates existing Apps in place, verifies the service principal is preserved on update, and does not change the orchestrator registry.

### 3. Grant the orchestrator access

Grant the orchestrator App service principal permission to use the specialist App. Capture the orchestrator service principal from the target app:

```bash
ORCH_SP=$(databricks apps get multiagent-app-dev --profile PROFILE --output json \
  | jq -r '.service_principal_name // .service_principal_client_id')
```

Use the Databricks Apps permission command supported by the installed CLI version:

```bash
databricks apps update-permissions hitl-app-agent \
  --profile PROFILE \
  --service-principal "$ORCH_SP" \
  --permission-level CAN_USE
```

Also grant the specialist App's service principal least-privilege access to the approved sales/CDI Genie spaces, SQL warehouse, Unity Catalog schemas, or other data resources it actually calls. Do not grant broad workspace or catalog permissions as a substitute for the exact data dependencies.

### 4. Register the App in this repository

For each target, update `src/aiserver/contracts/subagents.<target>.json` with:

```json
{
  "name": "store-intervention-agent",
  "type": "app",
  "auth_mode": "app",
  "allowed_personas": ["manager"],
  "requires_evidence": true,
  "requires_human_approval": true,
  "endpoint": "hitl-app-agent"
}
```

Keep the existing `owner`, `data_classification`, `freshness_sla`, `system_prompt`, and `description` fields aligned across dev, QA, staging, and production. The endpoint value is the App name, not the App URL.

If the target uses a different App name, change only that target's `endpoint` and document the mapping. Do not point the route at an unrelated App or an MCP hello-world sample.

### 5. Validate the registration

Run the typed registry and bundle checks:

```bash
uv run pytest -q tests/test_subagent_config.py tests/test_api_handlers.py
databricks bundle validate -t TARGET --profile PROFILE
make redeploy TARGET=TARGET APP_NAME=APP_NAME PROFILE=PROFILE
```

Then verify the route with the manager persona:

```bash
make query-dev \
  TARGET=dev \
  APP_NAME=multiagent-app-dev \
  PROFILE=PROFILE \
  QUERY_PERSONA=manager \
  QUERY='Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.'
```

A successful verification must show qualifying stores or a clear no-match result, evidence/source metadata, `approval_state.status=pending`, and no operational dispatch. If the result says `App with name hitl-app-agent does not exist`, the App creation, naming, deployment, or permission step is incomplete.

### 6. Promote by environment

Repeat the App binding/creation and least-privilege grants for QA, staging, and production, or use the organization-approved promotion mechanism if the App supports environment isolation. Replace target placeholders before promotion and keep each App's data resources in the same environment boundary as the orchestrator.

The bundle declares the specialist App as `resources.apps.hitl-app-agent`; `make update-hitl` remains the source-only helper for targeted HITL updates outside a full bundle deployment.

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
  "agent_name": "store-intervention-agent",
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
    "agent_name": "store-intervention-agent",
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
| `APPROVAL_DELEGATION_ENABLED` | Whether approved decisions create a durable planning task | `true` |
| `APPROVAL_DELEGATION_SOURCE_AGENT` | Source agent recorded on approved follow-up tasks | `approval-api` |
| `APPROVAL_DELEGATION_TARGET_AGENT` | Target agent for approved follow-up tasks | `store-intervention-agent` |
| `APPROVAL_DELEGATION_INTENT` | Intent recorded on approved follow-up tasks | `store_intervention_planning` |
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
