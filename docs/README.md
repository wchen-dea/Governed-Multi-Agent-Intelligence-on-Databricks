# Documentation Index

Use this index to navigate project documentation by purpose:

- [product/business-specs.md](product/business-specs.md): business goals, requirements, constraints, and success metrics.
- [architecture/technical-specs.md](architecture/technical-specs.md): centralized technical implementation specification.
- [quality/evaluation-spec.md](quality/evaluation-spec.md): datasets, scorers, KPI thresholds, and release-gate behavior.
- [governance/prompt-and-policy-spec.md](governance/prompt-and-policy-spec.md): prompt layering, deterministic policy checks, and guardrail controls.
- [architecture/model-and-tool-registry.md](architecture/model-and-tool-registry.md): inventory of active models, endpoints, and Genie Agents.
- [governance/data-contract-and-lineage-spec.md](governance/data-contract-and-lineage-spec.md): request and response contracts, sensitivity model, and audit lineage requirements.
- [governance/business-semantics-and-ai-metadata-spec.md](governance/business-semantics-and-ai-metadata-spec.md): canonical business semantics and required AI metadata contract.
- [governance/security-and-threat-model.md](governance/security-and-threat-model.md): trust boundaries, threats, and implemented controls.
- [operations/cost-and-performance-budget.md](operations/cost-and-performance-budget.md): operating budgets, key signals, and release checks.
- [operations/mlflow-implementation-checklist.md](operations/mlflow-implementation-checklist.md): one-page implementation plan with owners, tasks, and acceptance criteria for MLflow rollout.
- [operations/mlflow-execution-tracker.md](operations/mlflow-execution-tracker.md): live status board template for owners, dates, dependencies, evidence, and blockers.
- [architecture/api-contract-spec.md](architecture/api-contract-spec.md): API request/response and error behavior contract.
- [operations/postmortem-template.md](operations/postmortem-template.md): standard template for incidents and release regressions.
- [architecture/system-architecture.md](architecture/system-architecture.md): high-level system architecture, boundaries, and request flow.
- [architecture/system-design.md](architecture/system-design.md): low-level implementation details, runtime behavior, and configuration model.
- [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md): centralized concept, logical, and deployment diagram set.
- [operations/runbook.md](operations/runbook.md): deployment and operations procedures.
- [internal/claude.md](internal/claude.md): unified Claude skill summary, usage order, and operating guidelines.
- [adrs/README.md](adrs/README.md): architecture decision records and long-lived technical decisions.

## Recommended Read Order

1. [architecture/system-architecture.md](architecture/system-architecture.md)
2. [product/business-specs.md](product/business-specs.md)
3. [architecture/technical-specs.md](architecture/technical-specs.md)
4. [architecture/model-and-tool-registry.md](architecture/model-and-tool-registry.md)
5. [governance/data-contract-and-lineage-spec.md](governance/data-contract-and-lineage-spec.md)
6. [governance/business-semantics-and-ai-metadata-spec.md](governance/business-semantics-and-ai-metadata-spec.md)
7. [governance/prompt-and-policy-spec.md](governance/prompt-and-policy-spec.md)
8. [quality/evaluation-spec.md](quality/evaluation-spec.md)
9. [governance/security-and-threat-model.md](governance/security-and-threat-model.md)
10. [operations/cost-and-performance-budget.md](operations/cost-and-performance-budget.md)
11. [operations/mlflow-implementation-checklist.md](operations/mlflow-implementation-checklist.md)
12. [operations/mlflow-execution-tracker.md](operations/mlflow-execution-tracker.md)
13. [architecture/api-contract-spec.md](architecture/api-contract-spec.md)
14. [architecture/system-design.md](architecture/system-design.md)
15. [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md)
16. [operations/runbook.md](operations/runbook.md)
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

For deployment and incident procedures, see [operations/runbook.md](operations/runbook.md).
