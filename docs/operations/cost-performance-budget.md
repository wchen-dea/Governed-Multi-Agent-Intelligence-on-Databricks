# Cost and Performance Budget

Define latency, throughput, and cost constraints for safe operation at scale.

## Purpose

Create measurable operating budgets and escalation thresholds for runtime cost and performance.

## Performance Targets

- Interactive response target: optimized for guardrail-finalized streaming UX
- Track both first-byte and full-response latency for invoke and stream modes
- Preflight startup target: server readiness and invocation checks must pass in local validation
- Tool route health: MCP/tool failures should degrade gracefully when possible

Recommended request-latency SLOs (per environment profile):

- `stream.first_delta_latency_ms`: p50 and p95
- `stream.full_response_latency_ms`: p50 and p95
- `invoke.full_response_latency_ms`: p50 and p95
- `mcp.connect_latency_ms`: p50 and p95
- `mcp.unavailable_ratio`: percentage of requests with MCP unavailability

Default operational targets should be set by environment (`dev`, `qa`, `stg`, `prd`) and reviewed at release gates.

## Cost Drivers

- LLM token usage for orchestrator and tool calls
- External serving endpoint invocations
- Message bus backend transport and persistence costs
- Evaluation simulation and scorer usage in CI
- Worker/process fan-out and per-worker memory overhead
- MCP health-check probe frequency and timeout configuration

## Budget Controls

- Use route selection discipline to avoid unnecessary tool fan-out.
- Keep policy denials and retries visible via lifecycle metrics.
- Tune evaluation suite size by release tier.
- Apply fallback behavior for unavailable non-critical transports.

Runtime tuning controls in this repository:

- Process tuning:
  - `BACKEND_UVICORN_WORKERS`
- Message bus async path:
  - `MESSAGE_BUS_ASYNC`
  - `MESSAGE_BUS_ASYNC_QUEUE_SIZE`
  - `MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS`
- MCP latency and cache tuning:
  - `MCP_CONNECT_TIMEOUT_SECONDS`
  - `MCP_LIST_TOOLS_TIMEOUT_SECONDS` (default `30`, was `10`): pre-flight `list_tools()`
    probe timeout used to decide whether a tool is reported "unavailable" to the model
    before any real turn runs. Too tight a value causes false "please enable this agent"
    responses when a Genie space is slow/cold but would have succeeded on a real query.
  - `MCP_HEALTH_TTL_SECONDS`
  - `MCP_HEALTH_FAILURE_TTL_SECONDS`
  - `MCP_SESSION_TIMEOUT_SECONDS` (default `45`): read timeout for the MCP `ClientSession`
    used on every agent turn (not just the pre-flight health check). The underlying SDK
    defaults this to `20` seconds if unset, which can be too tight for a slow/cold Genie
    space and surfaces as an uncaught `McpError` mid-turn instead of a graceful
    "unavailable" degradation. Raise this if composite/multi-Genie queries intermittently
    fail with `McpError: Timed out while waiting for response to ClientRequest`.
- Orchestrator setup efficiency:
  - `ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE`

Tuning guardrails:

- Change one control family at a time and measure before/after.
- Keep `MESSAGE_BUS_FAIL_OPEN=true` unless strict fail-closed behavior is required.
- Increase worker counts only when CPU saturation is observed and memory headroom is confirmed.

## Monitoring Signals

- Request success/failure rate
- Tool invocation count and failure ratio
- Guardrail block ratio
- Evaluation pass/fail trend
- Stream first-delta latency p50/p95
- Invoke full-response latency p50/p95
- MCP connect/probe timeout counts
- Async message-bus queue pressure (drops/full events)

Recommended metric dimensions:

- environment (`dev`, `qa`, `stg`, `prd`)
- mode (`invoke`, `stream`)
- auth path (`app`, `obo`)
- tool route (`genie`, `mcp`, `serving_endpoint`, `app`)

## Release Checks

- Verify KPI gates before deployment.
- Review performance and error trends after deployment.

Performance release checklist:

1. Capture baseline for p50/p95 latency, error rate, and resource usage.
2. Apply one optimization or tuning change.
3. Re-run identical workload and compare deltas.
4. Promote only when latency/cost improves without safety/governance regression.
5. Record final settings in runbook and target config notes.

Suggested optimization validation order:

1. Stream pipeline changes
2. MCP parallel checks and TTL cache tuning
3. Async message-bus mode
4. Instruction/setup cache tuning
5. Worker/process tuning

## Related Documents

- ../quality/evaluation-spec.md
- operations-runbook.md
- ../architecture/high-level-architecture.md
