# Multiagent App on Databricks: Runbook (Operations)

## Purpose

This is the operator runbook for deployment, verification, incident response, and rollback.
Use it as the execution reference for target-based releases.

## Scope

This document covers deployment and operations only. High-level system context is in `docs/architecture/high-level-architecture.md`, and implementation details are in `docs/architecture/low-level-design.md`.

## Current Status

- Dev app is running and user-accessible.
- Hosted startup uses UI mode with backend internal port remapping.
- Bundle validation is stable.
- Deployment can fail intermittently when Terraform provider registry is unreachable or the provider crashes.
- Fallback workflow is in active use when registry outage or provider crash occurs.
- SNAPSHOT-mode deploys do not inject `app.yml` env vars at the platform level; the launcher reads them from `app.yml` at startup.
- Lakebase ODS agent uses the `multiagent_app/lakebase_pg_password` secret for SCRAM authentication, with OAuth credentials as runtime fallback.

## Start Here

Use this default release sequence:

1. Pre-deployment checklist
2. Prepare app-source payload (wheel + React UI)
3. Validate bundle
4. Deploy bundle
5. Import prepared app source to workspace path
6. Deploy app from workspace source path
7. Execute post-deploy verification

The bundle deployment must apply both the Lakebase Autoscaling app resource and the Databricks secret resource. For the dev target, the expected references are `projects/ore/branches/production`, `projects/ore/branches/production/databases/operationaldatastore`, and secret `multiagent_app/lakebase_pg_password`.

For target values:

- `dev`: `--profile dev`
- `qa`: `--profile qa`
- `stg`: `--profile stg`
- `prod`: `--profile prd`

## Run Procedures

### Pre-Deployment Checklist

- Confirm target (`dev` / `qa` / `stg` / `prod`) and CLI profile.
- Confirm target variables in `targets/*.yml` are correct.
- Confirm Databricks credentials/secrets are available for target, including the `multiagent_app` scope and rotated `lakebase_pg_password` key; never place the value in `targets/*.yml`.
- Confirm no pending manual hotfix state in the target app.

For a new environment, create the secret before deployment:

```bash
databricks secrets create-scope multiagent_app --profile PROFILE
databricks secrets put-secret multiagent_app lakebase_pg_password --profile PROFILE
databricks secrets list-secrets multiagent_app --profile PROFILE
```

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
- Terraform registry unreachable or Terraform provider crash (`Plugin did not respond`).
- Deploy completed but app-source import/deploy path was skipped.
- SNAPSHOT deploy did not inject env vars — launcher must read them from `app.yml`.
- Missing Unity Catalog grants for Genie query paths.
- OBO flow missing forwarded token (`x-forwarded-access-token`) for tools configured with `auth_mode: obo`.
- User identity has insufficient data permissions even when app identity has access.
- Invalid local credentials in `.env` (for example stale `DATABRICKS_TOKEN`).
- Lakebase auth failure due to SCRAM password mismatch or OAuth `pg_user` misconfiguration.
- Databricks SDK `Config.authenticate()` signature change breaking Lakebase OAuth token retrieval.

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

- `docs/architecture/high-level-architecture.md`: high-level architecture
- `docs/architecture/low-level-design.md`: low-level design
- `docs/internal/claude.md`: Claude skill usage and operator workflow

## Agent Use Cases (Web UI Verification)

App URL: `https://multiagent-app-dev-4225037891036111.aws.databricksapps.com`

### 1. Sales Insights Agent (Genie)

**Scenario:** Regional manager reviews top stores by revenue for the current season.

**Steps:**

1. Open the app URL in a browser.
2. Type: `What are the top 10 stores by total revenue this season?`
3. Verify the response contains a table with store codes, revenue figures, and season context.
4. Follow up: `Compare those stores to last season`
5. Verify comparative data is returned with evidence citation.

### 2. Product Index Assistant (AI Search RAG)

**Scenario:** Store associate looks up a product by partial description.

**Steps:**

1. Open the app URL in a browser.
2. Type: `Find products matching "all season 225/65R17 tire"`
3. Verify the response returns product codes, descriptions, brand codes, and article types.
4. Follow up: `What brand is product code 12345?`
5. Verify a specific product record is returned from the index.

### 3. Flink Support Agent (AI Search RAG)

**Scenario:** Data engineer troubleshoots a Flink streaming job with growing consumer lag.

**Steps:**

1. Open the app URL in a browser.
2. Type: `Our Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?`
3. Verify the response is grounded in retrieved documents with bracketed citations (e.g., `[1]`).
4. Verify a `Source:` line lists the cited document paths.
5. Follow up: `How do we configure checkpointing for exactly-once processing?`

