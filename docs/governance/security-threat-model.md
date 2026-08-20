# Security and Threat Model

Define threat scenarios and required controls for this AI system.

## Purpose

Provide a practical security model for prompt injection resilience, auth safety, and data governance.

## Assets

- User identity context and forwarded tokens
- Governed data access routes
- Tool invocation pathways
- Lifecycle audit event streams

## Trust Boundaries

- UI to backend boundary
- Backend to external tool and model boundary
- App identity vs user identity boundary
- Message bus and audit persistence boundary

## Threat Scenarios

1. Prompt injection attempts to bypass route restrictions.
2. Unauthorized access through missing or forged OBO context.
3. Sensitive response leakage with low confidence.
4. Event tampering or missing audit coverage.

## Controls Implemented

- Deterministic request-time policy checks before tool execution.
- Hybrid auth with explicit OBO requirements.
- Response guardrails with block behavior on risky output.
- Structured lifecycle event publication across critical stages.
- Optional UC-governed event persistence.

## Required Operational Practices

- Never store raw tokens in logs.
- Validate environment-specific permissions for all Genie Agents.
- Enforce release-gate thresholds before deploy.
- Run incident review for guardrail or policy regression events.

## Future Hardening Candidates

- Automated secret scanning in CI
- Signed event pipeline for audit integrity
- Extended adversarial evaluation corpus

## Related Documents

- prompt-policy-controls.md
- data-contracts-lineage.md
- ../operations/operations-runbook.md
