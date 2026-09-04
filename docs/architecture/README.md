# Architecture Guide

## Purpose

This guide is the entry point for the architecture corpus. It separates authoritative implementation documents from visual artifacts so readers can find the right level of detail without treating diagrams, runbooks, and specifications as competing sources of truth.

## Read By Role

| Reader | Start here | Then use |
| --- | --- | --- |
| AI executive | [High-level architecture](high-level-architecture.md) | [Implementation review checklist](design-artifacts/00-architecture-review-checklist.md), [evaluation specification](../quality/evaluation-spec.md) |
| AI architect | [Runtime technical specifications](runtime-technical-specs.md) | [Runtime behavior and implementation](runtime-behavior-and-implementation.md), [backend package structure and layers](backend-package-structure-and-layers.md) |
| Application engineer | [API contracts](api-contracts.md) | [Tool and model registry](tool-and-model-registry.md), [request execution diagram](design-artifacts/07-runtime-invocation-stream-pipeline.md) |
| Platform operator | [Operations runbook](../operations/operations-runbook.md) | [Deployment diagrams](design-artifacts/05-deployment-topology-and-resources.md), [06 deployment detailed](design-artifacts/06-deployment-network-cicd-observability.md) |

## Authority Map

| Document | Authority |
| --- | --- |
| [Runtime technical specifications](runtime-technical-specs.md) | Current implementation facts, model routes, delegation, release state |
| [API contracts](api-contracts.md) | External request, stream, and delegation-status behavior |
| [Tool and model registry](tool-and-model-registry.md) | Active dev tools, MCP routes, Lakebase configuration, and model routes |
| [Semantics layer design](semantics-layer-design.md) | Semantics layer scope, ownership boundaries, and build pipelines for AI Search indexes and Metric Views |
| [High-level architecture](high-level-architecture.md) | System boundaries, trust model, and end-to-end control planes |
| [Runtime behavior and implementation](runtime-behavior-and-implementation.md) | Module responsibilities, request lifecycle, configuration, and implementation patterns |
| [Human-in-the-loop approval](../governance/human-in-the-loop.md) | Approval states, manager decision API, persistence, and dispatch boundary |
| [Backend package structure and layers](backend-package-structure-and-layers.md) | Backend package layout, dependency composition, staged execution, and service responsibilities |
| [Design artifacts](design-artifacts/README.md) | Visual views of the canonical architecture, not independent implementation specifications |

## Current Control Planes

- **Tool execution:** native function and MCP calls; user-visible text is rendered only from finalized `response.output_text.delta` events.
- **Model routing:** deterministic standard, reasoning, and synthesis classification; dev uses `databricks-gpt-5-6-luna` for standard turns and `databricks-claude-sonnet-5` for reasoning/synthesis turns.
- **Data and identity:** Unity Catalog governance, app/OBO authorization, persona policy, response guardrails, and OAuth-only Lakebase access.
- **Delegation:** bounded app-auth handoffs with UC task/event tables, leases, retries, dead-letter states, lifespan worker execution, and redacted status.
- **Delivery and quality:** versioned-wheel `upload-wheel` recovery, bundle-managed resource controls, and MLflow evaluation with blocking auth-correctness, safety, and groundedness thresholds. Tool-call accuracy remains monitored but non-blocking until nested tool spans are scored reliably.

## Visual Reading Order

1. [Implementation review checklist](design-artifacts/00-architecture-review-checklist.md)
2. [Concept business context](design-artifacts/01-concept-business-context.md)
3. [Logical containers and flows](design-artifacts/03-logical-containers-and-flows.md)
4. [Logical components, policy, and evaluation](design-artifacts/04-logical-components-policy-evaluation.md)
5. [Runtime invocation and stream pipeline](design-artifacts/07-runtime-invocation-stream-pipeline.md)
6. [Runtime domain model](design-artifacts/08-runtime-domain-model.md)
7. [Deployment topology and resources](design-artifacts/05-deployment-topology-and-resources.md)
8. [Deployment network, CI/CD, and observability](design-artifacts/06-deployment-network-cicd-observability.md)
