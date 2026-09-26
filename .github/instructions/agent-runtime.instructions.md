---
description: "Agent orchestration, delegation, tool execution, and model-routing rules."
applyTo: "src/aiserver/application/orchestration/**,src/aiserver/application/delegation/**,src/aiserver/application/adapters/**,src/aiserver/contracts/**"
---

# Agent Runtime

- Keep deterministic route planning and authorization before model-driven tool selection.
- Add delegation targets only with allowed intents, an executor, correlation IDs, deterministic idempotency keys, and structured failure results.
- Represent tool outcomes with the existing typed execution contracts and closed status values.
- Do not let handlers call subagents directly; use the orchestrator/tool-construction path.
- Keep observability metadata out of model-visible prompts.
- For retries, timeouts, concurrency, or circuit breakers, centralize policy and add focused tests rather than adding local ad hoc behavior.