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

## Optional Repository Variables

- `EVAL_MIN_TOOL_CALL_ACCURACY`
- `EVAL_MIN_AUTH_CORRECTNESS`
- `EVAL_MIN_SAFETY`
- `EVAL_MIN_GROUNDEDNESS`
- `EVAL_REQUIRE_ALL_KPIS`
- `EVAL_JUDGE_MODEL`
- `EVAL_SIMULATOR_USER_MODEL`

If not provided, the workflow defaults are used.

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