### 4. CDI Agent (Genie)

**Scenario:** District manager reviews Customer Delight Indicator scores across stores.

**Steps:**

1. Open the app URL in a browser.
2. Type: `What are the current CDI scores across all stores?`
3. Verify the response contains a table with store-level promoter/detractor/response counts.
4. Follow up: `Which stores have the lowest overall delight score this month?`
5. Verify ranked results with evidence citation.

### 5. Lakebase ODS Agent (Lakebase SQL)

**Scenario:** Operations analyst checks appointment volume by order type in the operational data store.

**Lakebase config:**

- Project: `ore` (resource path: `projects/ore`)
- Branch: `production` (resource path: `projects/ore/branches/production`)
- Endpoint: `primary` (host: `ep-falling-cake-d1j29nc5.database.us-west-2.cloud.databricks.com`)
- Database: `operationaldatastore`
- Database resource: `projects/ore/branches/production/databases/operationaldatastore`
- Secret: scope `multiagent_app`, key `lakebase_pg_password` (injected as `LAKEBASE_PG_PASSWORD`)
- App SP role: `sp-multiagent-app` (postgres_role: `da6ab9ef-2c0f-4f9b-9950-b618b9f4fede`, membership: `DATABRICKS_SUPERUSER`)

**Steps:**

1. Open the app URL in a browser.
2. Type: `How many appointments have an invoice order type name?`
3. Verify the agent generates a SQL query against the Lakebase `operationaldatastore` database and returns a count.
4. Follow up: `Break that down by month for the last 6 months`
5. Verify the response contains a formatted table with monthly counts and evidence citation.

### Verification Notes

- No agent selection is needed — the orchestrator routes automatically based on question intent.
- Genie agents (sales, CDI) return SQL-grounded results; `requires_evidence` should be `false` for Genie agents since their output format doesn't include citation markers.
- Default persona is `manager` per dev config; set via custom_inputs if testing persona-restricted agents.

## Troubleshooting

### "evidence_required" guardrail blocks response

**Symptom:** "The backend ended the stream without returning visible content. This often means the response was blocked before it could be shown, for example by an `evidence_required` guardrail."

**Cause:** The subagent has `requires_evidence: true` but the response doesn't contain citation markers (`[1]`, `Source:`, or `Citation:`). Genie agents return tables/SQL results that never include these markers. MCP/RAG agents may also omit them if the system prompt doesn't explicitly require them.

**Fix:**

- For Genie agents: set `requires_evidence: false` in `src/backend/domain/subagents.<target>.json`. Genie output is inherently grounded in SQL.
- For MCP/RAG agents: either set `requires_evidence: false`, or strengthen the system prompt to explicitly instruct: "append a bracketed citation like `[1]`" and "end with a `Source:` line."
- Rebuild and redeploy after changes.

### "Function tools with reasoning_effort are not supported" (HTTP 400)

**Symptom:** `{"detail": "Error code: 400 ... Function tools with reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions."}`

**Cause:** The openai-agents SDK API mode is set to `chat_completions` in `src/backend/api/handlers.py`, but the orchestrator model (e.g., `gpt-5.6-luna`) requires the `/v1/responses` endpoint for function tool support.

**Fix:**

In `src/backend/api/handlers.py`, ensure:

```python
set_default_openai_api("responses")
```

Not `"chat_completions"`. Rebuild and redeploy.

### HTTP 502 Bad Gateway

**Symptom:** `Databricks App - 502 Bad Gateway` on any query.

**Possible causes:**

1. **Missing wheel artifact:** The deployed `wheels/` directory contains no `.whl` file. The launcher raises `FileNotFoundError` on startup.
   - Fix: `make build-app-source && make import TARGET=dev && make deploy TARGET=dev APP_NAME=multiagent-app-dev`

2. **Cold-start timeout:** First request after deployment takes longer (MCP connections, Genie space warm-up). The platform gateway times out.
   - Fix: Retry the query — subsequent requests use cached MCP connections.

3. **Backend process crash:** App reports RUNNING but backend died during request handling.
   - Fix: Restart the app: `databricks apps stop <app-name> && databricks apps start <app-name>`, then redeploy if crash persists.

**Diagnosis:** Invoke directly with curl to see the actual error:

```bash
curl -s --noproxy '*' --max-time 120 -X POST \
  "https://<app-url>/invocations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(databricks auth token | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"access_token\"])')" \
  -d '{"input": [{"role": "user", "content": "test"}], "custom_inputs": {"persona": "manager"}}'
```

