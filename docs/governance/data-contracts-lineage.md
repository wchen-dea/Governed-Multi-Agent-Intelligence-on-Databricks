# Data Contract and Lineage Spec

Define data contracts, sensitivity boundaries, and lineage expectations for routed answers.

## Purpose

Ensure governed data usage is predictable, auditable, and safe across tool and model flows.

## Data Contract Layers

### Request Contract

- Input role/content items
- Optional context identifiers
- Optional custom inputs for persona, tool targeting, and confidence
- Optional forwarded token header for OBO routes

### Routing Contract

- Subagent metadata controls route eligibility
- Auth mode and policy checks determine allow/deny decisions
- Unavailable routes must produce explicit user-visible behavior

### Response Contract

- Response text and stream events are normalized
- Guardrails may block response before final return
- Governed responses may require citation or source evidence

## Sensitivity Model

Supported levels:

- public
- internal
- confidential
- restricted

Sensitivity level influences:

- policy checks
- confidence gating
- evidence expectations

## Lineage Requirements

Each governed request should be traceable through:

- request lifecycle event
- policy decision event(s)
- tool call event(s)
- guardrail decision event
- final response outcome
- approval decision when the response requires human review

## Storage and Audit

Lifecycle events can persist to UC-governed Delta tables via `uc_table` message bus backend.

Required identifiers:

- event_id
- event_type
- event_ts
- event_payload

Approval records are a separate durable contract from lifecycle events. They are keyed by `request_id` and contain `agent_name`, optional `store_id`, `approver`, `decision`, `reason`, `notes`, and `status`. Approval records must not contain credentials, raw SQL, or unreviewed tool payloads. An `approved` record authorizes only the reviewed decision boundary; it is not itself a dispatch command.

## Operational Rules

- Avoid introducing undocumented custom input fields.
- Keep subagent metadata and data-classification values valid and versioned.
- Validate policy and guardrail behavior in tests and evaluation before release.

## Related Documents

- business-semantics-metadata.md
- ../architecture/runtime-technical-specs.md
- ../architecture/tool-and-model-registry.md
- ../operations/operations-runbook.md
