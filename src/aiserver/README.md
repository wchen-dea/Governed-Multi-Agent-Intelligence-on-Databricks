# Backend README

## Overview

The backend hosts the multi-agent runtime using MLflow Agent Server.

Core responsibilities:

- accept invoke/stream requests,
- build runtime auth context (app and OBO),
- enforce request-time policy and response guardrails,
- route across subagent tools and MCP integrations,
- publish lifecycle events to configurable message bus backends.

Primary entrypoint:

- `src/backend/api/server.py`

## Structure

- `src/backend/api/`
  - `server.py`: AgentServer bootstrap and app startup.
  - `handlers.py`: `@invoke` and `@stream` request handlers.
  - `dependencies.py`: dependency wiring for services.
- `src/backend/services/`
  - `orchestrator_service.py`: tool construction and orchestration behavior.
  - `runtime_auth_service.py`: request-scoped auth context and policy-aware availability.
  - `policy_service.py`: deterministic request-time policy checks.
  - `guardrails_service.py`: deterministic response-time guardrail checks.
  - `message_bus.py`: structured logging, noop, Kafka, RabbitMQ, UC table backends.
  - `memory_service.py`: no-op and Lakebase-backed conversation/persona memory backends.
  - `interfaces.py`: service protocols for dependency injection.

Supported subagent types:
  - `genie`: Genie Agent via MCP protocol.
  - `serving_endpoint`: Databricks Model Serving via Responses API.
  - `app`: Databricks App via Responses API.
  - `mcp`: AI Search or generic MCP route.
  - `lakebase`: Lakebase PostgreSQL via psycopg2 with OAuth credentials.
- `src/backend/domain/`
  - `subagent_config.py`: typed config model and validation.
  - `subagents.<target>.json`: environment-specific subagent/tool registry config.
- `src/backend/shared/`
  - `settings.py`: typed runtime settings.
  - `runtime_utils.py`: auth/request helper utilities.
  - `request_utils.py`: request normalization helpers.
  - `logging_config.py`: backend logging configuration.
  - `lakebase_client.py`: shared OAuth/psycopg2 connection helper for Lakebase Postgres.
- `src/backend/evaluate_agent.py`: release-gate evaluation runner.

## Local Run

Start backend only:

```bash
uv run runtime-serve-backend --reload
```

Backend health and root probes:

- `GET /health`
- `GET /`

Invoke endpoint:

- `POST /invocations`

## For New Developers

Use this workflow when iterating on orchestration logic:

1. Start backend: `uv run runtime-serve-backend --reload`
2. Modify handlers/services under `src/backend/api/` and `src/backend/services/`
3. Run targeted tests: `uv run pytest -q`

Most common edit locations:

- `src/backend/api/handlers.py`: invoke/stream flow and guardrail enforcement.
- `src/backend/services/runtime_auth_service.py`: auth context and tool availability.
- `src/backend/services/policy_service.py`: deterministic policy checks.
- `src/backend/services/orchestrator_service.py`: tool and MCP orchestration behavior.

Tip:

- Keep `src/backend/domain/subagents.<target>.json` and runtime behavior aligned when adding/changing tools.

## Key Environment Variables

General:

- `ORCHESTRATOR_MODEL`: orchestrator model name.
- `DATABRICKS_OPENAI_BASE_URL`: optional Databricks OpenAI base URL override (for example Unity AI Gateway URL).
- `DATABRICKS_OPENAI_TIMEOUT_SECONDS`: optional Databricks OpenAI timeout in seconds; `0` keeps SDK defaults.
- `BACKEND_LOG_LEVEL`, `BACKEND_LOG_FORMAT`, `BACKEND_LOG_DATE_FORMAT`.

Message bus:

- `MESSAGE_BUS_BACKEND`: `structured_logging` (default), `noop`, `kafka`, `rabbitmq`, `uc_table`.
- `MESSAGE_BUS_TOPIC`
- `MESSAGE_BUS_FAIL_OPEN`
- `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_CLIENT_ID`
- `RABBITMQ_URL`
- `UC_AUDIT_WAREHOUSE_ID`, `UC_AUDIT_CATALOG`, `UC_AUDIT_SCHEMA`, `UC_AUDIT_TABLE`

Conversation memory (disabled by default; persists conversation content when enabled — review data classification before turning it on):

- `MEMORY_BACKEND`: `disabled` (default) or `lakebase`.
- `MEMORY_PROJECT_ID`, `MEMORY_BRANCH_ID`, `MEMORY_ENDPOINT_ID`, `MEMORY_DATABASE`, `MEMORY_PG_HOST`, `MEMORY_PG_USER`
- `MEMORY_CONVERSATION_TABLE` (default `agent_memory_conversations`), `MEMORY_PREFERENCE_TABLE` (default `agent_memory_preferences`)
- `MEMORY_MAX_TURNS` (default `20`), `MEMORY_FAIL_OPEN` (default `true`)

Evaluation gate:

- `EVAL_MIN_TOOL_CALL_ACCURACY`
- `EVAL_MIN_AUTH_CORRECTNESS`
- `EVAL_MIN_SAFETY`
- `EVAL_MIN_GROUNDEDNESS`
- `EVAL_REQUIRE_ALL_KPIS`

## Evaluation and Tests

Run tests:

```bash
uv run pytest -q
```

Run evaluation gate:

```bash
uv run assistant-evaluate
```

## For Operators

Use this checklist before and after deployment:

1. Validate config and tests: `uv run pytest -q`
2. Run quality gate: `uv run assistant-evaluate`
3. Confirm backend health endpoint and invocation path
4. Review message-bus and guardrail/policy events in logs or UC sink

Operational focus areas:

- OBO failures: confirm forwarded token presence and permissions.
- Policy/guardrail blocks: inspect deny and block reason codes.
- Message-bus transport: verify selected backend connectivity and fail-open behavior.

## Troubleshooting

- OBO route unavailable:
  - verify `x-forwarded-access-token` is forwarded from frontend.
  - verify user identity has required data permissions.
- Non-interactive Databricks Apps invocation tests:
  - use `Authorization: Bearer <token>` for direct `/invocations` calls.
  - do not rely on `x-forwarded-access-token` in raw curl flows, which can enter OIDC redirect paths.
- Policy or guardrail blocks:
  - inspect backend logs for deny reasons and guardrail reason codes.
  - Genie agents should have `requires_evidence: false` since their output format doesn't include citation markers.
- Message bus backend initialization failure:
  - with `MESSAGE_BUS_FAIL_OPEN=true`, runtime should fall back to structured logging.
  - otherwise fix backend credentials/connectivity for selected transport.
- Reasoning model errors (400):
  - ensure `set_default_openai_api("responses")` in handlers.py, not `"chat_completions"`.

## Setup Scripts

- `uv run assistant-setup-flink`: create Vector Search index from support KB volume for Flink RAG agent.
- `uv run assistant-setup-cdi`: verify CDI materialized view exists and create Genie space.
