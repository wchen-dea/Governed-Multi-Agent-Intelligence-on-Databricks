# ADR Index

Architecture Decision Records (ADRs) capture durable technical decisions for this project.

ADRs explain accepted rationale at the time of the decision. They are not the mutable runtime inventory; use the [architecture guide](../architecture/README.md) and [runtime technical specifications](../architecture/runtime-technical-specs.md) for current implementation facts.

## ADR Conventions

- Filename format: `NNNN-short-kebab-case-title.md`
- Status values: `Accepted`, `Superseded`, `Proposed`
- Required sections: `Status`, `Context`, `Decision`, `Alternatives Considered`, `Consequences`, `Implementation Notes`
- Update policy: when a decision changes materially, create a new ADR and mark older ADRs as `Superseded` rather than rewriting history.

## ADR Catalog

| ADR | Title | Status |
| --- | ----- | ------ |
| [0001](0001-layered-backend-architecture.md) | Use layered backend package structure | Accepted |
| [0002](0002-hybrid-auth-model.md) | Use hybrid app plus OBO authorization model | Accepted |
| [0003](0003-centralized-dependency-composition.md) | Centralize dependency composition in API layer | Accepted |
| [0004](0004-lifecycle-message-bus.md) | Use lifecycle message bus abstraction with pluggable transports | Accepted |
| [0005](0005-governed-routing-policy-and-response-guardrails.md) | Enforce governed routing policy and response guardrails | Accepted |
| [0006](0006-unity-catalog-audit-table-for-lifecycle-events.md) | Persist lifecycle events to UC-governed audit table | Accepted |
| [0007](0007-evaluation-kpi-release-gate.md) | Block release when evaluation KPIs are below thresholds | Accepted |
| [0008](0008-custom-orchestrator-vs-databricks-supervisor-agent.md) | Keep custom orchestrator as primary runtime over Databricks Supervisor Agent | Accepted |
| [0009](0009-unity-ai-gateway-for-llm-traffic.md) | Route orchestrator LLM traffic through Unity AI Gateway | Accepted |
