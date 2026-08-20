# Architecture Board Review Pack

Single-page review pack embedding the complete AI system design across concept, logical, and deployment phases. Reflects current implementation as of the active codebase.

## Source Artifact Set

- [01-concept-high-level.md](01-concept-high-level.md)
- [02-concept-detailed.md](02-concept-detailed.md)
- [03-logical-high-level.md](03-logical-high-level.md)
- [04-logical-detailed.md](04-logical-detailed.md)
- [05-deployment-high-level.md](05-deployment-high-level.md)
- [06-deployment-detailed.md](06-deployment-detailed.md)

---

## Concept Phase: High Level

### Business Capability Map

```mermaid
flowchart LR
    A[Conversational Access] --> B[Persona-Governed Routing]
    B --> C[Tool-Backed Response Generation]
    C --> D[Evidence-Attributed Outcomes]
    D --> E[Auditable Multi-Environment Delivery]
```

### Stakeholder and Actor Map

```mermaid
flowchart TB
    subgraph Business
        U1[Manager — full agent access]
        U2[Analyst — Product Index + Lakebase ODS]
        U3[Operator — Flink Support only]
        U4[Engineer — Product Index + Flink Support + Lakebase ODS]
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

### System Context Diagram

```mermaid
flowchart LR
    User[Enterprise Users] --> UI[React Chat UI]
    UI --> AISYS[AI Orchestrator — Databricks App]
    AISYS --> Genie[Genie Spaces — Sales / CDI]
    AISYS --> AIS[AI Search MCP — Product Index / Flink Support]
    AISYS --> LB[Lakebase PostgreSQL — ODS]
    AISYS --> FM[Foundation Models — databricks-claude-sonnet-4]
    AISYS --> AIGW[AI Gateway — optional]
    AISYS --> Audit[UC Audit Table / Message Bus]
    AISYS --> Identity[Workspace Identity — App + OBO]
```

---

## Concept Phase: Detailed

### Persona-Agent Access Matrix

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

### Trust Boundary and Risk Sketch

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
        LBZ[Lakebase — PostgreSQL ODS]
        FM[Foundation Model Serving]
        AIGW[AI Gateway — optional]
    end

    subgraph Zone4[Control Zone]
        AUDIT[UC Audit Table]
        SEC[Security Monitoring]
    end

    U --> UI --> ORCH --> GENIE
    ORCH --> AIS
    ORCH --> LBZ
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

---

## Logical Phase: High Level

### Container Diagram

```mermaid
flowchart LR
    User[User] --> FE[React Chat UI — Vite/TS]
    FE --> API[Backend API — MLflow Agent Server]
    API --> ORCH[Orchestrator — OpenAI Agents SDK Runner]
    ORCH --> POL[Policy Service + Guardrails Service]
    ORCH --> TOOL[Tool + MCP Adapter Layer]
    TOOL --> GENIE[Genie MCP — sales_insights / cdi]
    TOOL --> AIS[AI Search MCP — product_index / flink_support]
    TOOL --> LB[Lakebase — lakebase_ods — psycopg2 + OAuth]
    ORCH --> FM[Foundation Model — databricks-claude-sonnet-4]
    FM -.-> AIGW[AI Gateway — optional]
    ORCH --> BUS[Message Bus]
    BUS --> AUDIT[UC Audit Table]
```

### End-to-End Request Flow

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

### Security and Identity Flow

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

---

## Logical Phase: Detailed

### Component Diagram: Backend Runtime

```mermaid
flowchart TB
    H[API Handlers — handlers.py] --> D[Dependency Container — dependencies.py]
    D --> RA[Runtime Auth Service]
    D --> OR[Orchestrator Service]
    D --> PO[Policy Service]
    D --> GR[Guardrails Service]
    D --> MB[Message Bus]

    OR --> SC[Subagent Config — subagent_config.py]
    OR --> TL[Tool Builders — serving_endpoint / app]
    OR --> MCP[MCP Server Builders — genie / mcp]
    OR --> LB[Lakebase Tools Builder — psycopg2 + OAuth]

    SC --> S1[sales_insights_agent — Genie — manager only]
    SC --> S2[product_index_assistant — AI Search — analyst, manager, engineer]
    SC --> S3[flink_support_agent — AI Search — operator, manager, engineer]
    SC --> S4[cdi_agent — Genie — manager only]
    SC --> S5[lakebase_ods_agent — Lakebase — analyst, manager, engineer]
