# ADR 0007: Block Release When Evaluation KPIs Are Below Thresholds

## Status

Accepted

## Context

Pre-deployment evaluation existed but was not an enforced quality gate. This allowed potential regressions in tool-call accuracy, authorization correctness, safety, and groundedness to ship without detection.

## Decision

Make evaluation an enforced release gate via `enforce_release_gate()` in `operations/evaluate_agent.py`. Deployment is blocked when auth correctness, safety, or groundedness fall below configured thresholds. Tool-call accuracy remains monitored but non-blocking until the MLflow scorer can reliably assess nested tool spans.

### KPI thresholds

| KPI | Env Var | Default | Metric Candidates Searched |
|-----|---------|---------|---------------------------|
| Tool-call accuracy | `EVAL_MIN_TOOL_CALL_ACCURACY` | 0.80 | `toolcallcorrectness/mean`, `tool_call_correctness`, `tool_call_accuracy` (monitored, non-blocking) |
| Authorization correctness | `EVAL_MIN_AUTH_CORRECTNESS` | 0.90 | `authcorrectness/mean`, `auth_correctness`, `authorization_correctness`, `auth/mean` |
| Safety | `EVAL_MIN_SAFETY` | 0.95 | `safety/mean`, `safety` |
| Groundedness | `EVAL_MIN_GROUNDEDNESS` | 0.80 | `directgroundedness/mean`, `direct_groundedness`, `groundedness` |

### Controls

- `EVAL_REQUIRE_ALL_KPIS` (default `false`) — when true, missing KPI metrics also fail the gate.
- Multiple metric name candidates per KPI allow compatibility with different MLflow scorer output formats.
- Gate runs after `pytest` passes in CI and before `bundle deploy`.

### Scorers used

MLflow built-in: `Completeness`, `ConversationCompleteness`, `ConversationalSafety`, `KnowledgeRetention`, `UserFrustration`, `Fluency`, `RelevanceToQuery`, `Safety`, `ToolCallCorrectness`.

Custom: `auth_correctness_scorer` — validates that policy-denied tools are not invoked and OBO paths correctly block without token.

## Alternatives Considered

- Informational-only evaluation without deploy blocking.
- Manual reviewer sign-off in place of automated threshold checks.
- Gate only on one KPI (e.g., safety) instead of a balanced score set.
- Hard-coded thresholds instead of environment-configurable.

## Consequences

### Positive

- Converts evaluation from observability into enforceable release quality.
- Reduces production regressions in tool routing, safety, and authorization behavior.
- Makes deployment outcomes more consistent across environments.
- Custom auth scorer catches privilege escalation regressions that generic scorers miss.

### Trade-offs

- Requires periodic threshold tuning to avoid over-blocking during development.
- Can fail when expected metrics are absent if strict mode is enabled.
- Evaluation dataset must be maintained alongside implementation changes.

## Implementation Notes

- Gate logic and scorers: [src/operations/evaluate_agent.py](../../src/operations/evaluate_agent.py) (`enforce_release_gate`, `auth_correctness_scorer`)
- CI enforcement: [.github/workflows/databricks-cicd.yml](../../.github/workflows/databricks-cicd.yml) (runs `uv run assistant-evaluate` before deployment)
- Makefile target: `make evaluate` (invokes `uv run assistant-evaluate`)
- Operational guidance: [docs/operations/operations-runbook.md](../operations/operations-runbook.md)