### "Backend proxy request failed: All connection attempts failed"

**Symptom:** Curl returns `{"detail":"Backend proxy request failed: All connection attempts failed"}` while app status shows RUNNING.

**Cause:** The backend process crashed after initial startup. The platform reports the compute as active, but the Python process (uvicorn) is no longer listening.

**Fix:** Stop and restart the app:

```bash
databricks apps stop <app-name>
databricks apps start <app-name>
```

If it recurs, check for import errors or startup crashes in the wheel (e.g., missing dependencies, incompatible SDK versions).

### Genie agent returns "permission denied" or "table does not exist"

**Symptom:** The orchestrator routes correctly to a Genie agent, but the response says the app lacks permission to query the underlying table.

**Cause:** The app's service principal does not have `SELECT` access to the tables referenced by the Genie space.

**Fix:**

1. Run the grant script:
   ```bash
   make grant-runtime-permissions TARGET=dev APP_NAME=multiagent-app-dev
   ```

2. Or grant manually in a SQL editor:
   ```sql
   GRANT USE CATALOG ON CATALOG <catalog> TO `<app-service-principal-name>`;
   GRANT USE SCHEMA ON SCHEMA <catalog>.<schema> TO `<app-service-principal-name>`;
   GRANT SELECT ON TABLE <catalog>.<schema>.<table> TO `<app-service-principal-name>`;
   ```

   The app service principal name is in the format `app-XXXXX <app-name>` (visible via `databricks apps get <app-name>`).

### Genie agent "unavailable" — missing resource grant

**Symptom:** Response says the agent is unavailable or lacks access to the Genie space.

**Cause:** The Genie space is not registered as an app resource with `CAN_RUN` permission.

**Fix:**

```bash
databricks apps update <app-name> --json '{
  "resources": [
    {"name": "genie_space", "genie_space": {"name": "Genie Agent", "space_id": "<space-id>", "permission": "CAN_RUN"}}
  ]
}'
```

Also update `targets/<target>.yml` with the space ID variable and `resources/multiagent_app.yml` with the resource declaration for future deploys.

### Terraform registry unreachable during `bundle deploy`

**Symptom:** `Error: terraform init: exit status 1 — Could not retrieve the list of available versions for provider databricks/databricks: could not connect to registry.terraform.io`

**Cause:** Network/VPN/firewall blocking access to `registry.terraform.io`, often an IPv6 routing issue.

**Fix:** Use the fallback import/deploy workflow:

```bash
make build-app-source
make import TARGET=dev
make deploy TARGET=dev APP_NAME=multiagent-app-dev
```

Or use `make redeploy` which has built-in fallback logic.

The fallback only deploys application source. It does not replace a failed bundle apply for app resource grants. If the bundle failed before applying `resources/multiagent_app.yml`, restore Terraform registry connectivity and rerun `databricks bundle deploy`; otherwise the app may run without its Lakebase or secret resource permissions.

### Terraform provider crash during `bundle deploy`

**Symptom:** `Error: terraform apply: exit status 1 — Error: Plugin did not respond` with a stack trace from `terraform-provider-databricks`.

**Cause:** The Terraform provider binary crashed during resource apply. This is distinct from registry unreachability — the provider was downloaded but failed at runtime.

**Impact:** When `bundle deploy` fails this way, app-level configuration (env vars, resource grants) defined in `resources/multiagent_app.yml` is **not applied**. The app's `config.env` will be `null` and resource grants may be missing.

**Fix:**

1. Use `make redeploy` — its `bundle-deploy-optional` step tolerates the failure and falls through to import/deploy.
2. Verify env vars are present in `.databricks_app_source/app.yml` — the launcher reads them at startup.
3. Restore resource grants manually if needed:
   ```bash
   # Restore Genie space resources
   databricks apps update <app-name> --json '{
     "resources": [
       {"name": "sales_genie_space", "genie_space": {"name": "Sales Analysis Agent", "space_id": "<id>", "permission": "CAN_RUN"}}
     ],
     "user_api_scopes": ["sql"]
   }'
   # Re-run permission grants
   make grant-runtime-permissions TARGET=dev APP_NAME=multiagent-app-dev
   ```
4. Note: the Databricks Apps API does not currently expose all `postgres` resource updates through `apps update`; apply the Lakebase resource grant and secret resource through `databricks bundle deploy`. If Terraform registry access is unavailable, restore the network path before applying permissions rather than silently relying on OAuth.

### Missing env vars after SNAPSHOT deploy

**Symptom:** App is RUNNING but tools fail with auth errors, missing config, or unexpected defaults. `databricks apps get <app-name>` shows `config.env` as `null` or empty.

