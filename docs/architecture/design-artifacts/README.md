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
|---|------|-------|
| 00 | [00-architecture-board-review.md](00-architecture-board-review.md) | Review index, implementation status, and canonical links |
| 01 | [01-concept-high-level.md](01-concept-high-level.md) | Business capabilities, actors, system context |
| 02 | [02-concept-detailed.md](02-concept-detailed.md) | Scope map, persona-agent matrix, trust boundaries |
| 03 | [03-logical-high-level.md](03-logical-high-level.md) | Container diagram, request flow, identity flow |
| 04 | [04-logical-detailed.md](04-logical-detailed.md) | Components, policy rules, failure/recovery, evaluation gate |
| 05 | [05-deployment-high-level.md](05-deployment-high-level.md) | Environment topology, runtime map, resource mapping |
| 06 | [06-deployment-detailed.md](06-deployment-detailed.md) | Network topology, CI/CD pipeline, observability, HA |
| 07 | [07-request-execution-flow-class-diagram.md](07-request-execution-flow-class-diagram.md) | UML class diagrams for invoke/stream pipeline stages |
| 08 | [08-backend-class-diagram-as-is.md](08-backend-class-diagram-as-is.md) | Domain model, DI composition, message bus strategy, subagent registry |

## Coverage Matrix

| Phase | High Level | Detailed |
|-------|-----------|----------|
| Concept | Business capabilities, actor/persona map, system context, value flow | Scope map, persona-agent access matrix, trust boundaries + risks |
| Logical | Container diagram, end-to-end request flow, data lineage, identity flow | Backend components, policy decision tree, prompt layering, failure/recovery, evaluation gate |
| Deployment | Environment topology, runtime deployment map, subagent resource mapping | Network/security topology, CI/CD pipeline, observability architecture, HA/recovery |

## Current Implementation Facts

- **5 subagents**: sales_insights (Genie), cdi (Genie), product_index (AI Search MCP), flink_support (AI Search MCP), lakebase_ods (Lakebase)
- **4 personas**: manager (all), analyst (product + lakebase), operator (flink), engineer (product + flink + lakebase)
- **Model router**: deterministic standard, reasoning, and synthesis selection; dev resolves all routes to `databricks-gpt-5-6-luna`
- **AI Gateway**: opt-in via DATABRICKS_OPENAI_BASE_URL
- **Message bus**: uc_table (dev) with structured_logging fallback
- **Delegation**: bounded app-auth UC task/event store, lifespan worker, and payload-redacted status endpoint
- **Streaming**: events buffer and finalize before the UI renders `response.output_text.delta` only
- **Release gate**: `ToolCallCorrectness = 0.400 < 0.800`; promotion blocked
- **Workspace**: dbc-baff2b7f-4402.cloud.databricks.com (dev)

Canonical narrative references: [runtime technical specifications](../runtime-technical-specs.md), [API contracts](../api-contracts.md), [tool and model registry](../tool-and-model-registry.md), and [low-level design](../low-level-design.md).

## Ownership and Update Policy

- Primary owner: platform engineering
- Update triggers: new subagent, persona change, auth/policy change, deployment topology change
- Update these artifacts in the same PR where behavior changes.
