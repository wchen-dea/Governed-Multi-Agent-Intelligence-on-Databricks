---
description: "Security, authorization, prompt policy, guardrail, and human-approval requirements."
applyTo: "src/aiserver/application/auth/**,src/aiserver/application/guardrails/**,docs/governance/**,src/aiserver/contracts/subagents*.json"
---

# Governance and Security

- Enforce identity, persona, tool authorization, and sensitive-data confidence checks before execution.
- Treat prompts as advisory; deterministic policy and guardrails are authoritative.
- Preserve evidence requirements, source attribution, PII/safety checks, and structured allow/deny reason codes.
- Human approval is not authorization to dispatch. Preserve pending state, approval IDs, audit records, and post-decision checks.
- Do not log or persist credentials, forwarded tokens, raw sensitive tool payloads, or unnecessary personal data.
- Prompt or policy changes require tests, evaluation evidence, and documentation updates when decision behavior changes.