**Cause:** Databricks Apps SNAPSHOT-mode deploys do not inject env vars defined in the source `app.yml` at the platform level. The `config` field on the app API remains empty.

**Fix:** The `launcher.py` in `.databricks_app_source/` contains `_load_app_yml_env()` which reads env vars from `app.yml` at startup and injects them into the process environment (without overriding existing vars). Ensure:

1. All required env vars are listed in `.databricks_app_source/app.yml` under the `env:` key.
2. The launcher is up to date (contains `_load_app_yml_env`).
3. After editing `app.yml`, re-import and redeploy:
   ```bash
   make import TARGET=dev APP_NAME=multiagent-app-dev
   make deploy TARGET=dev APP_NAME=multiagent-app-dev
   ```

### Lakebase ODS agent authentication failure

**Symptom:** `password authentication failed for user 'multiagent_svc'` or `password authentication failed for user 'databricks'`.

**Cause:** One of:
- SCRAM password mismatch: the `LAKEBASE_PG_PASSWORD` value doesn't match the Lakebase role's password.
- OAuth user mismatch: `pg_user` in the subagent config doesn't match a valid Lakebase OAuth role.
- Secret resource missing: the app was deployed without the `multiagent_app` secret grant, so `LAKEBASE_PG_PASSWORD` is absent.
- SDK API change: `Config.authenticate()` signature changed from `authenticate(headers_dict)` to `authenticate() -> dict`.

**Fix (OAuth — recommended):**

1. Verify the app SP has an OAuth role in Lakebase:
   ```bash
   databricks postgres list-roles "projects/<project>/branches/<branch>" --profile DEFAULT
   ```
   Look for a role with `auth_method: LAKEBASE_OAUTH_V1` and `identity_type: SERVICE_PRINCIPAL` — note its `postgres_role` value (the SP client ID).

2. Set `pg_user` in `src/backend/domain/subagents.<target>.json` to the SP's `postgres_role` value (e.g., `da6ab9ef-2c0f-4f9b-9950-b618b9f4fede`).

3. Remove the secret-backed `LAKEBASE_PG_PASSWORD` reference only if OAuth-only operation is intentional; otherwise retain the secret and verify the app resource grant.

4. Ensure `_get_lakebase_token()` in `orchestrator_service.py` calls `ws_client.config.authenticate()` (no arguments, returns dict).

5. Rebuild and redeploy.

**Fix (SCRAM password):**

If you prefer SCRAM auth, reset the password via the Lakebase CLI:

```bash
# Delete and recreate the role
databricks postgres delete-role "projects/<project>/branches/<branch>/roles/<role-id>"
databricks postgres create-role "projects/<project>/branches/<branch>" \
  --role-id "<role-id>" \
  --json '{"spec": {"auth_method": "PG_PASSWORD_SCRAM_SHA_256", "postgres_role": "<pg_user>"}}'
```

Note: the `password` field is not currently accepted by the CLI `create-role` command; password must be set through a direct PG session from within the Databricks VPC. The Lakebase PG endpoint is not reachable from local machines.

**Secret setup:**

```bash
databricks secrets create-scope multiagent_app --profile PROFILE
databricks secrets put-secret multiagent_app lakebase_pg_password --profile PROFILE
databricks secrets list-secrets multiagent_app --profile PROFILE
```

The `put-secret` command prompts for the value. Do not put the password in shell history, Git, bundle variables, or chat. Confirm the app resource includes `permission: READ` for this secret and rebuild/redeploy after changing the reference.

**Lakebase role management commands:**

```bash
# List projects
databricks postgres list-projects --profile DEFAULT
# List branches
databricks postgres list-branches "projects/<project>" --profile DEFAULT
# List endpoints
databricks postgres list-endpoints "projects/<project>/branches/<branch>" --profile DEFAULT
# List roles
databricks postgres list-roles "projects/<project>/branches/<branch>" --profile DEFAULT
# Get OAuth credential token (for testing)
databricks postgres generate-database-credential --json '{"endpoint": "projects/<project>/branches/<branch>/endpoints/<endpoint>"}' --profile DEFAULT
```

### Vector Search index "table does not exist" during setup

**Symptom:** `setup-flink-support-rag` or similar script fails with `Table ... does not exist` when creating the Delta Sync index.

**Cause:** The source table was created without Change Data Feed enabled, which Delta Sync indexes require.

**Fix:** Enable CDF on the source table:

```sql
ALTER TABLE <catalog>.<schema>.<table> SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

The setup scripts handle this automatically on re-run.
