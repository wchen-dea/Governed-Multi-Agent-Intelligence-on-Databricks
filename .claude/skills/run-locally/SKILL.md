---
name: run-locally
description: "Run and validate the app locally. Use when: starting backend/frontend, testing invocations, or troubleshooting local runtime issues."
---

# Run Locally

## Start Modes

Full local app (backend + Chainlit UI):

```bash
uv run runtime-serve-app
```

Backend only:

```bash
uv run runtime-serve-backend --reload
uv run runtime-serve-backend --port 8001
uv run runtime-serve-backend --workers 4
```

## Validate Runtime

```bash
uv run runtime-preflight
uv run assistant-evaluate
```

## Test API

Non-streaming:

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"hi"}]}'
```

Streaming:

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"hi"}],"stream":true}'
```

## Troubleshooting

- Port conflict: change `--port` or stop existing process.
- Auth errors: run `uv run assistant-bootstrap` and verify profile.
- Missing deps: run `uv sync`.
- Experiment errors: confirm `.env` contains valid `MLFLOW_EXPERIMENT_ID` and `MLFLOW_TRACKING_URI`.
