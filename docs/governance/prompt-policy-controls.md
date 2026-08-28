# Prompt and Policy Spec

Define prompt-layer behavior and deterministic policy-layer controls.

## Purpose

Separate model instruction strategy from hard policy enforcement and define safe change procedures.

## Prompt Layers

### Orchestrator Instructions

- Source: runtime instruction assembly in `src/aiserver/application/orchestration/agent.py`
- Responsibility: tool routing intent, unavailable tool behavior, citation expectation, composite/multi-tool comparison sequencing (call each relevant tool once, then compute the comparison itself), and per-source freshness-SLA disclosure when combining tools with different freshness SLAs

### Tool Function Prompts

- Source: function tool wrappers in `src/aiserver/application/orchestration/agent.py`
- Responsibility: model and endpoint invocation shape

### UI Behavior Hints

- Source: frontend message handling and content rendering modules
- Responsibility: user-facing framing and source hints

### Human-in-the-Loop Instructions

- Source: `store_intervention_agent` configuration in `src/aiserver/contracts/subagents.<target>.json`
- Responsibility: analyze revenue-versus-CDI risk, produce an evidence-backed manager packet, and stop at `pending` approval before any operational recommendation or dispatch.
- The prompt must not claim approval, dispatch an action, or treat a model-generated recommendation as authorization.

## Policy Layers

### Request-Time Policy

- Source: `src/aiserver/application/auth/policy.py`
- Checks:
  - auth mode and identity presence
  - persona allow-list
  - requested tool targeting
  - confidence threshold for sensitive data

### Response-Time Guardrails

- Source: `src/aiserver/application/guardrails/checks.py`
- Checks:
  - evidence requirement
  - unsafe output patterns
  - low-confidence sensitive output
- A subagent's `requires_evidence` flag must match its `system_prompt` citation mandate (see [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md)); a mismatch either silently skips enforcement or blocks output the prompt never asked for citations on.
- A subagent's `requires_human_approval` flag must match its prompt and runtime `approval_state` behavior. Approval records are submitted through `POST /approval-decisions` and are not dispatch commands.

## Decision Logging

All policy decisions must emit event metadata with:

- result (allow or deny)
- reason code
- subagent or tool name
- context attributes (persona, confidence, identity flag)

For approval-required workflows, include the request ID, agent name, store ID when available, approval status, and decision outcome in the audit trail. Do not persist credentials or raw tool payloads in approval records.

## Change Control

For any prompt or policy change:

1. Update this document and impacted ADR(s) if decision-level behavior changes.
2. Add or update tests.
3. Run evaluation and verify no KPI regression.
4. Record release note under runbook/change control process.

## Anti-Patterns

- Prompt-only access controls for regulated behavior.
- Silent fallback from OBO-required flow to app identity.
- Unversioned policy changes without evaluation evidence.

## Related Documents

- business-semantics-metadata.md
- prompt-engineering-guidelines.md
- ../architecture/runtime-technical-specs.md
- ../quality/evaluation-spec.md
- ../adrs/0005-governed-routing-policy-and-response-guardrails.md
