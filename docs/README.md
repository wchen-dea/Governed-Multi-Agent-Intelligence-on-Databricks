# Documentation Index

This documentation set supports the blueprint project for building multi-agent apps on Databricks.

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

- [product/business-specs.md](product/business-specs.md): business goals, requirements, constraints, and success metrics.
- [architecture/runtime-technical-specs.md](architecture/runtime-technical-specs.md): centralized technical implementation specification.
- [quality/evaluation-spec.md](quality/evaluation-spec.md): datasets, scorers, KPI thresholds, and release-gate behavior.
- [governance/prompt-policy-controls.md](governance/prompt-policy-controls.md): prompt layering, deterministic policy checks, and guardrail controls.
- [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md): inventory of active models, endpoints, and Genie Agents.
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

1. [architecture/high-level-architecture.md](architecture/high-level-architecture.md)
2. [product/business-specs.md](product/business-specs.md)
3. [architecture/runtime-technical-specs.md](architecture/runtime-technical-specs.md)
4. [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md)
5. [governance/data-contracts-lineage.md](governance/data-contracts-lineage.md)
6. [governance/business-semantics-metadata.md](governance/business-semantics-metadata.md)
7. [governance/prompt-policy-controls.md](governance/prompt-policy-controls.md)
8. [quality/evaluation-spec.md](quality/evaluation-spec.md)
9. [governance/security-threat-model.md](governance/security-threat-model.md)
10. [operations/cost-performance-budget.md](operations/cost-performance-budget.md)
11. [operations/mlflow-rollout-checklist.md](operations/mlflow-rollout-checklist.md)
12. [operations/mlflow-rollout-tracker.md](operations/mlflow-rollout-tracker.md)
13. [architecture/api-contracts.md](architecture/api-contracts.md)
14. [architecture/low-level-design.md](architecture/low-level-design.md)
15. [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md)
16. [operations/operations-runbook.md](operations/operations-runbook.md)
17. [operations/postmortem-template.md](operations/postmortem-template.md)
18. [internal/claude.md](internal/claude.md)
19. [adrs/README.md](adrs/README.md)

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
