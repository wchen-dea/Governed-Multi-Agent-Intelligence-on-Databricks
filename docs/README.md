# Documentation Guide

This guide separates current implementation authority from operating procedures, governance intent, decision history, and platform-neutral reference material.

## Authority Map

| Need | Authoritative location |
| --- | --- |
| Current runtime behavior | [Architecture guide](architecture/README.md) and [runtime technical specifications](architecture/runtime-specification.md) |
| Current solution overview | [AI solution current](ai-solution-current.md) |
| AI frameworks, patterns, tools, and skills | [AI technologies and patterns](architecture/technology-and-patterns.md) |
| API and stream behavior | [API contracts](api/contracts.md) |
| Active tools, models, and integration routes | [Tool and model registry](architecture/tool-and-model-registry.md) |
| Deployment and incident procedures | [Operations guide](operations/README.md) |
| Evaluation and release evidence | [Quality guide](quality/README.md) |
| Policy intent and security expectations | [Governance guide](governance/README.md) |
| Historical technical decisions | [ADR index](decisions/README.md) |
| Enterprise target-state research | [Reference pack](reference/README.md) |

## Read By Role

1. **AI executive:** [Architecture guide](architecture/README.md) -> [Product guide](product/README.md) -> [Quality guide](quality/README.md) -> [Operations guide](operations/README.md)
2. **AI architect:** [Architecture guide](architecture/README.md) -> [Governance guide](governance/README.md) -> [ADR index](decisions/README.md)
3. **Application engineer:** [API contracts](api/contracts.md) -> [Low-level design](architecture/runtime-implementation.md) -> [Tool and model registry](architecture/tool-and-model-registry.md)
4. **Platform operator:** [Operations guide](operations/README.md) -> [Architecture deployment artifacts](architecture/design-artifacts/05-deployment-topology-and-resources.md)
5. **Security or governance reviewer:** [Governance guide](governance/README.md) -> [Architecture high-level view](architecture/system-architecture.md)

## Team Onboarding: Skills and Capabilities

Primary project skills:

- `environment-quickstart`, `environment-run-local`, `capability-discover`, `capability-create`, `capability-register`, `behavior-modify`, `governance-routing`, `governance-guardrails`, `governance-auth-obo`, `observability-audit`, `quality-evaluation`, `release-deploy`

Capabilities enabled:

- Multi-agent orchestration with governed routing and guardrails.
- Genie Agent, AI Search, and serving-endpoint integrations with environment-specific config.
- Hybrid authorization (`app` and `obo`), deployment promotion, and evidence-driven release gates.

Active skill playbooks:

- [environment-quickstart](../.claude/skills/environment-quickstart/SKILL.md)
- [environment-run-local](../.claude/skills/environment-run-local/SKILL.md)
- [capability-discover](../.claude/skills/capability-discover/SKILL.md)
- [capability-create](../.claude/skills/capability-create/SKILL.md)
- [capability-register](../.claude/skills/capability-register/SKILL.md)
- [behavior-modify](../.claude/skills/behavior-modify/SKILL.md)
- [governance-routing](../.claude/skills/governance-routing/SKILL.md)
- [governance-guardrails](../.claude/skills/governance-guardrails/SKILL.md)
- [governance-auth-obo](../.claude/skills/governance-auth-obo/SKILL.md)
- [observability-audit](../.claude/skills/observability-audit/SKILL.md)
- [quality-evaluation](../.claude/skills/quality-evaluation/SKILL.md)
- [release-deploy](../.claude/skills/release-deploy/SKILL.md)

Use this index to navigate project documentation by purpose:

