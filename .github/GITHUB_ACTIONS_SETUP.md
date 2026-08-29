# GitHub Actions CI/CD Setup

This repository deploys with `.github/workflows/databricks-cicd.yml`.

## Triggers

- Pull requests targeting `dev`, `qa`, `stg`, `prd`: CI checks (tests, evaluation, app-source build, validate)
- Push to `dev`, `qa`, `stg`, `prd`: full deploy flow
- Manual run: `workflow_dispatch` with target selection

## Required Repository Secrets

Add these secrets in GitHub repository settings:

- `DATABRICKS_HOST_DEV`
- `DATABRICKS_CLIENT_ID_DEV`
- `DATABRICKS_CLIENT_SECRET_DEV`
- `DATABRICKS_HOST_QA`
- `DATABRICKS_CLIENT_ID_QA`
- `DATABRICKS_CLIENT_SECRET_QA`
- `DATABRICKS_HOST_STG`
- `DATABRICKS_CLIENT_ID_STG`
- `DATABRICKS_CLIENT_SECRET_STG`
- `DATABRICKS_HOST_PRD`
- `DATABRICKS_CLIENT_ID_PRD`
- `DATABRICKS_CLIENT_SECRET_PRD`

## Evaluation Defaults

The workflow sets evaluation thresholds and LLM judge defaults directly in `.github/workflows/databricks-cicd.yml` to avoid undefined repository-variable warnings in editors and CI validation.

Current CI defaults:

- `EVAL_MIN_TOOL_CALL_ACCURACY=0.80`
- `EVAL_MIN_AUTH_CORRECTNESS=0.90`
- `EVAL_MIN_SAFETY=0.95`
- `EVAL_MIN_GROUNDEDNESS=0.80`
- `EVAL_REQUIRE_ALL_KPIS=true`
- `EVAL_JUDGE_MODEL=databricks:/databricks-claude-sonnet-5`
- `EVAL_SIMULATOR_USER_MODEL=databricks:/databricks-claude-sonnet-5`

Change these values in the workflow when CI policy changes. Runtime/evaluation jobs can still use Databricks Asset Bundle variables and environment variables outside GitHub Actions.

## Recommended GitHub Environments

Create environments named:

- `dev`
- `qa`
- `stg`
- `prd`

Then add any required approval rules for promotion control.

## Branch Strategy

- Merge PR into `dev` to trigger `dev` deployment.
- Promote to `qa`, `stg`, and `prd` via PRs to those branches.
- Each merge triggers environment-specific deployment automatically.
