# Multiagent App on Databricks: Runbook (Operations)

## Purpose

This is the operator runbook for deployment, verification, incident response, and rollback.
Use it as the execution reference for target-based releases.

## Scope

This document covers deployment and operations only. High-level system context is in `docs/architecture/system-architecture.md`, and implementation details are in `docs/architecture/system-design.md`.

## Current Status

- Dev app is running and user-accessible.
- Hosted startup uses UI mode with backend internal port remapping.
- Bundle validation is stable.
- Deployment can fail intermittently when Terraform provider registry is unreachable.
- Fallback workflow is in active use when registry outage occurs.

## Start Here

Use this default release sequence:

1. Pre-deployment checklist
2. Prepare app-source payload (wheel + React UI)
3. Validate bundle
4. Deploy bundle
5. Import prepared app source to workspace path
6. Deploy app from workspace source path
7. Execute post-deploy verification

For target values:

- `dev`: `--profile dev`
- `qa`: `--profile qa`
- `stg`: `--profile stg`
- `prod`: `--profile prd`

## Run Procedures

### Pre-Deployment Checklist

- Confirm target (`dev` / `qa` / `stg` / `prod`) and CLI profile.
- Confirm target variables in `targets/*.yml` are correct.
- Confirm Databricks credentials/secrets are available for target.
- Confirm no pending manual hotfix state in the target app.

### UC Audit + KPI Gate Release Checklist

Before promoting to `qa`, `stg`, or `prod`, ensure these placeholders are replaced in the corresponding target file:

- `message_bus_backend: uc_table`
- `uc_audit_warehouse_id: <...>`
- `uc_audit_catalog: <...>`
- `uc_audit_schema: <...>`
- `uc_audit_table: agent_lifecycle_events` (or approved override)

Then verify CI/deployment environment variables are set for evaluation gate thresholds:

- `EVAL_MIN_TOOL_CALL_ACCURACY`
- `EVAL_MIN_AUTH_CORRECTNESS`
- `EVAL_MIN_SAFETY`
- `EVAL_MIN_GROUNDEDNESS`
- `EVAL_REQUIRE_ALL_KPIS=true`

Model profile selection by environment is documented in:

