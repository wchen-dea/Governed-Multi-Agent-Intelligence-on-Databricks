# Architecture Board Review Pack

This document is the single-page review pack that embeds the complete AI system design diagram set across concept, logical, and deployment phases.

## Source Artifact Set

- [README.md](README.md)
- [01-concept-high-level.md](01-concept-high-level.md)
- [02-concept-detailed.md](02-concept-detailed.md)
- [03-logical-high-level.md](03-logical-high-level.md)
- [04-logical-detailed.md](04-logical-detailed.md)
- [05-deployment-high-level.md](05-deployment-high-level.md)
- [06-deployment-detailed.md](06-deployment-detailed.md)

## Concept Phase: High Level

### Business Capability Map

```mermaid
flowchart LR
    A[Conversational Access] --> B[Governed Routing]
    B --> C[Safe Response Generation]
    C --> D[Auditable Outcomes]
    D --> E[Reliable Multi-Environment Delivery]
```

### Stakeholder and Actor Map

```mermaid
flowchart TB
    subgraph Business
        U1[Business User]
        U2[Analyst]
        U3[Executive]
    end

    subgraph Platform
        O1[Platform Engineer]
        O2[Operator]
        O3[Security and Governance]
    end

    U1 --> SYS[AI System]
    U2 --> SYS
    U3 --> SYS

    O1 --> SYS
    O2 --> SYS
    O3 --> SYS
```

### System Context Diagram

```mermaid
flowchart LR
    User[User Channels] --> UI[Chat UI]
    UI --> AISYS[AI Orchestrator System]
    AISYS --> Genie[Genie Spaces Sales CDI]
    AISYS --> VS[Vector Search AI Search Indexes]
    AISYS --> Models[Foundation Model APIs]
    AISYS --> Audit[Audit and Observability Sinks]
    AISYS --> Identity[Identity and Authorization Services]
```

### Business Value and Decision Flow

```mermaid
flowchart TD
    Q[Business Question] --> Ctx[Context and Intent Understanding]
    Ctx --> Route[Tool and Agent Route Decision]
    Route --> Ans[Answer with Evidence]
    Ans --> Action[Business Action]
    Action --> Outcome[Measured Outcome and Feedback]
```

## Concept Phase: Detailed

### Product Scope Map

```mermaid
flowchart LR
    subgraph InScope[In Scope]
        S1[Multi-agent orchestration]
        S2[Policy and guardrails]
        S3[Audit event lifecycle]
        S4[Release quality gate]
    end

    subgraph OutScope[Out of Scope]
        O1[Custom BI dashboarding]
        O2[Long-running agent mailbox workflows]
        O3[Cross-tenant orchestration]
    end
```

### Trust Boundary and Risk Sketch

```mermaid
flowchart TB
    subgraph Zone1[User Zone]
        U[User Session]
    end

    subgraph Zone2[App Runtime Zone]
        UI[Frontend]
        ORCH[Orchestrator]
        POL[Policy and Guardrails]
    end

    subgraph Zone3[Enterprise Services Zone]
        TOOL[Tools and MCP]
        DATA[Governed Data Assets]
    end

    subgraph Zone4[Control Zone]
        AUDIT[Audit Sink]
        SEC[Security Monitoring]
    end

    U --> UI --> ORCH --> TOOL --> DATA
    ORCH --> POL
    ORCH --> AUDIT
    POL --> AUDIT
    AUDIT --> SEC

    R1[Risk: prompt injection] -.mitigate.-> POL
    R2[Risk: unauthorized access] -.mitigate.-> ORCH
    R3[Risk: untraceable output] -.mitigate.-> AUDIT
```

## Logical Phase: High Level

### Container Diagram

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
    ORCH --> BUS[Message Bus]
    BUS --> AUDIT[Audit Storage]
```

### End-to-End Request Flow

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

### Data Flow and Lineage

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

### Security and Identity Flow

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

## Logical Phase: Detailed

### Component Diagram: Backend Runtime

```mermaid
flowchart TB
    H[API Handlers] --> D[Dependency Container]
    D --> RA[Runtime Auth Service]
    D --> OR[Orchestrator Service]
    D --> PO[Policy Service]
    D --> GR[Guardrails Service]
    D --> MB[Message Bus]

    OR --> SC[Subagent Config Domain]
    OR --> TL[Tool Builders]
    OR --> MCP[MCP Server Builders]
```

### Orchestration and Tool Call Sequence

```mermaid
sequenceDiagram
    participant H as Handler
    participant RA as Runtime Auth
    participant OR as Orchestrator
    participant TS as Tool Service
    participant MB as Message Bus

    H->>MB: request.started
    H->>RA: Build auth and policy context
    RA-->>H: Allowed tools and unavailable tools
    H->>OR: Build agent with allowed tools
    OR->>TS: Execute selected tool
    TS-->>OR: Tool result
    OR-->>H: Response items
    H->>MB: request.succeeded
