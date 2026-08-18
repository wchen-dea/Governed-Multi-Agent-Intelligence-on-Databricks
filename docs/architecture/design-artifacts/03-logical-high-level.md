# Logical Phase: High-Level Diagrams

This document captures high-level logical architecture and end-to-end runtime flows.

## 1. Container Diagram

```mermaid
flowchart LR
    User[User] --> FE[Frontend Chat UI]
    FE --> API[Backend API Handlers]
    API --> ORCH[Orchestrator Service Responses API]
    ORCH --> POL[Policy and Guardrails]
    ORCH --> TOOL[Tool and MCP Adapter Layer]
    TOOL --> GENIE[Genie Spaces Sales CDI]
    TOOL --> VS[Vector Search AI Search Indexes]
    TOOL --> SEP[Serving Endpoints]
    VS --> KB[Support KB Volume]
    VS --> PT[Product Data]
    GENIE --> ST[Sales Tables]
    GENIE --> MV[CDI Materialized View]
    ORCH --> BUS[Message Bus]
    BUS --> AUDIT[Audit Storage]
```

## 2. End-to-End Request Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant BE as Backend Handler
    participant OR as Orchestrator
    participant TL as Tool Layer

    U->>FE: Send prompt
    FE->>BE: POST /invocations
    BE->>OR: Build runtime context
    OR->>OR: Policy checks
    OR->>TL: Call selected tool
    TL-->>OR: Tool result
    OR->>OR: Guardrail checks
    OR-->>BE: Final response
    BE-->>FE: Stream response
    FE-->>U: Render response
```

## 3. Data Flow and Lineage

```mermaid
flowchart TD
    I[User Input] --> N[Normalized Request]
    N --> P[Policy Decision]
    P --> T[Tool Invocation]
    T --> R[Retrieved Data]
    R --> G[Generated Response]
    G --> O[Output to User]

    N --> E1[Request Event]
    P --> E2[Policy Event]
    T --> E3[Tool Event]
    G --> E4[Guardrail Event]
    O --> E5[Response Event]
    E1 --> L[Lineage and Audit Store]
    E2 --> L
    E3 --> L
    E4 --> L
    E5 --> L
```

## 4. Security and Identity Flow

```mermaid
flowchart LR
    UI[UI Session] --> HDR[Forwarded Token Header Optional]
    HDR --> AUTH[Runtime Auth Builder]
    AUTH --> APP[App Identity Path]
    AUTH --> OBO[User OBO Path]

    APP --> TOOL1[App-Auth Tool Calls]
    OBO --> TOOL2[User-Auth Tool Calls]

    AUTH --> POL[Policy Decision]
    POL --> ALLOW[Allowed Tools]
    POL --> DENY[Denied Tools]
```
