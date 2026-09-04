# Operations Guide

## Scope

This section owns deployment procedures, runtime verification, MLflow operations, cost/performance planning, scripts, and incident materials. Runtime contracts are authoritative in [architecture](../architecture/README.md); this section explains how to operate them.

## Operational Paths

| Need | Start here |
| --- | --- |
| Deploy or recover an app | [Operations runbook](operations-runbook.md) |
| Deliver the React web UI | [UI deployment guide](ui-deployment-guide.md) |
| Review commands | [Command reference](command-reference.md) |
| Trace or evaluate behavior | [MLflow guide](mlflow-guide.md) and [evaluation specification](../quality/evaluation-spec.md) |
| Understand monitoring coverage and gaps | [AI agent monitoring: observability, evaluation, safety, drift, and cost](ai-agent-monitoring-observability.md) |
| Plan cost/performance | [Cost and performance budget](cost-performance-budget.md) |
| Run a release activity | [MLflow rollout checklist](mlflow-rollout-checklist.md) |
| Capture an incident | [Postmortem template](postmortem-template.md) |

## Deployment Authority

- The [operations runbook](operations-runbook.md) is authoritative for app-level
	deployment, Databricks resources, permissions, health checks, smoke checks,
	rollback, and incident recovery.
- The [UI deployment guide](ui-deployment-guide.md) is authoritative for
	frontend-local development, browser checks, and the UI build inputs that feed
	the app-source payload. It does not replace the app deployment procedure in
	the runbook.
- The [command reference](command-reference.md) is the index of canonical command
	groups and release targets; workflow guides show commands in their operational
	context.
- `make redeploy` is the full validation, bundle-attempt, grants, health, and smoke workflow.
- `make upload-wheel` is the versioned source-only fallback. It cannot apply bundle-managed resources or grants.
- Run `uv run assistant-evaluate` to determine current gate status. Tool-call accuracy is monitored but non-blocking while nested tool spans cannot be scored reliably.

## Templates

The rollout checklist, rollout tracker, and postmortem are operating templates. They do not replace current implementation facts, target configuration, or deployment evidence.
