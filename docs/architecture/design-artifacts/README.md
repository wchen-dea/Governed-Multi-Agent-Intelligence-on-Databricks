# AI System Design Artifacts

Centralized system-design artifact set for the multi-agent orchestrator across concept, logical, and deployment phases.

## Scope

Artifacts are organized by phase and depth:

- **Concept** — business framing, personas, trust boundaries
- **Logical** — runtime architecture, pipeline stages, policy/guardrail flows
- **Deployment** — environment topology, CI/CD, observability

Each phase is split into high-level (architecture overview) and detailed (engineering implementation) views.

## Artifact Inventory

| # | File | Focus |
| --- | --- | --- |
| 00 | [00-architecture-review-checklist.md](00-architecture-review-checklist.md) | Review index, implementation status, and canonical links |
| 01 | [01-concept-business-context.md](01-concept-business-context.md) | Business capabilities, actors, and system context |
| 02 | [02-concept-scope-personas-boundaries.md](02-concept-scope-personas-boundaries.md) | Scope map, persona-agent matrix, trust boundaries |
| 03 | [03-logical-containers-and-flows.md](03-logical-containers-and-flows.md) | Runtime containers, request flow, and identity flow |
| 04 | [04-logical-components-policy-evaluation.md](04-logical-components-policy-evaluation.md) | Components, policy rules, failure/recovery, evaluation gate |
| 05 | [05-deployment-topology-and-resources.md](05-deployment-topology-and-resources.md) | Environment topology, runtime map, and resource mapping |
| 06 | [06-deployment-network-cicd-observability.md](06-deployment-network-cicd-observability.md) | Network topology, CI/CD pipeline, observability, HA |
| 07 | [07-runtime-invocation-stream-pipeline.md](07-runtime-invocation-stream-pipeline.md) | Invoke and stream pipeline class diagrams |
| 08 | [08-runtime-domain-model.md](08-runtime-domain-model.md) | Domain model, dependency composition, message bus, and subagent registry |

## Coverage Matrix

| Phase | High Level | Detailed |
| --- | --- | --- |
| Concept | Business capabilities, actor/persona map, system context, value flow | Scope map, persona-agent access matrix, trust boundaries + risks |
| Logical | Container diagram, end-to-end request flow, data lineage, identity flow | Backend components, policy decision tree, prompt layering, failure/recovery, evaluation gate |
| Deployment | Environment topology, runtime deployment map, subagent resource mapping | Network/security topology, CI/CD pipeline, observability architecture, HA/recovery |

## Current Implementation Facts

- **6 subagents**: sales_insights (Genie), cdi (Genie), product_index (AI Search MCP), flink_support (AI Search MCP), store-intervention-agent (Databricks App HITL), lakebase_ods (Lakebase)
- **4 personas**: manager (all), analyst (sales + product + lakebase), operator (flink), engineer (flink + lakebase)
- **Model router**: deterministic standard, reasoning, and synthesis selection; dev uses `databricks-gpt-5-6-luna` for standard turns and `databricks-claude-sonnet-5` for reasoning/synthesis turns
- **AI Gateway**: opt-in via DATABRICKS_OPENAI_BASE_URL
- **Message bus**: uc_table (dev) with structured_logging fallback
- **Delegation**: bounded app-auth UC task/event store, synchronous native handoff settlement, optional lifespan worker, and payload-redacted status endpoint
- **Streaming**: events buffer and finalize before the UI renders `response.output_text.delta` only
- **Release gate**: auth correctness, safety, and groundedness block promotion; tool-call accuracy is monitored but non-blocking until nested tool spans are scored reliably
- **Workspace**: dbc-baff2b7f-4402.cloud.databricks.com (dev)

Canonical narrative references: [runtime technical specifications](../runtime-technical-specs.md), [API contracts](../api-contracts.md), [tool and model registry](../tool-and-model-registry.md), and [low-level design](../runtime-behavior-and-implementation.md).

## Ownership and Update Policy

- Primary owner: platform engineering
- Update triggers: new subagent, persona change, auth/policy change, deployment topology change
- Update these artifacts in the same PR where behavior changes.
