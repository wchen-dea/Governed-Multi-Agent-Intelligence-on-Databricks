# AI Agent Monitoring: Observability, Evaluation, Safety, Drift, and Cost

Consolidated view of how this project monitors the running agent system across five dimensions: observability, evaluation/quality, safety/guardrails, drift/anomaly detection, and token cost/performance. Each dimension already has its own authoritative document; this page maps what's implemented, where, and — honestly — what is not yet implemented, so monitoring gaps aren't discovered only during an incident.

## 1. Observability (Implemented)

- **Runtime tracing:** every request produces a full MLflow trace (`mlflow.openai.autolog()` in [handlers.py](../../src/aiserver/api/handlers.py)) capturing the span tree (handler → orchestrator → tool calls), per-span latency, token counts, and request/response payloads. Full detail: [mlflow-guide.md](mlflow-guide.md) section 1.
- **Lifecycle audit events:** routing, policy, and guardrail decisions are published as structured events through the injected `MessageBus` (structured logging, Kafka, RabbitMQ, or Unity Catalog table backend) — see [../adrs/0004-lifecycle-message-bus.md](../adrs/0004-lifecycle-message-bus.md) and [../adrs/0006-unity-catalog-audit-table-for-lifecycle-events.md](../adrs/0006-unity-catalog-audit-table-for-lifecycle-events.md).
- **Trace metadata for routing decisions:** `mlflow.update_current_trace(metadata=...)` in `orchestrator_service.py` attaches routing/subagent/auth-mode metadata directly to the trace (see [agent-harness-engineering-guidelines.md](../governance/agent-harness-engineering-guidelines.md) Rule 8) — kept separate from model-visible prompt content.
- **Monitoring signals defined:** request success/failure rate, tool invocation count and failure ratio, guardrail block ratio, stream/invoke latency p50/p95, MCP connect/probe timeouts, async message-bus queue pressure — see [cost-performance-budget.md](cost-performance-budget.md) "Monitoring Signals".

**Gap:** signals are *defined* but there is no standing dashboard/alerting layer wired to them yet — today's routine is manual: open the MLflow Experiments UI and inspect traces. See [Possible Improvements](#possible-improvements-to-level-up).

## 2. Evaluation and Quality (Implemented, Partially Blocking)

- **Scoring pipeline:** `mlflow.genai.evaluate()` with a `ConversationSimulator` (LLM-as-judge) runs 9 built-in scorers (`ToolCallCorrectness`, `Safety`, `ConversationalSafety`, `RelevanceToQuery`, `Completeness`, `ConversationCompleteness`, `Fluency`, `KnowledgeRetention`, `UserFrustration`) plus 2 custom scorers (`AuthCorrectness`, `DirectGroundedness`). Full detail: [evaluation-spec.md](../quality/evaluation-spec.md).
- **Release gate:** `enforce_release_gate()` in `src/aiserver/evaluate_agent.py` blocks promotion when `auth_correctness` (≥0.90), `safety` (≥0.95), or `groundedness` (≥0.80) fall below threshold.
- **Known limitation (documented, not hidden):** `tool_call_accuracy` is currently non-blocking due to a documented MLflow/`openai-agents` trace-selection scoring gap — see the "Known Issue" section in [evaluation-spec.md](../quality/evaluation-spec.md). This is a real, active quality gap, not a monitoring omission — it is tracked and reported, just not gate-blocking yet.
- **Triage tooling:** `uv run assistant-triage-evaluation` classifies failing tool-call assessments from a run's traces into documented triage categories.

## 3. Safety and Guardrails (Implemented)

- **Request-time policy** (`policy_service.py`): auth mode/identity checks, persona allow-list, requested-tool targeting, confidence threshold for sensitive data.
- **Response-time guardrails** (`guardrails_service.py`): evidence requirement (citation enforcement when `requires_evidence: true`), unsafe-output pattern matching, low-confidence sensitive-output blocking. See [prompt-policy-controls.md](../governance/prompt-policy-controls.md).
- **Decision logging:** every policy/guardrail decision emits event metadata (result, reason code, subagent/tool name, context attributes) to the lifecycle audit trail.

## 4. Drift and Anomaly Detection (Not Implemented — Target-State Only)

This is the one dimension with a real gap between aspiration and implementation, and it should be stated plainly rather than implied as "handled":

