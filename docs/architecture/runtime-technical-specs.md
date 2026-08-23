# Technical Specs

This document summarizes the technical specifications currently implemented in this project.

## 1. Runtime Architecture Specification

- Layered backend architecture is implemented with API, services, domain, and shared layers.
- Request handling supports both invoke and stream flows through MLflow Agent Server handlers.
- Orchestrator agent is assembled at runtime with available tools and healthy MCP servers.
- Frontend runtime is React UI first, with a legacy Chainlit path retained for compatibility.

Primary implementation:

- src/backend/api/handlers.py
- src/backend/api/dependencies.py
- src/backend/services/orchestrator_service.py
- src/reactui/src/App.tsx
- src/reactui/src/api.ts
- src/scripts/react_ui_server.py

## 2. Tool Routing Specification

- Subagent configuration is externalized in JSON and validated through typed domain models.
- Supported subagent kinds include genie, serving_endpoint, app, mcp, and lakebase.
- Non-Genie function tools are generated dynamically from subagent metadata.
- Genie integrations use MCP server registration with parallel runtime health checks and short TTL health caching.
- Lakebase integrations use PostgreSQL wire protocol with a secret-backed SCRAM password when configured, falling back to OAuth credentials generated at invocation time.
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
- Lakebase password material is supplied through the `multiagent_app/lakebase_pg_password` Databricks secret and is never read from target YAML values.

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

## 8. Deployment and Environment Specification

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

## 9. Validation Specification

- Unit and integration tests cover subagent config, runtime auth, policy, message bus, and guardrails.
- Compile checks and preflight runtime checks are used for end-to-end local validation.
- Bundle validation is used to verify deploy-time configuration integrity.
- App resource validation includes Lakebase Autoscaling `branch`, `database`, and `CAN_CONNECT_AND_CREATE` fields plus secret-scope resource grants.

## 10. Evaluation Readiness

- Deterministic route-plan tests pass for sales, product, Flink, CDI, and Lakebase intents.
- The latest Databricks-backed conversational evaluation remains blocked at tool-call accuracy `0.400 < 0.800`.
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

- high-level-architecture.md
- low-level-design.md
- ../product/business-specs.md
- ../operations/operations-runbook.md
- adrs/README.md
