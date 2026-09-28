---
description: "Building the React + TypeScript frontend (src/aiweb) and its contract with the FastAPI backend (src/aiserver)."
applyTo: "src/aiweb/**"
---

# React + TypeScript Frontend (`src/aiweb`)

## Introduction

`src/aiweb` is the primary browser client for this platform. It is a **React 18 + TypeScript + Vite** single-page app with **no router, no state-management library, and no CSS framework** — deliberately. All UI state lives in React hooks inside `src/App.tsx`, and all styling lives in a single `src/styles.css`.

It talks to a **FastAPI** backend in `src/aiserver`. That backend is not hand-rolled: `src/aiserver/api/server.py` obtains its `app` from MLflow's `AgentServer("ResponsesAgent", enable_chat_proxy=True)`, then attaches this project's own routes and static-file mounts to it.

The two tiers ship as **one artifact**. `make build-app-source` builds the Vite bundle and packages it into `src/aiserver/static/`, which FastAPI serves in-process (`/assets` mount, `/` index, `/{path:path}` SPA fallback). There is **no reverse proxy and no separate frontend server in production** — the browser, the API, and the static assets are all the same origin.

Treat that same-origin design as an invariant. It is why no CORS middleware exists anywhere in `src/aiserver`, and why `VITE_API_PROXY` defaults to the relative path `/invocations`.

General React + TypeScript streaming conventions live in the user-level
`react-typescript-streaming-frontend` instructions. This file covers only what is
specific to this repository.

## Module Boundaries

Respect these; do not collapse them into `App.tsx`.

| File | Responsibility |
| --- | --- |
| `src/main.tsx` | React root mount. Almost never changes. |
| `src/App.tsx` | All UI, hooks, and session state. |
| `src/api.ts` | Transport only — `fetch`, SSE reading, request shaping. |
| `src/stream.ts` | **Pure functions** that reduce SSE events into tool/source hints and governance metadata. No I/O, no React. |
| `src/commands.ts` | Slash-command parsing (`/token`, `/clear-token`) and token masking. |
| `src/config.ts` | Single source of truth for `import.meta.env` reads. |
| `src/types.ts` | Shared contract types mirroring the backend envelope. |

`config.ts` is the sole reader of `import.meta.env`, and `stream.ts` must stay
pure — both are load-bearing here specifically because `App.tsx` is large.

## Backend Contract

Primary call: `POST /invocations`, streaming.

```jsonc
{
  "input": [{ "role": "user", "content": "..." }],   // full history, then the new turn
  "stream": true,
  "context": { "conversation_id": "<stable per conversation>" },
  "custom_inputs": { "persona": "store-manager" }     // omitted when no persona is selected
}
```

Other routes owned by this repo: `GET /health`, `POST /approval-decisions`, `GET /approval-decisions/{request_id}`, `GET /delegations/{task_id}`.

Rules when touching the wire format:

- **Persona travels in `custom_inputs.persona`** — not a header, not a query param. Valid values are constrained by `DEFINED_AGENT_PERSONAS` in `config.ts`; legacy names are remapped there, so extend that map rather than special-casing at call sites.
- **The OBO token travels in the `x-forwarded-access-token` header**, whose name is configurable via `settings.forwardedAccessTokenHeader`. It is held in memory for the session only — never persist it to `localStorage`, never log it, and mask it with `maskToken` before it reaches the transcript.
- **Derive sibling endpoints from `settings.backendUrl`** the way `submitApprovalDecision` does (strip the trailing `/invocations`). Do not introduce a second base-URL setting.
- **Any change to the response envelope must be mirrored in `types.ts`** (`GovernanceMetadata`, `HumanApprovalState`, `OpenAIAgentRunMetadata`, `RoutePlan`) and in `src/aiserver/contracts/responses.py`. These two files are a matched pair.

## Streaming

The response body is SSE parsed by hand in `api.ts`. The generic parser rules
(partial-line buffering, tolerating bad frames, de-duplication, `AbortController`)
are covered by the user-level instructions. Repo-specific points:

- The de-duplication guard is the `seenEvents` set **plus** the
  `fullText.endsWith(delta)` check. This backend replays events; dropping either
  guard causes visibly doubled text.
- Publish the abort controller through `onRequestController` — it backs both the
  `settings.timeoutSeconds` timeout and the user-facing cancel button.
- Stream text through `onTextDelta`, and keep the terminal states `blocked`,
  `unavailable`, `error`, and `truncated` visually distinct.
- Model output renders as a restricted subset: headings, tables, citation markers.

## Local Development

Same-origin (matches production; preferred for anything involving auth, SPA fallback, or static assets):

```bash
make build-app-source
AIWEB_DIST_DIR="$PWD/src/aiweb/dist" uv run runtime-serve-app --port 8000
```

Split mode (fast HMR on `:5173`, backend on `:8000`):

```bash
uv run runtime-serve-backend --reload --port 8000
cd src/aiweb && npm run dev
```

Split mode is cross-origin. If the browser blocks the call, **add a `server.proxy` entry to `vite.config.ts`** so the app keeps issuing same-origin relative requests. Do **not** add `CORSMiddleware` to the backend to work around it — that would weaken the deployed posture to fix a dev-only problem.

`.env` is local-only and must never hold production secrets.

## Checks

```bash
cd src/aiweb
npm run build      # tsc -b && vite build — type errors fail the build
npm run lint       # prettier --check
npm run test:e2e   # Playwright, desktop + mobile projects
```

Playwright starts its own dev server on `127.0.0.1:5173` and **mocks the SSE responses**, so the suite runs with no Databricks deployment and no live backend. New streaming, governance, or approval behavior belongs in `tests/e2e/` with a mocked event sequence.

Run `npm run format` before committing; `npm run lint` is check-only and will fail CI on unformatted files.

## Conventions

- Add dependencies only with a clear justification — the runtime dependency set is intentionally just `react` and `react-dom`.
- The built `dist/` and `src/aiserver/static/` are **generated**. Edit sources and rebuild; never hand-patch build output.
