# Evaluation Spec

Define how model, routing, safety, and authorization quality are measured and enforced.

## Purpose

Provide one source of truth for evaluation datasets, scorer behavior, KPI thresholds, and release-gate policy.

## Evaluation Scope

- Tool routing correctness
- Authorization correctness
- Safety behavior
- Groundedness and relevance
- Conversation quality and usability

## Data Sets

### Baseline Simulation Set

- Source: `src/backend/evaluate_agent.py` simulator test cases
- Use for: pre-merge regression checks and release-gate validation

### Governed and Sensitive Set

- Source: curated prompts that require policy enforcement and evidence
- Use for: policy and guardrail regression checks

### Authorization Set

- Source: prompts requiring `auth_mode=obo` with and without forwarded token context
- Use for: auth correctness validation

### Evaluation Status (2026-08-23)

The latest Databricks-backed simulator run completed and logged an MLflow evaluation run. The release gate correctly blocked promotion because tool-call accuracy was `0.400`, below the required `0.800`. This is an active quality failure, not a missing-metrics condition.

The run also reported scorer failures for completeness, fluency, and relevance. These failures must be triaged from the individual trace assessments before treating the evaluation as a stable baseline.

## Scoring Specification

Default scorers:

- ToolCallCorrectness
- Safety
- RelevanceToQuery
- Completeness
- ConversationCompleteness
- ConversationalSafety
- KnowledgeRetention
- UserFrustration
- Fluency
- AuthCorrectness (custom)
- DirectGroundedness (custom; evidence marker and freshness metadata)

Custom scorer implementation:

- `src/backend/evaluate_agent.py`

## KPI Thresholds (Release Gate)

- `EVAL_MIN_TOOL_CALL_ACCURACY` default `0.80`
- `EVAL_MIN_AUTH_CORRECTNESS` default `0.90`
- `EVAL_MIN_SAFETY` default `0.95`
- `EVAL_MIN_GROUNDEDNESS` default `0.80`
- `EVAL_REQUIRE_ALL_KPIS` default `false` (set `true` for strict enforcement)

The CI workflow sets `EVAL_REQUIRE_ALL_KPIS=true`; local `make evaluate` follows the process environment and may use the softer default.

## Gate Policy

Deployment is blocked when:

- Any required KPI is missing while strict mode is enabled.
- Any observed KPI falls below its configured threshold.

Tool-call accuracy is evaluated over all simulator turns, including turns where the user is acknowledging an answer, asking for clarification, or asking whether a goal is complete. The route planner therefore uses confidence-gated narrowing: confident capability matches narrow tools; weak or ambiguous matches retain policy-approved candidates. The evaluation corpus still needs explicit `no_tool_required` expectations for conversational turns so the model is not rewarded for calling a business tool unnecessarily.

## Execution Commands

```bash
make evaluate
uv run assistant-evaluate
```

Use `make evaluate` when:

- Before deploy/redeploy to validate release-gate KPIs.
- After changes to prompts, routing, guardrails, or authorization logic.
- After adding/renaming tools or subagents that can affect tool-call correctness.
- After model or evaluator configuration changes that may affect quality or safety.
- Before merging pull requests that change agent runtime behavior.

When evaluation fails, preserve the MLflow run ID and classify each failed turn as one of:

- incorrect tool selected
- required tool omitted
- tool should not have been called
- policy or auth decision mismatch
- scorer invocation failure

Do not lower `EVAL_MIN_TOOL_CALL_ACCURACY` to mask a routing regression.

Use `make test` for fast code-level regressions; use `make evaluate` for end-to-end conversational quality validation with MLflow scoring and release-gate enforcement.

CI pipeline enforcement:

- `.github/workflows/databricks-cicd.yml`

## Proposed Model Experiment Matrix

The following profiles are an experiment and promotion plan, not active target configuration. Current dev model routing resolves standard, reasoning, and synthesis to `databricks-gpt-5-6-luna` unless target environment variables explicitly override it.

The project supports model selection at three layers:

- Orchestrator model via `ORCHESTRATOR_MODEL`.
- Subagent model/endpoint per environment config in `src/backend/domain/subagents.<target>.json`.
- Evaluation user model in `src/backend/evaluate_agent.py` (`simulator.user_model`).

### Recommended Runtime Profiles

| Profile | Orchestrator model | Subagent model strategy | Evaluation model | Cost | Quality | Latency | Use case |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Balanced (default) | `databricks-gpt-5-6-luna` | Keep current target-specific Genie and AI Search MCP routes | `databricks:/databricks-claude-sonnet-5` | Medium | High | Medium | Day-to-day development and standard release checks |
| Quality-first | `databricks-claude-sonnet-5` | Keep current routes and enforce strict guardrails/evidence on governed paths | `databricks:/databricks-claude-sonnet-5` | High | Very high | Medium-high | High-stakes release validation and executive-facing workflows |
| Cost-first | Smaller served instruction model endpoint in workspace | Keep Genie and AI Search routes unchanged; optimize only orchestration cost first | Smaller model for fast loops plus nightly Sonnet baseline | Low | Medium | Fast | High-volume internal traffic and rapid iteration |

### Proposed Environment-Specific Recommendation

- `dev`:
	- Profile: Cost-first for inner loop, plus Balanced once per day.
	- Orchestrator: smaller workspace-served model for local/branch testing.
	- Evaluation: fast model for PR loops and `databricks:/databricks-claude-sonnet-5` before merge to shared branch.
- `qa`:
	- Profile: Balanced.
	- Orchestrator: `databricks-gpt-5-6-luna`.
	- Evaluation: `databricks:/databricks-claude-sonnet-5` on each integration cycle.
- `stg`:
	- Profile: Quality-first.
	- Orchestrator: `databricks-claude-sonnet-5`.
	- Evaluation: `databricks:/databricks-claude-sonnet-5` with strict KPI enforcement (`EVAL_REQUIRE_ALL_KPIS=true`).
- `prod`:
	- Profile: Balanced runtime with Quality-first pre-release gate.
	- Orchestrator: `databricks-gpt-5-6-luna` by default; temporarily promote to `databricks-claude-sonnet-5` for sensitive launches.
	- Evaluation: required Sonnet 5 gate before deployment and periodic post-release drift checks.

### Promotion Rule

- Promote model/profile changes only when `make evaluate` passes gate thresholds in the target environment.
- For Cost-first adoption, require no regression in tool-call correctness, auth correctness, and safety versus the Balanced baseline.

## Reporting and Review

For each release candidate, capture:

- Aggregate KPI values
- Failing test cases and root-cause category
- Decision: pass, conditional pass, or block
- Follow-up owner and remediation timeline

## Ownership

- Primary owner: platform engineering
- Review partners: product analytics, security/governance, and operations

## Related Documents

- [Quality guide](README.md)
- [Runtime technical specifications](../architecture/runtime-technical-specs.md)
- [Business specifications](../product/business-specs.md)
- [Operations runbook](../operations/operations-runbook.md)
- [Evaluation KPI release-gate ADR](../adrs/0007-evaluation-kpi-release-gate.md)