```

### Policy Rules Decision Tree

```mermaid
flowchart TD
    Start[Per-subagent evaluation] --> HasPersona{Persona set?}
    HasPersona -- No --> PR[persona_required — block if subagent restricts]
    HasPersona -- Yes --> InList{Persona in allowed_personas?}
    InList -- No --> PNA[persona_not_allowed — block]
    InList -- Yes --> AuthMode{auth_mode = obo?}
    AuthMode -- Yes --> HasToken{Forwarded token present?}
    HasToken -- No --> OBO[obo_identity_required — block]
    HasToken -- Yes --> Confidence
    AuthMode -- No --> Confidence{Confidence check needed?}
    Confidence -- Yes --> ConfOK{confidence >= 0.75?}
    ConfOK -- No --> LCS[low_confidence_sensitive — block]
    ConfOK -- Yes --> Allow[ALLOWED]
    Confidence -- No --> Allow
```

### Failure and Recovery Flow

```mermaid
flowchart TD
    Start[Request Start] --> MCP{MCP Health Check}
    MCP -- Unhealthy --> Cache[Cache failure 10s TTL — add to unavailable]
    MCP -- Healthy --> Cache2[Cache success 30s TTL]
    Cache --> Tool{Other tools available?}
    Cache2 --> Tool
    Tool -- None --> NoTool[Run without tools — LLM-only response]
    Tool -- Yes --> Exec[Execute via Runner]
    Exec --> Ok{Execution OK?}
    Ok -- No --> FailOpen{Message bus fail_open?}
    FailOpen -- Yes --> Fallback[Structured logging fallback — continue]
    FailOpen -- No --> Error[Raise exception]
    Ok -- Yes --> Guard{Guardrail pass?}
    Guard -- No --> Block[Invoke: raise UserError / Stream: emit block delta]
    Guard -- Yes --> Success[Return response with source suffix]
```

---

## Deployment Phase: High Level

### Environment Topology

```mermaid
flowchart LR
    Dev[dev — dbc-baff2b7f-4402] --> QA[qa]
    QA --> STG[stg]
    STG --> PRD[prod]

    Dev -. bundle validate .-> QA
    QA -. bundle deploy .-> STG
    STG -. release gate .-> PRD
```

### Runtime Deployment Map

```mermaid
flowchart TB
    subgraph DatabricksApp[Databricks App — multiagent-app-dev]
        FE[React Chat UI — Vite build]
        BE[Backend — MLflow Agent Server — uvicorn]
    end

    FE --> BE
    BE --> FM[Foundation Model — databricks-claude-sonnet-4]
    FM -.-> AIGW[AI Gateway — optional]
    BE --> GENIE[Genie MCP — Sales / CDI Spaces]
    BE --> AIS[AI Search MCP — Product Index / Flink Support]
    BE --> LB[Lakebase PostgreSQL — ODS]
    BE --> AUD[UC Audit Table]
    BE --> OBS[MLflow Tracing]
```

---

## Deployment Phase: Detailed

### CI/CD and Promotion Pipeline

```mermaid
flowchart TD
    Commit[Commit to main] --> Lint[Static Checks — ruff / mypy]
    Lint --> Unit[pytest — test_*.py]
    Unit --> Eval[make evaluate — MLflow KPI gate]
    Eval --> Validate[databricks bundle validate -t dev]
    Validate --> DeployDev[make deploy — dev target]
    DeployDev --> Smoke[make test-deployed — health + invoke check]
    Smoke --> DeployQA[bundle deploy -t qa]
    DeployQA --> DeployStg[bundle deploy -t stg]
    DeployStg --> DeployProd[bundle deploy -t prod]
```

### Observability Architecture

```mermaid
flowchart TB
    Req[Request Lifecycle Events] --> MB[Message Bus]
    Tool[Tool Lifecycle Events] --> MB
    Pol[Policy + Guardrail Decisions] --> MB

    MB --> Log[StructuredLoggingMessageBus]
    MB --> Kafka[KafkaMessageBus]
    MB --> Rabbit[RabbitMQMessageBus]
    MB --> UCT[UcAuditTableMessageBus]

    UCT --> Delta[quickstart_catalog.multi_agent_schema.agent_lifecycle_events]
    Trace[MLflow Tracing] --> Exp[MLflow Experiment]
    Delta --> Dash[Dashboards and Alerts]
    Exp --> Dash
```
