# React UI (Primary Frontend)

This folder provides the primary TypeScript and React frontend used by the app runtime.

## Current Scope

- Chat request and streaming response rendering through backend `/invocations`.
- Session commands:
  - `/token <databricks_access_token>`
  - `/clear-token`
- Persona assignment through the visible dropdown; forwarded via `custom_inputs.persona`.
- Forwarded token header support (`x-forwarded-access-token` by default).
- For direct non-interactive Databricks Apps invocation tests, use `Authorization: Bearer <token>`.
- Session status footer and source/tool hint footer.
- Incremental text rendering with accessible live-region updates while a response streams.
- Visible persona selector and App identity versus Hybrid OBO status.
- User-selectable homepage background theme (deep ocean, sky blue, deep sky blue), persisted in `localStorage`.
- Collapsible per-response run context showing tools, sources, guardrail state, and truncation.
- HITL starter tab with a discovery query for stores with strong revenue and declining CDI, including an approval pause before operational dispatch.
- Safe rendering for supported headings, tables, and citation markers; model HTML is not executed.
- Explicit streaming states for blocked, unavailable, error, and truncated responses.

## Run Locally

For the app as a whole, use the project-root commands from the top-level Makefile instead of manually invoking the frontend alone when you want the same build and deploy flow used by the Databricks app automation.

### Frontend-only local development

1. Install dependencies.

```bash
cd src/aiweb
npm install
```

2. Configure environment.

```bash
cp .env.example .env
```

3. Start the dev server.

```bash
npm run dev
```

### Project-level app workflow

```bash
make help
make build-app-source
make import
make deploy
make health
make smoke
```

These targets build the packaged app source, upload it to the Databricks app workspace, deploy the app, and validate the generated UI route and `/invocations` contract.

## Build

```bash
cd src/aiweb
npm run build
```

The app bundle is later assembled into the wheel source payload via the project-root `make build-app-source` flow, which packages the React UI into the backend app source directory used by Databricks Apps.

## Browser Tests

The Playwright suite uses mocked SSE responses so UI behavior can be validated without a Databricks deployment.

```bash
cd src/aiweb
npm run test:e2e
```

Coverage includes desktop and mobile layouts, incremental streaming, governance context, blocked responses, and OBO session state.

## Notes

- Default backend URL for local frontend-only development is `http://localhost:8000/invocations`.
- The built React UI is bundled into the backend wheel (`src/aiserver/static/`, produced by `prepare_app_source.py`) and served in-process by `src/aiserver/api/server.py` — same origin, no separate proxy process.
- Project automation lives in the root Makefile; use `make help` for the current command set and `make redeploy` for the end-to-end refresh path.
