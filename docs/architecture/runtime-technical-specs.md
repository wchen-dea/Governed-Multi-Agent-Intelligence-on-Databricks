# Technical Specs

This document summarizes the technical specifications currently implemented in this project.

## 1. Runtime Architecture Specification

- Layered backend architecture is implemented with API, services, domain, and shared layers.
- Request handling supports both invoke and stream flows through MLflow Agent Server handlers.
- Orchestrator agent is assembled at runtime with available tools and healthy MCP servers.
- A deterministic model router selects a configured Databricks model before agent assembly and records the decision in routing lifecycle metadata.
- Frontend runtime is React UI first, with a legacy Chainlit path retained for compatibility.

Primary implementation:

- src/backend/api/handlers.py
- src/backend/api/dependencies.py
- src/backend/services/orchestrator_service.py

### Task-Type Model Routes

| Task type | Default dev model | Examples |
| --- | --- | --- |
| standard | `databricks-gpt-5-6-luna` | product lookups and ordinary conversational requests |
| reasoning | `databricks-gpt-5-6-luna` | appointments, orders, SQL, Flink, streaming, debugging, and troubleshooting |
| synthesis | `databricks-gpt-5-6-luna` | analysis, comparison, executive summaries, recommendations, and plans |

Dev keeps all task classes on the verified balanced model. Promote a task route to another Databricks model only after a successful live invocation and evaluation run for that route.

Set `MODEL_ROUTING_ENABLED=false` to retain `ORCHESTRATOR_MODEL` for every task. Configure individual routes through `MODEL_ROUTING_DEFAULT_MODEL`, `MODEL_ROUTING_REASONING_MODEL`, and `MODEL_ROUTING_QUALITY_MODEL`.

With routing enabled, dev currently resolves standard, reasoning, and synthesis tasks to `databricks-gpt-5-6-luna`. Model-route metadata is not proof of tool-call correctness.
- src/reactui/src/App.tsx
- src/reactui/src/api.ts
- src/scripts/react_ui_server.py

This document is the canonical implementation-fact index for architecture behavior; [API contracts](api-contracts.md), [tool and model registry](tool-and-model-registry.md), and [low-level design](low-level-design.md) remain authoritative for their named concerns.

## 2. Tool Routing Specification

- Subagent configuration is externalized in JSON and validated through typed domain models.
- Supported subagent kinds include genie, serving_endpoint, app, mcp, and lakebase.
- Non-Genie function tools are generated dynamically from subagent metadata.
- Genie integrations use MCP server registration with parallel runtime health checks and short TTL health caching.
- Lakebase integrations use PostgreSQL wire protocol with an OAuth credential generated at invocation time by the Databricks Postgres credentials API.
- Native function and MCP calls are required; pseudo-tool text is not valid tool execution.
- A Lakebase request may use one schema-discovery query followed by one data query. A `LAKEBASE_QUERY_FAILED` result is not retried.
- Capability-based route planning produces a typed `RoutePlan`; ambiguous requests fall back to the policy-approved subagent set.
- Route confidence is based on the winning capability score relative to the runner-up. Plans below the implementation threshold of `0.60` use `low_confidence_fallback` and do not hard-restrict the model to a heuristic candidate.

Primary implementation:

- src/backend/domain/subagent_config.py
- src/backend/domain/subagents.dev.json
- src/backend/domain/subagents.qa.json
- src/backend/domain/subagents.stg.json
- src/backend/domain/subagents.prod.json
- src/backend/services/orchestrator_service.py

## 3. Authorization Specification

- Hybrid authorization is implemented at subagent level via auth_mode.
- auth_mode app uses app identity.
- auth_mode obo uses forwarded user identity via x-forwarded-access-token.
- Missing required OBO identity produces explicit authorization failure behavior.
- Lakebase uses the app identity's OAuth database role. The configured `pg_user` must match that role.

Primary implementation:

- src/backend/shared/runtime_utils.py
- src/backend/services/runtime_auth_service.py

## 4. Governance and Policy Specification

- Governance metadata is implemented in subagent schema:
  - data_classification
  - owner
  - freshness_sla
  - allowed_personas
  - requires_evidence
- Request-time policy enforcement runs before tool execution.
- Policy decisions produce explicit allow or deny reason codes.

Primary implementation:

- src/backend/domain/subagent_config.py
- src/backend/services/policy_service.py
- src/backend/services/runtime_auth_service.py

## 5. Response Guardrail Specification

- Guardrails run on response output before final return.
- Evidence and citation requirements are enforced for governed responses.
- Unsafe output and low-confidence sensitive output checks are enforced.
- Guardrail decisions emit pass and block lifecycle events.
- Input guardrails run before runtime authorization and emit `request.guardrail.blocked` with stable reason codes.
- Response budgets are configured with `MAX_INPUT_CHARS` and `MAX_RESPONSE_CHARS`.

Primary implementation:

