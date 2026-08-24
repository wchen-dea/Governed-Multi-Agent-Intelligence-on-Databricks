# MLflow Execution Tracker Template

Use this tracker with the implementation checklist to manage execution status, ownership, dates, and risks.

This is a planning template, not a current runtime status record. Use the [MLflow guide](mlflow-guide.md), [evaluation specification](../quality/evaluation-spec.md), and deployment evidence for current implementation state.

Related plan: [MLflow Implementation Checklist](mlflow-rollout-checklist.md)

## Program Status

| Field | Value |
| --- | --- |
| Program Owner |  |
| Reporting Cadence | Weekly |
| Current Phase | Foundation |
| Overall Status | Not Started |
| Last Updated | YYYY-MM-DD |

## Phase Milestones

| Phase | Target Date | Status | Owner | Notes |
| --- | --- | --- | --- | --- |
| Foundation (0-2 weeks) | YYYY-MM-DD | Not Started |  |  |
| Continuous Monitoring (2-6 weeks) | YYYY-MM-DD | Not Started |  |  |
| Production Hardening (6-12 weeks) | YYYY-MM-DD | Not Started |  |  |

## Work Item Tracker

| ID | Work Item | Phase | Owner | Start | Due | Status | Dependencies | Acceptance Criteria | Evidence Link | Blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ML-01 | Standardize MLflow experiment structure | Foundation | AI Platform Lead |  |  | Not Started |  | Env runs write to mapped experiments only |  |  |
| ML-02 | Enforce trace metadata baseline | Foundation | Backend Lead |  |  | Not Started | ML-01 | Metadata completeness >= 95% |  |  |
| ML-03 | Make evaluation gates deterministic | Foundation | QA and Evaluation Owner |  |  | Not Started | ML-02 | Missing KPI fails when strict mode enabled |  |  |
| ML-04 | Wire CI to MLflow gate outputs | Foundation | MLOps Lead |  |  | Not Started | ML-03 | Deploy blocked on failed quality gate |  |  |
| ML-05 | Add online quality dashboards | Continuous Monitoring | AI Platform Lead |  |  | Not Started | ML-04 | Dashboards with env and subagent filters |  |  |
| ML-06 | Build regression comparison workflow | Continuous Monitoring | QA and Evaluation Owner |  |  | Not Started | ML-05 | Weekly regression report with owner assignments |  |  |
| ML-07 | Connect user feedback to trace IDs | Continuous Monitoring | Backend Lead |  |  | Not Started | ML-05 | Feedback to trace linkage >= 90% |  |  |
| ML-08 | Add promotion policy and approvals | Production Hardening | MLOps Lead |  |  | Not Started | ML-06 | No prod promotion without approved quality bundle |  |  |
| ML-09 | Introduce canary auto-stop conditions | Production Hardening | Product and Ops Owner |  |  | Not Started | ML-08 | Rollout halts on KPI or safety breaches |  |  |
| ML-10 | Achieve full lineage and reproducibility | Production Hardening | AI Platform Lead |  |  | Not Started | ML-09 | Incident replay from run metadata succeeds |  |  |

Status options: Not Started, In Progress, Blocked, At Risk, Complete.

## Weekly Review Template

### YYYY-MM-DD

- Wins:
  - 
- Risks:
  - 
- Decisions Needed:
  - 
- Next Week Focus:
  - 

## Decision Log

| Date | Decision | Owner | Impact | Follow-up |
| --- | --- | --- | --- | --- |
| YYYY-MM-DD |  |  |  |  |

## Open Risks and Mitigations

| Risk | Severity | Owner | Mitigation | Due | Status |
| --- | --- | --- | --- | --- | --- |
|  | High/Med/Low |  |  |  | Open |
