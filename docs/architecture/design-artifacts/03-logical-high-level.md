# Logical Phase: High-Level Diagrams

This document captures high-level logical architecture and end-to-end runtime flows.

## 1. Container Diagram

```mermaid
flowchart LR
    User[User] --> FE[React Chat UI — Vite/TS]
    FE --> API[Backend API — MLflow Agent Server]
    API --> ORCH[Orchestrator — OpenAI Agents SDK Runner]
    ORCH --> POL[Policy Service + Guardrails Service]
    ORCH --> TOOL[Tool + MCP Adapter Layer]
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
    participant TL as Tool Layer
    participant GR as Guardrails Service
    participant MB as Message Bus

    U->>FE: Send prompt with persona
    FE->>BE: POST /invocations
    BE->>MB: request.started
    BE->>RA: Build identity + policy context
    RA->>POL: Filter subagents by persona + auth
    POL-->>RA: Allowed/denied subagents
    RA-->>BE: RuntimeAuthContext
    BE->>OR: Build Agent with allowed tools + MCP
    OR->>TL: Execute selected tool
    TL-->>OR: Tool result
    OR-->>BE: Response items
    BE->>GR: Evaluate guardrails
    GR-->>BE: Pass/block decision
    BE->>MB: request.succeeded
    BE-->>FE: Stream/invoke response
    FE-->>U: Render response with source
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
    P --> E2[runtime_auth.policy.denied]
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

    APP --> TOOL1[App-auth tools — all current subagents]
    OBO --> TOOL2[OBO-auth tools — when auth_mode=obo]

    AUTH --> POL[Policy Filter]
    POL --> ALLOW[Allowed subagents by persona]
    POL --> DENY[Denied — persona_not_allowed / obo_identity_required]
```