- src/backend/services/guardrails_service.py
- src/backend/api/handlers.py

## 6. Observability and Audit Specification

- Lifecycle events are normalized with a shared event envelope.
- Events are emitted across request, tool, MCP, auth, policy, and guardrail stages.
- Message bus backend is environment-configurable.
- Optional async queue-backed message-bus publishing is available to reduce request-path event I/O overhead.
- UC-governed persistence is implemented through a uc_table backend.
- Tool success/failure events include normalized status, latency, attempt count, auth mode, and error code.

Supported backends:

- structured_logging
- noop
- kafka
- rabbitmq
- uc_table

Primary implementation:

- src/backend/services/message_bus.py
- src/backend/shared/settings.py

## 7. Release Quality Gate Specification

- Automated evaluation is implemented as a release gate.
- KPI threshold checks are enforced for tool accuracy, auth correctness, safety, and groundedness.
- Missing KPI handling is configurable through strictness controls.
- CI runs tests and evaluation before deployment steps.

Primary implementation:

- src/backend/evaluate_agent.py
- .github/workflows/databricks-cicd.yml

## 8. Agent Delegation Specification

- Agent-to-agent delegation uses typed tasks with correlation IDs, idempotency keys, bounded retries, leases, expiry, and dead-letter states.
- The default `AGENT_TASK_BACKEND=memory` is suitable for synchronous, single-process handoffs only; dev is configured for `uc_table`.
- `AGENT_TASK_BACKEND=uc_table` persists tasks and state transitions in separate Unity Catalog Delta task and event tables through the SQL Statement API.
- The UC backend is fail-closed. It requires `AGENT_TASK_WAREHOUSE_ID`, `AGENT_TASK_CATALOG`, and `AGENT_TASK_SCHEMA`; missing configuration or failed writes stop delegation rather than dropping work.
- Delegation is deny-by-default, app-auth-only, and restricted by each target agent's allowed source, intent, and depth configuration.
- The first enabled dev handoff is `orchestrator -> lakebase_ods_agent` with intent `appointment_summary`.
- Dev provisions `quickstart_catalog.multi_agent_schema.agent_delegation_tasks` and `agent_delegation_events`, with exact-table `SELECT, MODIFY` access for the app identity.
- When `AGENT_TASK_WORKER_ENABLED=true`, the backend lifespan starts a bounded background worker that leases durable tasks at `AGENT_TASK_WORKER_POLL_SECONDS` intervals and stops it cleanly at shutdown.
- `GET /delegations/{task_id}` exposes a payload-redacted task status view through the backend and React proxy.

Primary implementation:

- src/backend/domain/agent_messages.py
- src/backend/services/agent_task_bus.py
- src/backend/services/agent_task_worker.py
- src/backend/services/agent_handoff_service.py
- src/backend/services/agent_delegation_policy_service.py

## 9. Deployment and Environment Specification

- Deployment is target-based with dev, qa, stg, and prod overlays.
- Shared resource configuration is centralized and target overrides are explicit.
- Environment variables configure runtime behavior for auth, bus backends, UC audit sink, and release gates.
- Process concurrency tuning is supported through backend and frontend Uvicorn worker env controls.
- Operational fallback deployment path is documented for registry outage scenarios.

Primary implementation:

- databricks.yml
- resources/multiagent_app.yml
- targets/dev.yml
- targets/qa.yml
- targets/stg.yml
- targets/prod.yml
- docs/operations/operations-runbook.md

## 10. Validation Specification

- Unit and integration tests cover subagent config, runtime auth, policy, message bus, and guardrails.
- Compile checks and preflight runtime checks are used for end-to-end local validation.
- Bundle validation is used to verify deploy-time configuration integrity.
- App resource validation includes Lakebase Autoscaling `branch`, `database`, and `CAN_CONNECT_AND_CREATE` fields.

## 11. Evaluation Readiness

- Deterministic route-plan tests pass for sales, product, Flink, CDI, and Lakebase intents.
- The latest Databricks-backed conversational evaluation remains blocked: `ToolCallCorrectness = 0.400 < 0.800`.
- Route-plan events must not be interpreted as proof of correct model tool calls; actual tool-call traces remain the release-gate authority.
- The evaluation corpus requires explicit cases for tool-required, tool-optional, and no-tool conversational turns.

Primary implementation:

- tests/test_subagent_config.py
- tests/test_runtime_auth.py
- tests/test_policy_service.py
- tests/test_guardrails_service.py
- tests/test_message_bus_backends.py
- tests/test_message_bus_integration.py
- src/scripts/preflight.py

## Related Documents

- [Architecture guide](README.md)
- [High-level architecture](high-level-architecture.md)
- [Low-level design](low-level-design.md)
- [Business specifications](../product/business-specs.md)
- [Operations runbook](../operations/operations-runbook.md)
- [Architecture decision records](../adrs/README.md)
