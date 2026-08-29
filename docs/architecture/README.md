# Architecture Guide

## Purpose

This guide is the entry point for the architecture corpus. It separates authoritative implementation documents from visual artifacts so readers can find the right level of detail without treating diagrams, runbooks, and specifications as competing sources of truth.

## Read By Role

| Reader | Start here | Then use |
| --- | --- | --- |
| AI executive | [High-level architecture](high-level-architecture.md) | [Architecture board review](design-artifacts/00-architecture-board-review.md), [evaluation specification](../quality/evaluation-spec.md) |
| AI architect | [Runtime technical specifications](runtime-technical-specs.md) | [Low-level design](low-level-design.md), [backend framework design](backend-framework-design.md) |
| Application engineer | [API contracts](api-contracts.md) | [Tool and model registry](tool-and-model-registry.md), [request execution diagram](design-artifacts/07-request-execution-flow-class-diagram.md) |
| Platform operator | [Operations runbook](../operations/operations-runbook.md) | [Deployment diagrams](design-artifacts/05-deployment-high-level.md), [06 deployment detailed](design-artifacts/06-deployment-detailed.md) |

## Authority Map

| Document | Authority |
| --- | --- |
| [Runtime technical specifications](runtime-technical-specs.md) | Current implementation facts, model routes, delegation, release state |
| [API contracts](api-contracts.md) | External request, stream, and delegation-status behavior |
| [Tool and model registry](tool-and-model-registry.md) | Active dev tools, MCP routes, Lakebase configuration, and model routes |
| [Semantics layer design](semantics-layer-design.md) | Semantics layer scope, ownership boundaries, and build pipelines for AI Search indexes and Metric Views |
| [High-level architecture](high-level-architecture.md) | System boundaries, trust model, and end-to-end control planes |
| [Low-level design](low-level-design.md) | Module responsibilities, request lifecycle, configuration, and implementation patterns |
| [Human-in-the-loop approval](../governance/human-in-the-loop.md) | Approval states, manager decision API, persistence, and dispatch boundary |
| [Backend framework design](backend-framework-design.md) | Backend package layout, dependency composition, staged execution, and service responsibilities |
| [Design artifacts](design-artifacts/README.md) | Visual views of the canonical architecture, not independent implementation specifications |

## Current Control Planes

- **Tool execution:** native function and MCP calls; user-visible text is rendered only from finalized `response.output_text.delta` events.
- **Model routing:** deterministic standard, reasoning, and synthesis classification; dev uses `databricks-gpt-5-6-luna` for standard turns and `databricks-claude-sonnet-5` for reasoning/synthesis turns.
- **Data and identity:** Unity Catalog governance, app/OBO authorization, persona policy, response guardrails, and OAuth-only Lakebase access.
- **Delegation:** bounded app-auth handoffs with UC task/event tables, leases, retries, dead-letter states, lifespan worker execution, and redacted status.
- **Delivery and quality:** versioned-wheel `upload-wheel` recovery, bundle-managed resource controls, and MLflow evaluation with blocking auth-correctness, safety, and groundedness thresholds. Tool-call accuracy remains monitored but non-blocking until nested tool spans are scored reliably.

## Visual Reading Order

1. [Architecture board review](design-artifacts/00-architecture-board-review.md)
2. [Concept high level](design-artifacts/01-concept-high-level.md)
3. [Logical high level](design-artifacts/03-logical-high-level.md)
4. [Logical detailed](design-artifacts/04-logical-detailed.md)
5. [Request execution pipeline](design-artifacts/07-request-execution-flow-class-diagram.md)
6. [Backend class diagrams](design-artifacts/08-backend-class-diagram-as-is.md)
7. [Deployment high level](design-artifacts/05-deployment-high-level.md)
8. [Deployment detailed](design-artifacts/06-deployment-detailed.md)
