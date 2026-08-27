# ADR 0005: Enforce Governed Routing Policy and Response Guardrails

## Status

Accepted

## Context

The orchestrator routes across 5 subagents with different data classifications (`internal`, `confidential`), persona restrictions, and governance requirements. Without explicit policy and response controls, the system risks over-broad tool access, weak justification quality, and unsafe disclosure patterns.

## Decision

Introduce two deterministic enforcement layers:

### Request-time policy (before tool assembly)

Per-subagent evaluation using `filter_subagents_by_policy()`. Rules applied in order:

| Rule | Reason Code | Blocks When |
|------|-------------|------------|
| Explicit tool routing miss | `tool_not_requested` | Request names a specific tool that doesn't match this subagent |
| Persona required | `persona_required` | No persona set and subagent restricts by `allowed_personas` |
| Persona not allowed | `persona_not_allowed` | Active persona not in subagent's `allowed_personas` |
| OBO identity required | `obo_identity_required` | `auth_mode=obo` but no forwarded token present |
| Low confidence + sensitive | `low_confidence_sensitive` | `request_confidence < 0.75` for `confidential`/`restricted` data |

Denied subagents are excluded from tool assembly and reported as `unavailable_auth`.

### Response-time guardrails (before returning content)

Post-execution evaluation using `evaluate_response_guardrails()`:

| Check | Reason Code | Blocks When |
|-------|-------------|------------|
| Evidence required | `evidence_required` | `requires_evidence=true` subagent contributed but response lacks `[N]`, `Source:`, or `Citation:` |
| Unsafe output | `unsafe_output` | Response contains SSN, credit card, private key, API key, or password patterns |
| Low confidence sensitive | `low_confidence_sensitive` | Hedging language detected for confidential/restricted data context |

All allow/deny decisions are emitted as lifecycle events (`response.guardrail.passed`, `response.guardrail.blocked`).

### Current persona-agent matrix

| Persona | Accessible Agents |
|---------|-------------------|
| manager | all 5 agents |
| analyst | sales_insights_agent, product_index_assistant, lakebase_ods_agent |
| operator | flink_support_agent |
| engineer | flink_support_agent, lakebase_ods_agent |

## Alternatives Considered

- Prompt-only policy guidance without deterministic enforcement.
- Response filtering only, without pre-tool policy gates.
- Per-tool ad hoc checks embedded in each tool function.
- Single global persona check instead of per-subagent evaluation.

## Consequences

### Positive

- Enforces least-privilege routing before tool execution.
- Improves explainability of allow/deny outcomes via explicit reason codes.
- Reduces risk of sensitive low-confidence output.
- Persona restrictions are declarative in subagent config — no code changes needed to adjust access.

### Trade-offs

- Additional policy and guardrail logic to maintain and tune.
- Potentially more false positives if heuristics are too strict (especially `evidence_required`).
- Guardrail divergence between invoke (raises `UserError`) and stream (emits block delta).

## Implementation Notes

- Policy service: [src/aiserver/services/policy_service.py](../../src/aiserver/services/policy_service.py) (`PolicyContext`, `PolicyDecision`, `filter_subagents_by_policy`)
- Guardrails service: [src/aiserver/services/guardrails_service.py](../../src/aiserver/services/guardrails_service.py) (`GuardrailResult`, `evaluate_response_guardrails`)
- Runtime integration: [src/aiserver/services/runtime_auth_service.py](../../src/aiserver/services/runtime_auth_service.py) (`build_runtime_auth_context`)
- Handler enforcement: [src/aiserver/api/handlers.py](../../src/aiserver/api/handlers.py) (`_finalize_invoke_stage`, `_finalize_stream_stage`)
- Persona config: `allowed_personas` field in [src/aiserver/domain/subagents.dev.json](../../src/aiserver/domain/subagents.dev.json)
- Tests: [tests/test_policy_service.py](../../tests/test_policy_service.py), [tests/test_guardrails_service.py](../../tests/test_guardrails_service.py)
