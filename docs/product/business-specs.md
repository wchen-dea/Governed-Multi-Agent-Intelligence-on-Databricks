# Business Specs

This document defines the business specification for the multi-agent application.

## Purpose

Align product, engineering, and operations on business goals, value, and measurable outcomes.

## Product Vision

Provide a governed enterprise AI assistant that routes requests to the right data and tools, enforces policy by default, and produces auditable responses suitable for business operations.

## Target Users

- Business users: need quick answers with clear source confidence.
- Analysts: need governed data retrieval and traceable tool usage.
- Operators: need predictable runtime behavior and incident visibility.
- Platform owners: need policy compliance and release quality gates.

## Core Business Capabilities

1. Unified conversational access to multiple specialist agents and tools.
2. Governed routing with hybrid authorization.
3. Transparent policy and guardrail enforcement.
4. Lifecycle auditability and compliance reporting.
5. Safe, repeatable multi-environment releases.

## Current Capability Boundary

| Capability | Current state | Authority |
| --- | --- | --- |
| Sales, product, Flink, CDI, and Lakebase requests | Implemented through governed native tool/MCP routes | [Tool and model registry](../architecture/tool-and-model-registry.md) |
| Bounded agent delegation | Implemented for approved app-auth tasks with UC durable state | [Runtime technical specifications](../architecture/runtime-technical-specs.md) |
| General asynchronous mailbox workflows | Target capability; not implemented | [Architecture guide](../architecture/README.md) |
| Release promotion | Blocked by `ToolCallCorrectness = 0.400 < 0.800` | [Evaluation specification](../quality/evaluation-spec.md) |

## Business Requirements

### BR-1: Governed Access

The system must enforce access policy before tool execution using identity, role/persona, and data classification constraints.

### BR-2: Explainable Safety

The system must block unsafe or low-confidence sensitive answers and provide user-facing reasons for blocked responses.

### BR-3: Audit and Compliance

The system must publish lifecycle and policy decision events and persist them to a governed store for compliance analysis.

### BR-4: Release Quality

The system must block deployment when critical quality KPIs are below thresholds.

### BR-5: Multi-Environment Consistency

The system must support dev, qa, stg, and prod environments with deterministic target configuration.

## Non-Functional Requirements

- Availability: graceful degradation when optional transports are unavailable.
- Security: no silent fallback from user-required auth to app auth.
- Observability: structured lifecycle events across request, tool, policy, and guardrail stages.
- Operability: runbook procedures for standard deploy, fallback deploy, and rollback.

## Success Metrics

- Tool-call accuracy meets release threshold.
- Authorization correctness meets release threshold.
- Safety and groundedness meet release thresholds.
- Reduction in policy violations reaching end users.
- Mean time to diagnose incidents improves using audit events.

## Scope Boundaries

In scope:

- Multi-agent orchestration on Databricks Apps
- Governance policy and response guardrails
- Lifecycle event observability and UC audit persistence
- CI quality gate enforcement

Out of scope:

- Full asynchronous message-mailbox workflows between agents
- Custom BI reporting UI for audit analytics

## Related Documents

- [Architecture guide](../architecture/README.md)
- [Runtime technical specifications](../architecture/runtime-technical-specs.md)
- [High-level architecture](../architecture/high-level-architecture.md)
- [Low-level design](../architecture/low-level-design.md)
- [Operations runbook](../operations/operations-runbook.md)
- [Architecture decision records](../adrs/README.md)