- The enterprise reference material ([01-foundation-governance.md](../reference/01-foundation-governance.md) — Model Owner role; [03-security-risk-controls.md](../reference/03-security-risk-controls.md) — "Model, Retrieval, and Data Drift" risk row) describes drift monitoring, retrieval-quality degradation tracking, and cost-anomaly alerting as *required* enterprise controls.
- **None of this is implemented in `src/` today.** There is no automated drift dashboard, no scheduled embedding/index staleness check beyond the documented `freshness_sla` metadata field, and no anomaly-detection job over token volume, latency, or business KPI movement.
- The closest existing practice is **periodic manual post-release evaluation runs** (re-running `evaluate_agent.py` against the same KPI thresholds after a release) — this catches gross regressions but is not continuous drift monitoring and does not detect gradual degradation between releases.
- **Do not describe this project as having drift/anomaly monitoring** in a security review, business case, or CoE case charter (see [08-ai-coe-business-requirements-and-case-design-rules.md](../reference/08-ai-coe-business-requirements-and-case-design-rules.md)) without flagging this gap explicitly.

## 5. Token Cost and Performance (Implemented, Manual)

- **Cost drivers, budget controls, and tuning levers** are documented in [cost-performance-budget.md](cost-performance-budget.md): LLM token usage, external endpoint invocations, message bus transport cost, evaluation simulation cost, MCP probe frequency.
- **Release checklist:** capture latency/cost baseline, apply one tuning change at a time, re-measure, promote only if there's no safety/governance regression.
- **Gap:** cost tracking today is manual (read MLflow token counts per trace, compare against the documented budget). There is no automated cost-per-request dashboard or budget-threshold alert, despite the enterprise reference material ([03-security-risk-controls.md](../reference/03-security-risk-controls.md) "Cost and Consumption Risk" row) calling for one.

## Summary Table

| Dimension | Status | Authoritative doc |
| --- | --- | --- |
| Observability (tracing, audit events) | Implemented | [mlflow-guide.md](mlflow-guide.md) |
| Evaluation/quality scoring | Implemented (one known non-blocking KPI gap) | [evaluation-spec.md](../quality/evaluation-spec.md) |
| Safety/guardrails | Implemented | [prompt-policy-controls.md](../governance/prompt-policy-controls.md) |
| Drift/anomaly detection | **Not implemented** — target-state only | [03-security-risk-controls.md](../reference/03-security-risk-controls.md) |
| Token cost/performance | Implemented, manual | [cost-performance-budget.md](cost-performance-budget.md) |

## Possible Improvements to Level Up

- **Automated drift monitoring.** Schedule a recurring job (weekly/bi-weekly) that re-runs the evaluation suite against a fixed holdout set and plots KPI trend over time, rather than relying on ad hoc manual re-runs after a release.
- **Retrieval/index staleness alerting.** Add an automated check that flags when an AI Search index (`dim_product_search_index`, `flink_support_index`) hasn't been refreshed within its `freshness_sla`, instead of relying on the semantics-layer job schedule alone.
- **Cost anomaly alerting.** Add a scheduled job that compares recent token-usage/cost-per-request against a rolling baseline and raises an alert on sudden increases, closing the gap called out in [03-security-risk-controls.md](../reference/03-security-risk-controls.md).
- **Wire monitoring signals to a dashboard.** The signals in [cost-performance-budget.md](cost-performance-budget.md) are defined but not yet dashboarded; connect them to a standing dashboard (System Tables + a BI tool, or MLflow-native charts) instead of manual trace inspection.
- **Resolve the `tool_call_accuracy` scoring gap** documented in [evaluation-spec.md](../quality/evaluation-spec.md) and re-enable it as a blocking KPI once fixed — this is the single biggest quality-monitoring gap today.
- **Business-KPI-linked anomaly detection.** Once a unified cross-domain semantic view exists (see the Tier 3 candidate case in [08-ai-coe-business-requirements-and-case-design-rules.md](../reference/08-ai-coe-business-requirements-and-case-design-rules.md)), extend anomaly detection beyond system metrics to business KPI movement (e.g., sudden CDI drop, sales anomaly) as called for in the "Operational Command Center" use case in [07-use-case-workflows.md](../reference/07-use-case-workflows.md).

## Related Documents

- [mlflow-guide.md](mlflow-guide.md)
- [cost-performance-budget.md](cost-performance-budget.md)
- [../quality/evaluation-spec.md](../quality/evaluation-spec.md)
- [../governance/prompt-policy-controls.md](../governance/prompt-policy-controls.md)
- [../governance/agent-harness-engineering-guidelines.md](../governance/agent-harness-engineering-guidelines.md)
- [../reference/01-foundation-governance.md](../reference/01-foundation-governance.md)
- [../reference/03-security-risk-controls.md](../reference/03-security-risk-controls.md)
- [../adrs/0004-lifecycle-message-bus.md](../adrs/0004-lifecycle-message-bus.md)
- [../adrs/0006-unity-catalog-audit-table-for-lifecycle-events.md](../adrs/0006-unity-catalog-audit-table-for-lifecycle-events.md)
