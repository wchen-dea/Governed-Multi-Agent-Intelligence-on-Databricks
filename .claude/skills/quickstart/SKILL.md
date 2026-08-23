---
name: quickstart
description: "Initialize local Databricks development for this repository. Use when: first setup, auth/profile setup, .env bootstrapping, or MLflow experiment setup."
---

# Quickstart

Use this skill to set up local development for this project.

## When to Use

- First run on a new machine
- `.env` is missing or invalid
- Databricks authentication/profile is not configured
- `MLFLOW_EXPERIMENT_ID` is missing

## Commands

```bash
uv run assistant-bootstrap
```

Common variants:

```bash
uv run assistant-bootstrap --profile <profile>
uv run assistant-bootstrap --host https://<workspace-host>
uv run assistant-bootstrap --app-name <existing-app-name>
uv run assistant-bootstrap --skip-lakebase
uv run assistant-bootstrap --help
```

## What This Configures

- Databricks profile selection or creation
- `.env` defaults for local execution
- MLflow tracking/experiment configuration
- Optional app binding for existing Databricks Apps

## Verify Setup

```bash
databricks auth profiles
uv run runtime-preflight
uv run runtime-serve-app
```

## Notes

- Prefer OAuth profile auth over hard-coded tokens.
- If auth fails, re-run `databricks auth login --profile <profile>` and retry.
- After quickstart, continue with `run-locally` or `deploy`.
