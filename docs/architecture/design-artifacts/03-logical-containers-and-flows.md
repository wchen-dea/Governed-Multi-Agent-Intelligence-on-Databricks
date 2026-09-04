# Logical Containers and Flows

This document captures high-level logical architecture and end-to-end runtime flows.

## 1. Container Diagram

```mermaid
flowchart LR
    User[User] --> FE[React Chat UI — Vite/TS]
    FE --> API[Backend API — MLflow Agent Server]
    API --> ORCH[Orchestrator — OpenAI Agents SDK Runner]
    ORCH --> POL[Policy Service + Guardrails Service]
    ORCH --> TOOL[Tool Assembly: Adapter Registry + MCP/Lakebase Builders]
    TOOL --> GENIE[Genie MCP — sales_insights_agent / cdi_agent]
    TOOL --> AIS[AI Search MCP — product_index_assistant / flink_support_agent]
    TOOL --> LB[Lakebase — lakebase_ods_agent — psycopg2 + OAuth credentials]
    GENIE --> ST[Sales Tables — quickstart_catalog]
    GENIE --> MV[CDI Materialized Views]
    AIS --> PI[dim_product_search_index]
    AIS --> FS[flink_support_index]
    LB --> OD[Operational Data Store — appointments, orders, invoices]
    ORCH --> FM[Foundation Model — target-configured]
    FM -.-> AIGW[AI Gateway — optional base_url override]
    ORCH --> BUS[Message Bus]
    BUS --> AUDIT[UC Audit Table — quickstart_catalog.multi_agent_schema.agent_lifecycle_events]
```

## 2. End-to-End Request Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React Frontend
    participant BE as Backend Handler
    participant RA as Runtime Auth Service
    participant POL as Policy Service
    participant OR as Orchestrator Agent
    participant TL as Tool Assembly
    participant DT as Delegation Task Bus
    participant GR as Guardrails Service
    participant MB as Message Bus

    U->>FE: Send prompt with persona
    FE->>BE: POST /invocations
    BE->>MB: request.started
    BE->>RA: Build identity + policy context
    RA->>POL: Filter subagents by persona + auth
    POL-->>RA: Allowed/denied subagents
    RA-->>BE: RuntimeAuthContext
    BE->>OR: Build route plan and agent with candidate tools + MCP
    alt Direct tool or MCP execution
        OR->>TL: Resolve direct adapter or dedicated MCP/Lakebase builder
        TL->>TL: Adapter precedence: MCP, Lakebase, app, delegation
        TL-->>OR: Native function tool or connected MCP server
        OR->>TL: Native function or MCP tool call
        TL-->>OR: Tool result
    else Approved native delegation
        OR->>DT: delegate_to_agent submits named task
        DT-->>OR: Synchronous task settlement result
    end
    OR-->>BE: Response items
    BE->>BE: Buffer stream events and finalize source
    BE->>GR: Evaluate guardrails
    GR-->>BE: Pass/block decision
    BE->>MB: request.succeeded
    BE-->>FE: response.output_text.delta plus metadata
    FE-->>U: Render output-text deltas only
```

## 3. Data Flow and Lineage

```mermaid
flowchart TD
    I[User Input + Persona] --> N[Normalized Messages — to_messages]
    N --> P[Policy Decision per subagent]
    P --> T[Tool Invocation — Genie / AI Search / Lakebase]
    P --> RP[Route Plan + Response Envelope]
    T --> R[Retrieved Data]
    R --> G[LLM Response Generation]
    G --> SRC[Source Suffix — governed attribution]
    SRC --> GR[Guardrail Check]
    GR --> O[Output to User]

    N --> E1[request.invoke.started]
    P --> E2[policy.subagent.decision]
    GR --> E3[response.guardrail.passed/blocked]
    O --> E4[request.invoke.succeeded]
    E1 --> L[UC Audit Table]
    E2 --> L
    E3 --> L
    E4 --> L
```

## 4. Security and Identity Flow

```mermaid
flowchart LR
    UI[React UI Session] --> HDR[x-forwarded-access-token — optional]
    HDR --> AUTH[Runtime Auth Builder]
    AUTH --> APP[App Identity — WorkspaceClient]
    AUTH --> OBO[User OBO Identity — user WorkspaceClient]

    APP --> TOOL1[Current dev app-auth tools]
    OBO --> TOOL2[OBO-auth tools — when auth_mode=obo]

    AUTH --> POL[Policy Filter]
    POL --> ALLOW[Allowed subagents by persona]
    POL --> DENY[Denied — persona_not_allowed / obo_identity_required]
```

## Current Alignment

The logical runtime adds deterministic model routing before agent construction; dev uses `databricks-gpt-5-6-luna` for standard turns and `databricks-claude-sonnet-5` for reasoning/synthesis turns. Streams buffer and finalize before the browser renders `response.output_text.delta` only. See [API contracts](../api-contracts.md) for the client-visible contract.