- [product/README.md](product/README.md): business outcomes, scope, and current capability boundary.
- [getting-started/agent-usage.md](getting-started/agent-usage.md): what each agent is best at, perfect-match query types, and composite/freshness guidance for end users.
- [ai-solution-current.md](ai-solution-current.md): consolidated current implementation architecture, runtime flow, deployment, HITL, model routing, and evaluation posture.
- [architecture/README.md](architecture/README.md): architecture reading paths, authority map, and current control planes.
- [architecture/technology-and-patterns.md](architecture/technology-and-patterns.md): concise inventory of AI frameworks, design patterns, tools, data capabilities, and project skills.
- [governance/README.md](governance/README.md): policy, data, semantic, and security ownership.
- [operations/README.md](operations/README.md): deployment, verification, MLflow, scripts, and incident paths.
- [quality/README.md](quality/README.md): evaluation, KPI thresholds, and release evidence.
- [internal/README.md](internal/README.md): contributor and assistant workflow boundaries.
- [architecture/runtime-specification.md](architecture/runtime-specification.md): centralized technical implementation specification.
- [quality/evaluation-specification.md](quality/evaluation-specification.md): datasets, scorers, KPI thresholds, and release-gate behavior.
- [governance/prompt-policy.md](governance/prompt-policy.md): prompt layering, deterministic policy checks, and guardrail controls.
- [governance/human-approval.md](governance/human-approval.md): implemented manager approval workflow, decision API, durable persistence, and dispatch boundary.
- [governance/prompt-engineering.md](governance/prompt-engineering.md): hands-on conventions for writing and reviewing subagent `system_prompt`/`description` fields and orchestrator instructions.
- [governance/context-engineering.md](governance/context-engineering.md): conventions for what context to assemble, retrieve, remember, and discard (routing instructions, sticky routing, memory, retrieval).
- [governance/agent-harness-guidelines.md](governance/agent-harness-guidelines.md): conventions for request pipeline, execution contracts, delegation bounds, model selection, and lifecycle observability.
- [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md): inventory of active models, endpoints, and Genie Agents.
- [architecture/semantics-layer-design.md](architecture/semantics-layer-design.md): semantics layer scope, ownership boundaries, and AI Search index/Metric View build pipelines.
- [governance/data-contracts-and-lineage.md](governance/data-contracts-and-lineage.md): request and response contracts, sensitivity model, and audit lineage requirements.
- [governance/business-semantics.md](governance/business-semantics.md): canonical business semantics and required AI metadata contract.
- [governance/security-threat-model.md](governance/security-threat-model.md): trust boundaries, threats, and implemented controls.
- [operations/cost-and-performance.md](operations/cost-and-performance.md): operating budgets, key signals, and release checks.
- [operations/mlflow-guide.md](operations/mlflow-guide.md): how MLflow tracing, evaluation, and release gating work in this project.
- [operations/monitoring-and-observability.md](operations/monitoring-and-observability.md): consolidated status of observability, evaluation/quality, safety, drift/anomaly detection, and cost monitoring — including what is not yet implemented.
- [operations/release-checklist.md](operations/release-checklist.md): one-page implementation plan with owners, tasks, and acceptance criteria for MLflow rollout.
- [operations/release-tracker.md](operations/release-tracker.md): live status board template for owners, dates, dependencies, evidence, and blockers.
- [api/contracts.md](api/contracts.md): API request/response and error behavior contract.
- [operations/postmortem-template.md](operations/postmortem-template.md): standard template for incidents and release regressions.
- [architecture/system-architecture.md](architecture/system-architecture.md): high-level system architecture, boundaries, and request flow.
- [architecture/runtime-implementation.md](architecture/runtime-implementation.md): low-level implementation details, runtime behavior, and configuration model.
- [architecture/backend-package-structure.md](architecture/backend-package-structure.md): backend package structure, request pipeline, DI, subagent types, and policy enforcement.
- [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md): centralized concept, logical, and deployment diagram set.
- [operations/runbook.md](operations/runbook.md): deployment and operations procedures.
- [development/ai-agent-guidelines.md](development/ai-agent-guidelines.md): unified Claude skill summary, usage order, and operating guidelines.
- [development/ai-development-lifecycle.md](development/ai-development-lifecycle.md): maps Claude Code skills to AI system development life-cycle stages and documents per-stage best practices.
- [decisions/README.md](decisions/README.md): architecture decision records and long-lived technical decisions.

## Recommended Read Order

1. [architecture/README.md](architecture/README.md)
2. [ai-solution-current.md](ai-solution-current.md)
3. [architecture/system-architecture.md](architecture/system-architecture.md)
4. [reference/business-requirements.md](reference/business-requirements.md)
5. [architecture/runtime-specification.md](architecture/runtime-specification.md)
6. [architecture/tool-and-model-registry.md](architecture/tool-and-model-registry.md)
7. [governance/data-contracts-and-lineage.md](governance/data-contracts-and-lineage.md)
8. [governance/business-semantics.md](governance/business-semantics.md)
9. [governance/prompt-policy.md](governance/prompt-policy.md)
10. [governance/human-approval.md](governance/human-approval.md)
11. [quality/evaluation-specification.md](quality/evaluation-specification.md)
12. [governance/security-threat-model.md](governance/security-threat-model.md)
13. [operations/cost-and-performance.md](operations/cost-and-performance.md)
14. [operations/release-checklist.md](operations/release-checklist.md)
15. [operations/release-tracker.md](operations/release-tracker.md)
16. [api/contracts.md](api/contracts.md)
17. [architecture/runtime-implementation.md](architecture/runtime-implementation.md)
18. [architecture/design-artifacts/README.md](architecture/design-artifacts/README.md)
19. [operations/runbook.md](operations/runbook.md)
20. [operations/postmortem-template.md](operations/postmortem-template.md)
21. [development/ai-agent-guidelines.md](development/ai-agent-guidelines.md)
22. [decisions/README.md](decisions/README.md)

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
