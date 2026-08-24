# ADR 0009: Route Orchestrator LLM Traffic through Unity AI Gateway

## Status

Accepted

## Context

The orchestrator calls Databricks-hosted foundation models (default: `databricks-gpt-5-6-luna`) via `AsyncDatabricksOpenAI`. By default these calls go directly to model serving endpoints, which provides basic usage tracking but no centralized rate-limiting, PII controls, inference logging, or platform-level guardrails.

Unity AI Gateway adds a governance layer on top of serving endpoints with configurable rate limits, PII detection and masking, safety filters, inference table capture, and usage tracking — all managed through endpoint configuration rather than application code.

The project already has application-level guardrails (ADR 0005) for evidence requirements and response safety. AI Gateway provides a complementary, platform-managed defense layer that operates independently of application logic.

## Decision

Support Unity AI Gateway as an opt-in routing layer for all orchestrator LLM calls.

The integration uses a single environment variable (`DATABRICKS_OPENAI_BASE_URL`) to redirect the `AsyncDatabricksOpenAI` client to a gateway-fronted endpoint. When the variable is empty (default), calls route directly to the model serving endpoint resolved by model name. When set, all orchestrator LLM traffic flows through the specified gateway URL.

A companion timeout override (`DATABRICKS_OPENAI_TIMEOUT_SECONDS`) accommodates gateway-introduced latency.

Both values are declared as Databricks Asset Bundle variables and propagated per target environment (`dev`, `qa`, `stg`, `prod`), allowing each environment to independently enable or bypass the gateway.

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

Foundation model endpoints (e.g., `databricks-claude-sonnet-4`, `databricks-gpt-5-6-luna`) have basic `usage_tracking` but no custom AI Gateway config — operators can configure these via the Databricks UI.

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

- Client construction with base URL override: [src/backend/api/handlers.py](../../src/backend/api/handlers.py) (`_build_openai_client`)
- Settings: [src/backend/shared/settings.py](../../src/backend/shared/settings.py) (`openai_base_url`, `openai_timeout_seconds`)
- Bundle variables: [databricks.yml](../../databricks.yml) (`openai_base_url`, `openai_timeout_seconds`)
- Per-target values: [targets/dev.yml](../../targets/dev.yml) (currently `openai_base_url=""` — direct to model serving)
