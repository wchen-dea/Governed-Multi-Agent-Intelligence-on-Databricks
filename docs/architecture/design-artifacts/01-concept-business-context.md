# Concept Business Context

This document captures high-level concept diagrams used to align stakeholders before implementation detail.

## 1. Business Capability Map

```mermaid
flowchart LR
    A[Conversational Access] --> B[Persona-Governed Routing]
    B --> C[Native Tool-Backed Response Generation]
    C --> H[Bounded Durable Delegated Handoff]
    H --> D[Evidence-Attributed Outcomes]
    D --> E[Auditable Multi-Environment Delivery]
```

## 2. Stakeholder and Actor Map

```mermaid
flowchart TB
    subgraph Business
        U1[Manager — full agent access]
        U2[Analyst — Sales Insights + Product Index + Lakebase ODS]
        U3[Operator — Flink Support only]
        U4[Engineer — Flink Support + Lakebase ODS]
    end

    subgraph Platform
        O1[Platform Engineer]
        O2[Security and Governance]
    end

    U1 --> SYS[Multi-Agent Orchestrator]
    U2 --> SYS
    U3 --> SYS
    U4 --> SYS

    O1 --> SYS
    O2 --> SYS
```

## 3. System Context Diagram

```mermaid
flowchart LR
    User[Enterprise Users] --> UI[React Chat UI]
    UI --> AISYS[AI Orchestrator — Databricks App]
    AISYS --> Genie[Genie Spaces — Sales / CDI]
    AISYS --> AIS[AI Search MCP — Product Index / Flink Support]
    AISYS --> LB[Lakebase PostgreSQL ODS OAuth-only]
    AISYS --> FM[Deterministic Model Router dev gpt-5-6-luna]
    AISYS --> AIGW[AI Gateway — optional routing layer]
    AISYS --> Audit[UC Audit Table / Message Bus]
    AISYS --> Tasks[UC Delegation Task and Event Tables]
    AISYS --> Identity[Workspace Identity — App + OBO]
```

## 4. Business Value and Decision Flow

```mermaid
flowchart TD
    Q[Business Question] --> P[Persona Resolution]
    P --> Route[Policy-Filtered Tool Selection]
    Route --> Tool[Tool Execution — Genie / AI Search / Lakebase]
    Tool --> Ans[Response with Source Attribution]
    Ans --> Guard[Guardrail Validation]
    Guard --> Action[Delivered Answer]
```

## Current Alignment

Concept views describe business intent only. Current implementation uses native function/MCP calls, payload-redacted delegation status, and buffered stream finalization before the UI renders answer deltas. See [runtime technical specifications](../runtime-technical-specs.md) for executable facts.
