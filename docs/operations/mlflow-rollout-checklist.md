# MLflow Implementation Checklist (One Page)

Purpose: execute an MLflow-first AI engineering rollout for this project with clear ownership, tasks, and acceptance criteria.

Scope: applies to agent runtime, tracing, evaluation, CI release gates, and production monitoring.

## Team Roles

- AI Platform Lead: MLflow experiments, run taxonomy, dashboards, promotion policy.
- Backend Lead: handler instrumentation, trace metadata, policy and guardrail observability.
- MLOps Lead: CI integration, release gates, deployment controls, canary automation.
- QA and Evaluation Owner: scorer coverage, dataset curation, regression triage.
- Product and Ops Owner: SLO targets, incident thresholds, operational sign-off.

## Phase 1: Foundation (Now to 2 Weeks)

### 1) Standardize MLflow Experiment Structure

- Owner: AI Platform Lead
- Tasks:
  - Define environment-specific experiment naming and location for dev, qa, stg, and prod.
  - Ensure local and deployed runtimes resolve to the expected experiment without manual overrides.
  - Record experiment map in docs and runbook.
- Acceptance Criteria:
  - Every evaluation run writes to the intended environment experiment.
  - No orphan runs found outside approved experiment paths for one full sprint.
- Evidence:
  - Experiment mapping section added to docs.
  - Screenshots or exported run listings per environment.

### 2) Enforce Trace Metadata Baseline

- Owner: Backend Lead
- Tasks:
  - Guarantee each request trace includes persona, auth mode, user token presence, selected subagent or tool, and policy plus guardrail outcomes.
  - Add coverage checks for missing metadata keys in test runs.
  - Ensure invoke and stream flows emit equivalent metadata quality.
- Acceptance Criteria:
  - Metadata completeness at or above 95 percent on sampled runs.
  - Missing required metadata fails CI quality checks.
- Evidence:
  - Updated traces and metadata reports.
  - Test output proving metadata completeness checks.

### 3) Make Evaluation Gates Deterministic

- Owner: QA and Evaluation Owner
- Tasks:
  - Keep release gate thresholds centralized via environment variables.
  - Ensure evaluation output produces a compact pass or fail summary artifact.
  - Treat missing KPI metrics as failure when strict mode is enabled.
- Acceptance Criteria:
  - Every evaluation run outputs all KPI values or explicitly fails.
  - CI blocks promotion when thresholds are not met.
- Evidence:
  - CI logs from passing and failing gate scenarios.
  - Stored evaluation artifact with KPI table.

### 4) Wire CI to MLflow Gate Outputs

- Owner: MLOps Lead
- Tasks:
  - Add a dedicated CI stage that runs evaluation and checks gate outcome before deploy.
  - Persist MLflow run ID and gate decision as build artifacts.
  - Make gate failure messaging actionable with metric deltas.
- Acceptance Criteria:
  - No successful deploy pipeline can bypass evaluation gate stage.
  - Build artifacts contain MLflow run link or ID plus gate decision.
- Evidence:
  - Pipeline configuration update and run screenshots.

## Phase 2: Continuous Quality Monitoring (2 to 6 Weeks)

### 5) Add Online Quality Dashboards

- Owner: AI Platform Lead
- Tasks:
  - Create dashboards for tool call correctness, auth correctness, safety, groundedness, latency, and cost trend.
  - Slice views by persona, subagent, and auth mode.
  - Define alert thresholds and notification channels.
- Acceptance Criteria:
  - Dashboard refreshes daily and supports environment filtering.
  - Alerts fire for threshold breaches and route to on-call channel.
- Evidence:
  - Dashboard URLs and alert rule exports.

### 6) Build Regression Comparison Workflow

- Owner: QA and Evaluation Owner
- Tasks:
  - Compare candidate builds against last known good baseline.
  - Add top-regression summary for scorer and route level.
  - Include failure clustering for policy, guardrail, and tool correctness.
- Acceptance Criteria:
  - Weekly regression report generated automatically.
  - Top 3 regressions have owners and remediation status.
- Evidence:
  - Regression report artifact with deltas.

### 7) Connect User Feedback to Trace IDs

- Owner: Backend Lead
- Tasks:
  - Attach user feedback events to corresponding request or trace identifiers.
  - Store feedback with enough context for scorer and route analysis.
  - Add a simple quality review query path for low-rated interactions.
- Acceptance Criteria:
  - At least 90 percent of feedback events map to a trace ID.
  - Feedback can be filtered by persona, subagent, and outcome reason.
- Evidence:
  - Example joined records and review workflow output.

## Phase 3: Production Hardening (6 to 12 Weeks)

### 8) Add Promotion Policy and Approval Workflow

- Owner: MLOps Lead
- Tasks:
  - Require MLflow metrics, baseline comparison, and policy checks before promotion.
  - Add explicit approval step for production transitions.
  - Capture release decision metadata for audit.
- Acceptance Criteria:
  - No production promotion without an approved quality bundle.
  - Promotion history is auditable with run ID, approver, and gate values.
- Evidence:
  - Promotion policy document and example approved run.

### 9) Introduce Canary with Automatic Stop Conditions

- Owner: Product and Ops Owner
- Tasks:
  - Define canary traffic split and holdback policy.
  - Stop rollout automatically on KPI degradation, safety incidents, or auth regressions.
  - Add rollback trigger and incident template linkage.
- Acceptance Criteria:
  - Canary stops automatically when thresholds are breached.
  - Rollback completes within agreed operational window.
- Evidence:
  - Canary run logs and rollback test record.

### 10) Achieve Full Lineage and Reproducibility

- Owner: AI Platform Lead
- Tasks:
  - Persist code version, config snapshot, dataset version, scorer versions, and model endpoint references per run.
  - Ensure incident replay can reconstruct outputs from logged artifacts.
- Acceptance Criteria:
  - Any production incident can be replayed from run metadata and artifacts.
  - Monthly audit sample passes reproducibility checks.
- Evidence:
  - Lineage checklist and replay report.

## Definition of Done Across All Phases

- All tasks have owner, due date, and status.
- Each acceptance criterion has objective evidence.
- CI and deployment docs reflect current gate behavior.
- Runbook includes operational actions for gate failures and quality incidents.

## Immediate Backlog (Start This Week)

- Add experiment mapping and quality gate section to docs and runbook.
- Add metadata completeness checks to evaluation pipeline.
- Publish first KPI summary artifact from CI.
- Create first dashboard draft with environment and subagent filters.
