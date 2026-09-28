---
name: quality-evaluation
description: "Evaluate agent behavior and produce release-gate evidence. Use when: changing prompts, models, tools, routing, guardrails, authorization, or response behavior before promotion."
---

# Quality Evaluation

Use this skill after behavior changes and before promotion. Follow the repository's evaluation specification and preserve evidence rather than weakening thresholds.

## Workflow

1. Identify the changed behavior and affected subagents, tools, policies, prompts, or models.
2. Read the applicable evaluation specification, contracts, scoped instructions, and nearby tests.
3. Run focused deterministic tests for routing, authorization, contracts, guardrails, delegation, and stream/invoke parity.
4. Run the applicable model-dependent evaluation for groundedness, safety, relevance, tool-call correctness, latency, and cost.
5. Preserve MLflow run IDs, trace evidence, failed-case classifications, and unavailable dependency information.
6. Compare results with the release-gate thresholds. Do not lower thresholds to hide regressions.
7. Report the changed behavior, commands, metrics, pass/fail status, limitations, and promotion recommendation.

## Required checks

- Authorization and safety remain blocking checks.
- Groundedness and evidence/citation behavior are tested when applicable.
- Tool selection includes both required and unnecessary-tool cases.
- Evaluation data matches registered subagents, personas, and expected tool calls.
- Tests use no live credentials or production data.
- A failed model evaluation is classified with its trace or run ID.

## Outputs

- Focused test results.
- Evaluation metrics and MLflow evidence when available.
- Release-gate status: `pass`, `fail`, or `blocked`.
- Unresolved risks and external validation limitations.