# ADR 0009: Route Orchestrator LLM Traffic through Unity AI Gateway

## Status

Accepted

## Context

The orchestrator calls Databricks-hosted foundation models (default: `databricks-gpt-5-6-luna`) via `AsyncDatabricksOpenAI`. By default these calls go directly to model serving endpoints, which provides basic usage tracking but no centralized rate-limiting, PII controls, inference logging, or platform-level guardrails.

Unity AI Gateway adds a governance layer on top of serving endpoints with configurable rate limits, PII detection and masking, safety filters, inference table capture, and usage tracking — all managed through endpoint configuration rather than application code.

The project already has application-level guardrails (ADR 0005) for evidence requirements and response safety. AI Gateway provides a complementary, platform-managed defense layer that operates independently of application logic.

## Decision

Support Unity AI Gateway as an opt-in routing layer for all orchestrator LLM calls, with routing modes resolved in this precedence order:

1. **Explicit base URL** (`DATABRICKS_OPENAI_BASE_URL`) — redirects `AsyncDatabricksOpenAI` to any gateway-fronted endpoint URL. Wins when set.
2. **Native AI Gateway V2** (`DATABRICKS_USE_AI_GATEWAY_NATIVE_API=true`) — auto-detects the workspace's Unity AI Gateway and routes through its native OpenAI-compatible API (`<host>/ai-gateway/openai/v1`).
3. **MLflow-compatible AI Gateway V2** (`DATABRICKS_USE_AI_GATEWAY=true`) — auto-detects the gateway and routes through its MLflow-compatible API (`<host>/ai-gateway/mlflow/v1`).

When none are set (all default off/empty), calls route directly to the legacy `/serving-endpoints/<model>/invocations` path resolved by model name.

Model name strings (for example `databricks-claude-sonnet-5`) are unchanged across all modes. The Unity Catalog `system.ai.<model>` name visible on each served entity (for example `system.ai.databricks-claude-sonnet-5`) identifies the registered model backing an endpoint for governance and lineage — it is not a valid `model` value for chat/responses calls, so it is never substituted into routing config.

A companion timeout override (`DATABRICKS_OPENAI_TIMEOUT_SECONDS`) accommodates gateway-introduced latency.

All four values are declared as Databricks Asset Bundle variables and propagated per target environment (`dev`, `qa`, `stg`, `prd`), allowing each environment to independently choose a routing mode. All targets default to the legacy direct-serving-endpoint path until AI Gateway is provisioned for the routed models.

### Gateway capabilities leveraged

| Capability | Purpose |
|------------|---------|
| Rate limits (calls/min, tokens/min) | Protect serving endpoints from burst traffic and control cost |
| PII detection/masking (input + output) | Platform-level sensitive data handling before application guardrails |
| Safety filters | Block harmful content at the platform layer |
| Inference tables | Capture request/response payloads to Unity Catalog for audit and evaluation |
| Usage tracking | Centralized token and call metering |

### Relationship to application guardrails

AI Gateway guardrails and application guardrails (ADR 0005) are complementary:

- AI Gateway operates at the **platform transport layer** — PII masking, safety, rate limits apply to raw LLM requests/responses before the application sees them.
- Application guardrails operate at the **domain layer** — evidence requirements, source attribution, and policy-aware routing apply to the orchestrated multi-agent output.

Neither replaces the other. AI Gateway catches broad platform-level violations; application guardrails enforce domain-specific governance.

### Available gateway endpoints in dev workspace

Endpoints with AI Gateway enabled: `kc-ai-assistant-v1` (full guardrails, PII, rate limits, inference tables), plus several `agents_dt_analytics-*` agent endpoints.

Foundation model endpoints (e.g., `databricks-claude-sonnet-4`, `databricks-gpt-5-6-luna`) currently have no AI Gateway configuration at all (`ai_gateway` is unset) — operators must configure gateway settings via the Databricks UI or API before enabling `DATABRICKS_USE_AI_GATEWAY`/`DATABRICKS_USE_AI_GATEWAY_NATIVE_API` for those models.

## Alternatives Considered

- **Hardcode a gateway URL per environment.** Rejected because it couples deployment config to application code and prevents quick toggling.
- **Wrap every LLM call with an explicit gateway client.** Rejected because `AsyncDatabricksOpenAI` already supports `base_url` override — a wrapper adds complexity with no benefit.
- **Rely solely on application-level guardrails.** Rejected because platform-level PII masking and rate limiting are better handled before traffic reaches application code.
- **Always require AI Gateway (no opt-out).** Rejected because local development and early-stage environments benefit from direct model access without gateway infrastructure.

## Consequences

### Positive

- Adds platform-managed PII, safety, and rate-limit controls without application code changes.
- Inference table capture enables centralized audit and offline evaluation via Unity Catalog.
- Per-environment opt-in keeps local and early-stage development friction-free.
- Complements existing application guardrails for defense-in-depth.

### Trade-offs

- Gateway routing adds network latency; timeout tuning may be needed per environment.
- Gateway guardrail behavior (e.g., PII masking) can alter LLM input/output in ways the application must tolerate.
- Operators must provision and configure the gateway endpoint separately from the application deployment.

## Implementation Notes

- Client construction with routing precedence: [src/aiserver/api/invocations.py](../../src/aiserver/api/invocations.py) (`_build_openai_client`)
- Settings: [src/aiserver/config/settings.py](../../src/aiserver/config/settings.py) (`openai_base_url`, `openai_use_ai_gateway`, `openai_use_ai_gateway_native_api`, `openai_timeout_seconds`)
- Bundle variables: [databricks.yml](../../databricks.yml) (`openai_base_url`, `openai_use_ai_gateway`, `openai_use_ai_gateway_native_api`, `openai_timeout_seconds`)
- Per-target values: [targets/dev.yml](../../targets/dev.yml) (currently all routing overrides off — direct to legacy model serving)