```

### Prompt and Policy Layering

```mermaid
flowchart TD
    A[Base System Instructions] --> B[Orchestrator Instructions]
    B --> C[Tool-specific Invocation Context]
    C --> D[Model Output]

    P1[Request-time Policy] --> G[Allowed Tool Set]
    G --> C
    D --> P2[Response-time Guardrails]
    P2 --> E[Allowed Response]
    P2 --> F[Blocked Response with Reason]
```

### Session and State Model

```mermaid
flowchart LR
    S[Chat Session] --> H[Conversation History]
    S --> T[Optional Forwarded Token]
    H --> R[Request Payload]
    T --> R
    R --> O[Orchestrator Execution]
    O --> U[Updated History]
```

### Failure and Recovery Flow

```mermaid
flowchart TD
    Start[Request Start] --> Tool{Tool Available}
    Tool -- No --> Unavailable[Return unavailable-tool behavior]
    Tool -- Yes --> Exec[Execute tool]
    Exec --> Ok{Execution OK}
    Ok -- No --> FailOpen{Fail-open enabled}
    FailOpen -- Yes --> Fallback[Use structured logging fallback and continue]
    FailOpen -- No --> Error[Return explicit error]
    Ok -- Yes --> Guard{Guardrail pass}
    Guard -- No --> Block[Return blocked response reason]
    Guard -- Yes --> Success[Return answer]
```

### Evaluation and Release Gate Flow

```mermaid
flowchart LR
    Code[Code and Config Change] --> Test[Automated Tests]
    Test --> Eval[Agent Evaluation Run]
    Eval --> KPI{KPI Thresholds Met}
    KPI -- Yes --> Promote[Deploy Promotion Allowed]
    KPI -- No --> Stop[Deployment Blocked]
```

## Deployment Phase: High Level

### Environment Topology

```mermaid
flowchart LR
    Dev[dev] --> QA[qa]
    QA --> STG[stg]
    STG --> PRD[prod]

    Dev -. validate .-> QA
    QA -. promote .-> STG
    STG -. release .-> PRD
```

### Runtime Deployment Map

```mermaid
flowchart TB
    subgraph DatabricksApp[Databricks App Runtime]
        FE[Frontend]
        BE[Backend Agent Server]
    end

    FE --> BE
    BE --> MOD[Model Serving Endpoints]
    BE --> GEN[Genie and MCP Integrations]
    BE --> AUD[Audit Storage]
    BE --> OBS[Observability Stack]
```

## Deployment Phase: Detailed

### Network and Security Topology

```mermaid
flowchart LR
    User[Enterprise Users] --> Ingress[App Ingress]
    Ingress --> FE[Frontend Service]
    FE --> BE[Backend Service]

    BE --> IDP[Identity Provider]
    BE --> MCP[MCP and Tool Integrations]
    BE --> SEP[Serving Endpoints]
    BE --> UC[UC Audit Table]

    SEC[Security Monitoring] --> Ingress
    SEC --> BE
    SEC --> UC
```

### CI/CD and Promotion Pipeline

```mermaid
flowchart TD
    Commit[Commit to Main] --> Build[Build and Static Checks]
    Build --> Unit[Unit and Integration Tests]
    Unit --> Eval[Evaluation KPI Gate]
    Eval --> Validate[Bundle Validate]
    Validate --> DeployDev[Deploy dev]
    DeployDev --> DeployQA[Deploy qa]
    DeployQA --> DeployStg[Deploy stg]
    DeployStg --> DeployProd[Deploy prod]
```

### Observability Architecture

```mermaid
flowchart TB
    Req[Request Lifecycle] --> MB[Message Bus]
    Tool[Tool Lifecycle] --> MB
    Pol[Policy and Guardrail Decisions] --> MB

    MB --> Log[Structured Logs]
    MB --> Queue[Kafka or RabbitMQ]
    MB --> UCTable[UC Audit Table]

    Log --> Dash[Dashboards and Alerts]
    Queue --> Dash
    UCTable --> Dash
```

### HA and DR Topology

```mermaid
flowchart LR
    subgraph Primary[Primary Region]
        A1[App Runtime]
        A2[Model Integrations]
        A3[Audit Storage]
    end

    subgraph Recovery[Recovery Region]
        B1[Standby Runtime]
        B2[Standby Integrations]
        B3[Replicated Audit Storage]
    end

    A1 -. failover .-> B1
    A2 -. failover .-> B2
    A3 -. replicate .-> B3
```