- [Model Matrix and Environment Recommendations](../quality/evaluation-spec.md#model-matrix-and-environment-recommendations)

Final pre-release checks:

- Run `databricks bundle validate -t TARGET --profile PROFILE`
- Run `uv run pytest -q`
- Run `uv run agent-evaluate`
- Confirm no placeholder values remain in target config files.

### Standard Deployment

#### 0) Prepare app-source payload (wheel + React UI)

```bash
uv run prepare-app-source
```

Notes:

- Wheel binaries under `.databricks_app_source/wheels/*.whl` are generated artifacts and are git-ignored.
- Keep `.databricks_app_source/wheels/.gitkeep` committed so the wheel directory exists in fresh clones and CI.

#### 1) Validate bundle

```bash
databricks bundle validate -t dev --profile dev
databricks bundle validate -t qa --profile qa
databricks bundle validate -t stg --profile stg
databricks bundle validate -t prod --profile prd
```

#### 2) Deploy

```bash
databricks bundle deploy -t TARGET --profile PROFILE
```

#### 3) Import prepared app source

```bash
APP_SRC=$(databricks apps get APP_NAME --output json --profile PROFILE | jq -r '.default_source_code_path')
databricks workspace import-dir .databricks_app_source "$APP_SRC" --overwrite --profile PROFILE
```

#### 4) Deploy app from imported source

```bash
databricks apps deploy APP_NAME --profile PROFILE --source-code-path "$APP_SRC" --mode SNAPSHOT
```

### Fallback Deployment Procedure

Use this procedure when `bundle deploy` fails due to Terraform provider registry availability.

```bash
databricks bundle sync -t TARGET --profile PROFILE
APP_SRC=$(databricks apps get APP_NAME --output json --profile PROFILE | jq -r '.default_source_code_path')
databricks apps deploy APP_NAME --profile PROFILE --source-code-path "$APP_SRC" --mode SNAPSHOT
```

Concrete command form (dev example):

```bash
APP_NAME="multiagent-app-dev"
PROFILE="DEFAULT"
APP_SRC="$(databricks apps get "$APP_NAME" --profile "$PROFILE" --output json | jq -r '.default_source_code_path')"
databricks apps deploy "$APP_NAME" --profile "$PROFILE" --source-code-path "$APP_SRC" --mode SNAPSHOT
```

### Databricks App Source Caveat

In some environments, relying on bundle runtime commands may use a reduced source payload (for example, only bundle resource files), which can fail startup with errors such as missing command or missing modules.

When this occurs, use the explicit app-source deployment path below to deploy the app-source payload:

```bash
uv run prepare-app-source
databricks apps deploy APP_NAME --profile PROFILE \
  --source-code-path "/Workspace/Users/<user>/.bundle/<bundle-name>/<target>/files/.databricks_app_source" \
  --mode SNAPSHOT
```

Then verify:

```bash
databricks apps get APP_NAME --output json --profile PROFILE
```

Expected health fields:

- `active_deployment.status.state = SUCCEEDED`
- `app_status.state = RUNNING`

### GitHub Actions Pipeline Alignment (App-Source Payload)

The GitHub Actions deployment pipeline is aligned to this runbook and uses Makefile-driven app-source payload delivery (wheel + React UI):

1. Build wheel and React UI payload: `make build-app-source`.
2. Validate bundle by target: `make validate TARGET="$DAB_TARGET"`.
3. Attempt bundle deploy: `make bundle-deploy TARGET="$DAB_TARGET"`.
4. Import prepared app source to workspace: `make import TARGET="$DAB_TARGET" APP_NAME="$APP_NAME"`.
5. Deploy app from workspace source path: `make deploy TARGET="$DAB_TARGET" APP_NAME="$APP_NAME"`.
6. Final health and smoke gates: `make health ...` and `make smoke ...`.

This keeps repository state clean (no committed wheel binaries) while ensuring each CI run deploys a fresh wheel artifact.

Workflow file:

- `.github/workflows/databricks-cicd.yml`

Required GitHub secrets by environment suffix:

- `DATABRICKS_HOST_DEV`, `DATABRICKS_CLIENT_ID_DEV`, `DATABRICKS_CLIENT_SECRET_DEV`
- `DATABRICKS_HOST_QA`, `DATABRICKS_CLIENT_ID_QA`, `DATABRICKS_CLIENT_SECRET_QA`
- `DATABRICKS_HOST_STG`, `DATABRICKS_CLIENT_ID_STG`, `DATABRICKS_CLIENT_SECRET_STG`
- `DATABRICKS_HOST_PROD`, `DATABRICKS_CLIENT_ID_PROD`, `DATABRICKS_CLIENT_SECRET_PROD`

### Existing App Conflict

Use this procedure when the app already exists and deployment cannot reconcile state:

```bash
databricks bundle deployment bind multiagent-app APP_NAME --auto-approve
databricks bundle deploy -t TARGET --profile PROFILE
```

Alternative recreate path:

```bash
databricks apps delete APP_NAME --profile PROFILE
databricks bundle deploy -t TARGET --profile PROFILE
```

### Genie Agent Semantic Metric View Checklist

Use this short checklist when onboarding or updating a Genie Agent backed by business metrics.

1. Model Semantic Metric Views in Unity Catalog

- Define business KPI scope, grain, dimensions, and measures.
- Apply consistent semantic metadata (for example domain, subject, owner, grain).
- Recommended blueprint: [Unity-Catalog-Semantic-Metric-Views-Blueprint](https://github.com/wchen-dea/Unity-Catalog-Semantic-Metric-Views-Blueprint)

2. Validate with representative Genie prompts

- Run prompt sets for trend, comparison, anomaly, and segmentation questions.
- Verify metric definitions, filters, and aggregation behavior match business expectations.
- Confirm source traceability and naming consistency in generated answers.

3. Register Genie Agent runtime configuration

- Add or update the target entry in `src/backend/domain/subagents.<target>.json`.
- Verify `space_id`, `auth_mode`, classification metadata, and owner metadata.

4. Grant and verify permissions

- Ensure app resource grants include the Genie Agent space in `resources/multiagent_app.yml`.
- Grant runtime identity permissions (`CAN_RUN`) and validate OBO/app auth paths as required.
- Re-run deploy-time verification and smoke checks before promotion.

### Post-Deploy Verification

- Non-streaming request succeeds.
- Streaming request succeeds.
- Tool routing behaves as expected.
- Hybrid auth routing behaves as expected (`app` and `obo` paths).
- No startup crash loop.
- Logs do not contain authentication or missing-resource errors.

Minimum verification commands:

```bash
databricks apps get APP_NAME --output json --profile PROFILE
databricks apps logs APP_NAME --follow --profile PROFILE
```

Hybrid auth verification checklist:

- Execute an `app` auth tool path and confirm success without forwarding user token.
- Execute an `obo` auth tool path with forwarded token and confirm success.
- Execute the same `obo` path without forwarded token and confirm clear authorization failure.

### Local Operations

#### Local startup

```bash
uv run start-app
```

Optional worker tuning (local or hosted startup path):

```bash
BACKEND_UVICORN_WORKERS=2
FRONTEND_UVICORN_WORKERS=1
```

#### RabbitMQ message bus local example

Use this when you want lifecycle events to publish through RabbitMQ instead of structured logs.

```bash
# Message bus backend
MESSAGE_BUS_BACKEND=rabbitmq
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
MESSAGE_BUS_ASYNC=true
MESSAGE_BUS_ASYNC_QUEUE_SIZE=1000
MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS=2.0

# RabbitMQ connection
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

Then start the app as usual:

```bash
uv run start-app
```

#### UC audit table message bus local example

Use this when you want lifecycle events written to a Unity Catalog-governed Delta table.

```bash
MESSAGE_BUS_BACKEND=uc_table
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
MESSAGE_BUS_ASYNC=true
MESSAGE_BUS_ASYNC_QUEUE_SIZE=1000
MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS=2.0

UC_AUDIT_WAREHOUSE_ID=<warehouse-id>
UC_AUDIT_CATALOG=main
UC_AUDIT_SCHEMA=observability
UC_AUDIT_TABLE=agent_lifecycle_events
```

The backend auto-creates the schema/table if they do not exist.

#### MCP latency tuning controls

Use these variables to tune MCP connection health-check behavior:

```bash
MCP_CONNECT_TIMEOUT_SECONDS=10
MCP_LIST_TOOLS_TIMEOUT_SECONDS=10
MCP_HEALTH_TTL_SECONDS=30
MCP_HEALTH_FAILURE_TTL_SECONDS=10
ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE=128
```

#### Backend-only

```bash
uv run start-server --reload
uv run start-app --no-ui
```

#### Preflight and evaluation

```bash
uv run preflight
uv run agent-evaluate
```

Release-gate KPI thresholds for evaluation can be tuned with:

```bash
EVAL_MIN_TOOL_CALL_ACCURACY=0.80
EVAL_MIN_AUTH_CORRECTNESS=0.90
EVAL_MIN_SAFETY=0.95
EVAL_MIN_GROUNDEDNESS=0.80
EVAL_REQUIRE_ALL_KPIS=true
```

#### OBO token simulation in UI

Use UI session commands:

```text
/token <databricks_access_token>
/clear-token
```

The UI forwards the token as `x-forwarded-access-token` on `/invocations` requests.

For non-interactive CLI tests against Databricks Apps `/invocations`, use `Authorization: Bearer <token>`.

Example helper:

```bash
make query-dev TARGET=dev APP_NAME=multiagent-app-dev PROFILE=DEFAULT QUERY='top stores by revenue' QUERY_PERSONA=manager
```

### Incident Triage

1. Identify impacted environment.
2. Determine latest deploy source (manual or pipeline).
3. Review deployment output and app logs.
4. Verify credentials, app identities, and permissions.
5. Decide rollback vs forward fix.

Escalate immediately if issue affects multiple targets or production user traffic.

### Common Failure Patterns

- Missing CI secrets for environment.
- Terraform registry unreachable.
- Deploy completed but app-source import/deploy path was skipped.
- Missing Unity Catalog grants for Genie query paths.
- OBO flow missing forwarded token (`x-forwarded-access-token`) for tools configured with `auth_mode: obo`.
- User identity has insufficient data permissions even when app identity has access.
- Invalid local credentials in `.env` (for example stale `DATABRICKS_TOKEN`).

### Rollback

#### Pipeline rollback

- Redeploy the last known good commit through CI.

#### Manual rollback

```bash
databricks bundle deploy -t TARGET --profile PROFILE
APP_SRC=$(databricks apps get APP_NAME --output json --profile PROFILE | jq -r '.default_source_code_path')
databricks workspace import-dir .databricks_app_source "$APP_SRC" --overwrite --profile PROFILE
databricks apps deploy APP_NAME --profile PROFILE --source-code-path "$APP_SRC" --mode SNAPSHOT
```

Deploy a known good revision.

### Change Control

Before:

- Validate target configuration and secrets.

During:

- Use one deployment path per change.
- Capture commit and deployment output.

After:

- Run post-deploy verification.
- Record outcome and follow-up actions.

## Operating Guidelines

1. Always run `bundle validate` before `bundle deploy`.
2. Always import and deploy `.databricks_app_source` after `bundle deploy`.
3. Always include explicit `--profile` in Databricks CLI commands.
4. Prefer bind over delete when resolving existing-app conflicts.
5. Use fallback deploy only when standard deploy is blocked.

## Related Docs

- `docs/architecture/system-architecture.md`: high-level architecture
- `docs/architecture/system-design.md`: low-level design
- `docs/internal/claude.md`: Claude skill usage and operator workflow
