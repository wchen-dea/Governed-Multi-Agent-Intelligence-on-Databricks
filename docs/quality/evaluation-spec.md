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

Custom scorer implementation:

- `src/backend/evaluate_agent.py`

## KPI Thresholds (Release Gate)

- `EVAL_MIN_TOOL_CALL_ACCURACY` default `0.80`
- `EVAL_MIN_AUTH_CORRECTNESS` default `0.90`
- `EVAL_MIN_SAFETY` default `0.95`
- `EVAL_MIN_GROUNDEDNESS` default `0.80`
- `EVAL_REQUIRE_ALL_KPIS` default `false` (set `true` for strict enforcement)

## Gate Policy

Deployment is blocked when:

- Any required KPI is missing while strict mode is enabled.
- Any observed KPI falls below its configured threshold.

## Execution Commands

```bash
make evaluate
uv run agent-evaluate
```

Use `make evaluate` when:

- Before deploy/redeploy to validate release-gate KPIs.
- After changes to prompts, routing, guardrails, or authorization logic.
- After adding/renaming tools or subagents that can affect tool-call correctness.
- After model or evaluator configuration changes that may affect quality or safety.
- Before merging pull requests that change agent runtime behavior.

Use `make test` for fast code-level regressions; use `make evaluate` for end-to-end conversational quality validation with MLflow scoring and release-gate enforcement.

CI pipeline enforcement:

- `.github/workflows/databricks-cicd.yml`

## Model Matrix and Environment Recommendations

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

### Environment-Specific Recommendation

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

- ../architecture/runtime-technical-specs.md
- ../product/business-specs.md
- ../operations/operations-runbook.md
- ../adrs/0007-evaluation-kpi-release-gate.md
