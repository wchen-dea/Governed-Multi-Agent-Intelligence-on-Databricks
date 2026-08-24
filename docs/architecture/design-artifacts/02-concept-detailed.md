# Concept Phase: Detailed Diagrams

This document captures detailed concept artifacts that shape implementation boundaries and governance assumptions.

## 1. Product Scope Map

```mermaid
flowchart LR
    subgraph InScope[In Scope]
        S1[Multi-agent orchestration — 5 subagents]
        S2[Persona-based policy + response guardrails]
        S3[Lifecycle event bus — UC audit table]
        S4[Evaluation KPI release gate]
        S5[AI Gateway opt-in routing]
    end

    subgraph OutScope[Out of Scope]
        O1[Custom BI dashboarding]
        O2[Long-running agent mailbox workflows]
        O3[Cross-tenant orchestration]
        O4[Custom model fine-tuning]
    end
```

## 2. Persona-Agent Access Matrix

```mermaid
flowchart TB
    subgraph Agents
        SA[sales_insights_agent — Genie]
        CDI[cdi_agent — Genie]
        PI[product_index_assistant — AI Search]
        FS[flink_support_agent — AI Search]
        LB[lakebase_ods_agent — Lakebase]
    end

    M[manager] --> SA
    M --> CDI
    M --> PI
    M --> FS
    M --> LB

    A[analyst] --> PI
    A --> LB

    OP[operator] --> FS

    E[engineer] --> PI
    E --> FS
    E --> LB
```

## 3. Trust Boundary and Risk Sketch

```mermaid
flowchart TB
    subgraph Zone1[User Zone]
        U[User Session + Persona]
    end

    subgraph Zone2[App Runtime Zone]
        UI[React Frontend]
        ORCH[Orchestrator + OpenAI Agents SDK]
        POL[Policy Service + Guardrails Service]
    end

    subgraph Zone3[Enterprise Services Zone]
        GENIE[Genie MCP — Sales / CDI]
        AIS[AI Search MCP — Product / Flink]
        LB[Lakebase — PostgreSQL ODS]
        FM[Foundation Model Serving]
        AIGW[AI Gateway — optional]
    end

    subgraph Zone4[Control Zone]
        AUDIT[UC Audit Table]
        SEC[Security Monitoring]
    end

    U --> UI --> ORCH --> GENIE
    ORCH --> AIS
    ORCH --> LB
    ORCH --> FM
    FM -.-> AIGW
    ORCH --> POL
    ORCH --> AUDIT
    POL --> AUDIT
    AUDIT --> SEC

    R1[Risk: prompt injection] -.mitigate.-> POL
    R2[Risk: unauthorized persona access] -.mitigate.-> POL
    R3[Risk: untraceable output] -.mitigate.-> AUDIT
    R4[Risk: PII in LLM traffic] -.mitigate.-> AIGW
```
