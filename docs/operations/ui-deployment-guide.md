# Web UI Delivery Guide

This guide describes the complete delivery path for the React web UI, from local development through the Databricks Apps release artifact.
The [operations runbook](operations-runbook.md) remains authoritative for
app-level deployment, permissions, health checks, and recovery.

## Delivery Model

The UI is a Vite-built React application in `src/aiweb`. It is not deployed as a separate frontend service:

1. Vite compiles the UI into `src/aiweb/dist`.
2. `runtime-build-source` copies that output into `src/aiserver/static`.
3. `uv build --wheel` packages the Python backend and static UI into one wheel.
4. The wheel is placed in `.databricks_app_source/wheels` with `app.yml`.
5. Databricks Apps runs one process. FastAPI serves the UI and `/invocations` from the same origin.

The generated directories `src/aiweb/dist`, `src/aiserver/static`, `.databricks_app_source`, and `dist` are build outputs. Do not edit them directly.

## Prerequisites

Install and authenticate the tools used by the repository:

- Python 3.11 or 3.12 with `uv`
- Node.js and `npm`
- Databricks CLI, `jq`, and a configured Databricks CLI profile for deployment
- Access to the target workspace, app, model/tool resources, and required permissions

From the repository root, install the Python environment and dependencies:

```bash
uv sync
```

Install the UI dependencies when working on the frontend directly:

```bash
cd src/aiweb
npm ci
cd ../..
```

## Local Development

### Frontend and backend separately

Use this mode for fast browser iteration. Start the backend in one terminal:

```bash
uv run runtime-serve-backend --reload --port 8000
```

In another terminal, configure the Vite client to call that backend and start Vite:

```bash
cd src/aiweb
cp .env.example .env
printf '\nVITE_API_PROXY=http://localhost:8000/invocations\n' >> .env
npm run dev
```

Open `http://localhost:5173`. The `.env` file is local-only and must not contain production secrets. The `/token` command accepts a Databricks access token in the browser session for hybrid OBO testing; clear it with `/clear-token` when finished.

