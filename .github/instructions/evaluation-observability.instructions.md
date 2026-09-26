---
description: "Evaluation, MLflow tracing, lifecycle audit, quality gates, cost, and drift guidance."
applyTo: "src/evaluation/**,src/operations/evaluate_agent.py,docs/quality/**,docs/operations/**"
---

# Evaluation and Observability

- Preserve MLflow traces, lifecycle audit events, routing metadata, tool outcomes, and redaction behavior.
- Evaluate authorization, safety, groundedness, tool use, relevance, latency, and cost—not only response fluency.
- Do not lower a release threshold to hide a regression. Classify failed traces and preserve the run ID.
- Changes to routing, prompts, tools, models, or guardrails require focused regression tests and the applicable evaluation command.
- Clearly distinguish implemented monitoring from target-state recommendations.