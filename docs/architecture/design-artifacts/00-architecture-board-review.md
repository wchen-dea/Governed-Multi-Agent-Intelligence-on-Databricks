# Architecture Board Review

## Purpose

Use this page as the architecture review entry point. The phase artifacts are the visual source of truth; the canonical narrative facts are maintained in [runtime technical specifications](../runtime-technical-specs.md), [API contracts](../api-contracts.md), [tool and model registry](../tool-and-model-registry.md), and [low-level design](../low-level-design.md).

## Review Status

| Control plane | Current implementation state |
| --- | --- |
| Tool execution | Native function and MCP calls; the UI does not render pseudo-tool content. |
| Model routing | Deterministic standard, reasoning, and synthesis routes; dev resolves all routes to `databricks-gpt-5-6-luna`. |
| Data governance | Unity Catalog, persona policy, app/OBO authorization, output guardrails, and OAuth-only Lakebase access. |
| Delegation | Bounded app-auth handoffs with correlation IDs, idempotency, UC task/event tables, leases, retries, dead-letter states, and payload-redacted status. |
| Streaming | Execution events buffer; source and guardrails finalize before the UI renders `response.output_text.delta` only. |
| Deployment | Databricks Apps, target overlays, versioned wheel `upload-wheel` fallback, lifecycle gates, and health checks. |
| Promotion | Auth correctness, safety, and groundedness are blocking KPIs. Tool-call accuracy is monitored but non-blocking until nested tool spans are scored reliably. |

## Artifact Set

| Phase | High-level view | Detailed view |
| --- | --- | --- |
| Concept | [01 concept high level](01-concept-high-level.md) | [02 concept detailed](02-concept-detailed.md) |
| Logical | [03 logical high level](03-logical-high-level.md) | [04 logical detailed](04-logical-detailed.md) |
| Deployment | [05 deployment high level](05-deployment-high-level.md) | [06 deployment detailed](06-deployment-detailed.md) |
| Runtime | [07 request execution pipeline](07-request-execution-flow-class-diagram.md) | [08 backend class diagrams](08-backend-class-diagram-as-is.md) |

## Review Questions

1. Does each new agent, model, data source, or workflow have an explicit policy, identity, and lifecycle-audit path?
2. Does the proposed change preserve native tool execution and delta-only answer rendering?
3. Can durable delegation remain bounded by approved source, target, intent, lease, retry, and dead-letter rules?
4. Are bundle-managed grants and source-only deployment recovery distinguished in the release plan?
5. Does evaluation satisfy the blocking auth-correctness, safety, and groundedness thresholds, while tool-call accuracy is monitored and triaged?
