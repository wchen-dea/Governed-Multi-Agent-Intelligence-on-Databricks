# React UI (Primary Frontend)

This folder provides the primary TypeScript and React frontend used by the app runtime.

## Current Scope

- Chat request and streaming response rendering through backend `/invocations`.
- Session commands:
  - `/token <databricks_access_token>`
  - `/clear-token`
  - `/persona <persona>`
  - `/clear-persona`
- Persona forwarding via `custom_inputs.persona`.
- Forwarded token header support (`x-forwarded-access-token` by default).
- For direct non-interactive Databricks Apps invocation tests, use `Authorization: Bearer <token>`.
- Session status footer and source/tool hint footer.
- Incremental text rendering with accessible live-region updates while a response streams.
- Visible persona selector and App identity versus Hybrid OBO status.
- User-selectable homepage background theme (deep ocean, sky blue, deep sky blue), persisted in `localStorage`.
- Collapsible per-response run context showing tools, sources, guardrail state, and truncation.
- Safe rendering for supported headings, tables, and citation markers; model HTML is not executed.
- Explicit streaming states for blocked, unavailable, error, and truncated responses.

## Run Locally

1. Install dependencies.

```bash
cd src/reactui
npm install
```

2. Configure environment.

```bash
cp .env.example .env
```

3. Start dev server.

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Browser Tests

The Playwright suite uses mocked SSE responses so UI behavior can be validated without a Databricks deployment.

```bash
npm run test:e2e
```

Coverage includes desktop and mobile layouts, incremental streaming, governance context, blocked responses, and OBO session state.

## Notes

- Default backend URL is `http://localhost:8000/invocations`.
- The React UI is served by the app runtime through `src/scripts/react_ui_server.py`.
- The legacy Chainlit implementation remains available under `src/frontend/` for fallback and compatibility checks.