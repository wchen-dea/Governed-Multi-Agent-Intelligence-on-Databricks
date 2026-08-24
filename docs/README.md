# Documentation Guide

This guide separates current implementation authority from operating procedures, governance intent, decision history, and platform-neutral reference material.

## Authority Map

| Need | Authoritative location |
| --- | --- |
| Current runtime behavior | [Architecture guide](architecture/README.md) and [runtime technical specifications](architecture/runtime-technical-specs.md) |
| API and stream behavior | [API contracts](architecture/api-contracts.md) |
| Active tools, models, and integration routes | [Tool and model registry](architecture/tool-and-model-registry.md) |
| Deployment and incident procedures | [Operations guide](operations/README.md) |
| Evaluation and release evidence | [Quality guide](quality/README.md) |
| Policy intent and security expectations | [Governance guide](governance/README.md) |
| Historical technical decisions | [ADR index](adrs/README.md) |
| Enterprise target-state research | [Reference pack](reference/README.md) |

## Read By Role

1. **AI executive:** [Architecture guide](architecture/README.md) -> [Product guide](product/README.md) -> [Quality guide](quality/README.md) -> [Operations guide](operations/README.md)
2. **AI architect:** [Architecture guide](architecture/README.md) -> [Governance guide](governance/README.md) -> [ADR index](adrs/README.md)
3. **Application engineer:** [API contracts](architecture/api-contracts.md) -> [Low-level design](architecture/low-level-design.md) -> [Tool and model registry](architecture/tool-and-model-registry.md)
4. **Platform operator:** [Operations guide](operations/README.md) -> [Architecture deployment artifacts](architecture/design-artifacts/05-deployment-high-level.md)
5. **Security or governance reviewer:** [Governance guide](governance/README.md) -> [Architecture high-level view](architecture/high-level-architecture.md)

## Team Onboarding: Skills and Capabilities

Primary project skills:

- `add-tools`, `create-tools`, `discover-tools`, `modify-agent`, `deploy`, `quickstart`, `run-locally`

Capabilities enabled:

- Multi-agent orchestration with governed routing and guardrails.
- Genie Agent and AI Search integrations with environment-specific config.
- Hybrid authorization (`app` and `obo`) and deployment promotion across environments.

Runtime skills playbooks:

- [runtime-routing](../.claude/skills/runtime-routing/SKILL.md)
- [runtime-guardrails](../.claude/skills/runtime-guardrails/SKILL.md)
- [runtime-auth-obo](../.claude/skills/runtime-auth-obo/SKILL.md)
- [runtime-audit-observability](../.claude/skills/runtime-audit-observability/SKILL.md)

Use this index to navigate project documentation by purpose:

- [product/README.md](product/README.md): business outcomes, scope, and current capability boundary.
- [architecture/README.md](architecture/README.md): architecture reading paths, authority map, and current control planes.
- [governance/README.md](governance/README.md): policy, data, semantic, and security ownership.
- [operations/README.md](operations/README.md): deployment, verification, MLflow, scripts, and incident paths.
- [quality/README.md](quality/README.md): evaluation, KPI thresholds, and release evidence.
- [internal/README.md](internal/README.md): contributor and assistant workflow boundaries.
- [architecture/runtime-technical-specs.md](architecture/runtime-technical-specs.md): centralized technical implementation specification.
- [quality/evaluation-spec.md](quality/evaluation-spec.md): datasets, scorers, KPI thresholds, and release-gate behavior.
- [governance/prompt-policy-controls.md](governance/prompt-policy-controls.md): prompt layering, deterministic policy checks, and guardrail controls.
- [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md): inventory of active models, endpoints, and Genie Agents.
- [architecture/semantics-layer-design.md](architecture/semantics-layer-design.md): semantics layer scope, ownership boundaries, and AI Search index/Metric View build pipelines.
- [governance/data-contracts-lineage.md](governance/data-contracts-lineage.md): request and response contracts, sensitivity model, and audit lineage requirements.
- [governance/business-semantics-metadata.md](governance/business-semantics-metadata.md): canonical business semantics and required AI metadata contract.
- [governance/security-threat-model.md](governance/security-threat-model.md): trust boundaries, threats, and implemented controls.
- [operations/cost-performance-budget.md](operations/cost-performance-budget.md): operating budgets, key signals, and release checks.
- [operations/mlflow-guide.md](operations/mlflow-guide.md): how MLflow tracing, evaluation, and release gating work in this project.
- [operations/mlflow-rollout-checklist.md](operations/mlflow-rollout-checklist.md): one-page implementation plan with owners, tasks, and acceptance criteria for MLflow rollout.
- [operations/mlflow-rollout-tracker.md](operations/mlflow-rollout-tracker.md): live status board template for owners, dates, dependencies, evidence, and blockers.
- [architecture/api-contracts.md](architecture/api-contracts.md): API request/response and error behavior contract.
- [operations/postmortem-template.md](operations/postmortem-template.md): standard template for incidents and release regressions.
- [architecture/high-level-architecture.md](architecture/high-level-architecture.md): high-level system architecture, boundaries, and request flow.
- [architecture/low-level-design.md](architecture/low-level-design.md): low-level implementation details, runtime behavior, and configuration model.
- [architecture/backend-framework-design.md](architecture/backend-framework-design.md): backend package structure, request pipeline, DI, subagent types, and policy enforcement.
- [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md): centralized concept, logical, and deployment diagram set.
- [operations/operations-runbook.md](operations/operations-runbook.md): deployment and operations procedures.
- [internal/claude.md](internal/claude.md): unified Claude skill summary, usage order, and operating guidelines.
- [adrs/README.md](adrs/README.md): architecture decision records and long-lived technical decisions.

## Recommended Read Order

1. [architecture/README.md](architecture/README.md)
2. [architecture/high-level-architecture.md](architecture/high-level-architecture.md)
3. [product/business-specs.md](product/business-specs.md)
4. [architecture/runtime-technical-specs.md](architecture/runtime-technical-specs.md)
5. [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md)
6. [governance/data-contracts-lineage.md](governance/data-contracts-lineage.md)
7. [governance/business-semantics-metadata.md](governance/business-semantics-metadata.md)
8. [governance/prompt-policy-controls.md](governance/prompt-policy-controls.md)
9. [quality/evaluation-spec.md](quality/evaluation-spec.md)
10. [governance/security-threat-model.md](governance/security-threat-model.md)
11. [operations/cost-performance-budget.md](operations/cost-performance-budget.md)
12. [operations/mlflow-rollout-checklist.md](operations/mlflow-rollout-checklist.md)
13. [operations/mlflow-rollout-tracker.md](operations/mlflow-rollout-tracker.md)
14. [architecture/api-contracts.md](architecture/api-contracts.md)
15. [architecture/low-level-design.md](architecture/low-level-design.md)
16. [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md)
17. [operations/operations-runbook.md](operations/operations-runbook.md)
18. [operations/postmortem-template.md](operations/postmortem-template.md)
19. [internal/claude.md](internal/claude.md)
20. [adrs/README.md](adrs/README.md)

## Quick Config Snippets

Use these in `.env` for local message-bus transport selection.

### Structured Logging (default)

```bash
MESSAGE_BUS_BACKEND=structured_logging
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
```

### Kafka

```bash
MESSAGE_BUS_BACKEND=kafka
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=multiagent-app
```

### RabbitMQ

```bash
MESSAGE_BUS_BACKEND=rabbitmq
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

### Unity Catalog Audit Table

```bash
MESSAGE_BUS_BACKEND=uc_table
MESSAGE_BUS_TOPIC=agent-lifecycle-events
MESSAGE_BUS_FAIL_OPEN=true
UC_AUDIT_WAREHOUSE_ID=<warehouse-id>
UC_AUDIT_CATALOG=main
UC_AUDIT_SCHEMA=observability
UC_AUDIT_TABLE=agent_lifecycle_events
```

For deployment and incident procedures, see [operations/operations-runbook.md](operations/operations-runbook.md).