For message-bus backends, stream execution tuning, MCP latency controls, and
backend preflight, see the [backend and deployment local operations](operations-runbook.md#local-operations-backend-and-deployment).

The client reads these build-time settings from `src/aiweb/.env`:

- `VITE_API_PROXY`: backend invocation URL; use the deployed same-origin default `/invocations` for the packaged app.
- `VITE_CHAT_GREETING`, `VITE_CHAT_COMPANY_NAME`, and `VITE_CHAT_COMPANY_TAGLINE`: display text.
- `VITE_CHAT_PROXY_TIMEOUT_SECONDS`: browser request deadline.
- `VITE_FORWARDED_ACCESS_TOKEN_HEADER`: forwarded-token header name.
- `VITE_CHAT_ALLOWED_PERSONAS`: comma-separated allowed persona identifiers.

### Full app process

To exercise the same-origin static serving used after packaging, build the UI and run the backend with the generated package assets:

```bash
cd src/aiweb
npm ci
npm run build
cd ../..
AIWEB_DIST_DIR="$PWD/src/aiweb/dist" uv run runtime-serve-app --port 8000
```

Check `http://localhost:8000/` for the React shell and `http://localhost:8000/health` for the service status. This mode confirms the SPA fallback and API are served by one process, but it does not replace the wheel packaging check below.

## Frontend Checks

Run these from `src/aiweb` before creating a release artifact:

```bash
npm ci
npm run lint
npm run build
npm run test:e2e
```

The Playwright tests use mocked SSE responses and do not require a Databricks deployment. If browsers are not installed in a new environment, install the repository's Playwright browser dependency using the Playwright command reported by the test runner, then rerun `npm run test:e2e`.

## Package the Deployable UI

Run the packaging command from the repository root. It installs the locked frontend dependencies, builds the React UI, copies the build into the Python package, builds a fresh wheel, and creates the minimal Databricks Apps source directory:

```bash
make build-app-source TARGET=dev
```

The equivalent canonical runtime command is:

```bash
TARGET=dev uv run runtime-build-source
```

The target controls the environment values synchronized into `.databricks_app_source/app.yml` from `resources/multiagent_app.yml` and `targets/dev.yml`. Use `TARGET=qa`, `TARGET=stg`, or `TARGET=prd` for those environments.

Confirm the package contains the UI before deployment:

```bash
find src/aiweb/dist -maxdepth 2 -type f | sort
find src/aiserver/static -maxdepth 2 -type f | sort
find .databricks_app_source/wheels -maxdepth 1 -type f -name '*.whl' -print
unzip -l .databricks_app_source/wheels/*.whl | grep 'aiserver/static/'
```

Do not manually copy files into `.databricks_app_source` or `src/aiserver/static`; the preparation command owns those transformations. A fresh wheel is generated on every run, and old remote wheel payloads are removed by the import workflow.

## Deploy to Databricks Apps

### Recommended release flow

Set the target-specific app name and profile, then run the full workflow:

```bash
make redeploy TARGET=dev APP_NAME=multiagent-app-dev PROFILE=dev
```

For another environment, change all three values consistently. `make redeploy` performs the following sequence:

1. Build the wheel and bundled React assets.
2. Validate the Databricks Asset Bundle.
3. Attempt the bundle deployment.
4. Import `.databricks_app_source` into the app workspace source path.
5. Deploy an app snapshot from that path.
6. Apply runtime permissions.
7. Verify deployment health and the UI/API smoke path.

The app source snapshot contains the UI and backend together. Existing app service principals are checked and must not change during an update.

### Manual release flow

Use the [standard deployment procedure in the operations runbook](operations-runbook.md#standard-deployment) when inspecting or recovering a release one boundary at a time. It includes the equivalent manual commands for validation, source import, app deployment, and verification.

### Terraform-free fallback

If the bundle deployment fails because the Terraform provider registry is
unavailable, use the [fallback deployment procedure in the operations
runbook](operations-runbook.md#fallback-deployment-procedure). It deploys the
packaged UI and backend but does not apply bundle-managed resources or grants.
Resolve those separately before promoting the release.

## Post-Deployment Verification

Run the standard checks and inspect the app status:

```bash
make health TARGET=dev APP_NAME=multiagent-app-dev PROFILE=dev
make smoke TARGET=dev APP_NAME=multiagent-app-dev PROFILE=dev
make status TARGET=dev APP_NAME=multiagent-app-dev PROFILE=dev
```

Expected health values are:

- `active_deployment.status.state`: `SUCCEEDED`
- `app_status.state`: `RUNNING`
- `compute_status.state`: `ACTIVE` or the platform's running equivalent
- Root response contains `<div id="root"></div>` when the UI is public to the smoke request
- `/invocations` is reachable and does not return `404`

For an authenticated functional check, use a Databricks bearer token without putting it in source control:

```bash
make query-dev TARGET=dev APP_NAME=multiagent-app-dev PROFILE=dev \
  QUERY='top stores by revenue' QUERY_PERSONA=store-manager
```

For governance-specific verification, provide `TOKEN` only through the shell environment and use `make smoke-governance` as documented in the operations runbook.

## Troubleshooting

- **The browser shows the backend JSON status instead of the UI:** run `make build-app-source`; the wheel only contains the UI when Vite has built and the preparation script has copied the assets.
- **The Vite page cannot reach the API:** set `VITE_API_PROXY=http://localhost:8000/invocations` for split local development. The deployed app must use `/invocations`.
- **A deployed update uses old UI code:** rebuild with `make build-app-source`, import the regenerated `.databricks_app_source`, and deploy a new snapshot. `apps deploy` does not rebuild local assets.
- **The app source path is missing:** run `make validate` to derive the bundle workspace path, or use the full `make redeploy` flow so the path is resolved automatically.
- **The app is healthy but the root smoke check is unauthorized:** a `401` or `403` root response is accepted by the structural smoke check; use an authenticated browser/session or invocation check to validate the UI content.
- **The deployment is locked or still in progress:** rerun the workflow; the Make targets wait for stable compute and active-deployment locks before updating.

For Databricks permissions, target configuration, rollback, and incident handling, continue with the [operations runbook](operations-runbook.md).
