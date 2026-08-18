# Logical Phase: Detailed Diagrams

This document captures detailed logical artifacts for engineering implementation and review.

## 1. Component Diagram: Backend Runtime

```mermaid
flowchart TB
    H[API Handlers] --> D[Dependency Container]
    D --> RA[Runtime Auth Service]
    D --> OR[Orchestrator Service]
    D --> PO[Policy Service]
    D --> GR[Guardrails Service]
    D --> MB[Message Bus]

    OR --> SC[Subagent Config Domain]
    OR --> TL[Tool Builders serving_endpoint/app]
    OR --> MCP[MCP Server Builders genie/mcp]
    OR --> LB[Lakebase Tool Builders lakebase]

    SC --> S1[sales_insights_agent Genie]
    SC --> S2[product_index_assistant MCP AI Search]
    SC --> S3[flink_support_agent MCP AI Search RAG]
    SC --> S4[cdi_agent Genie]
    SC --> S5[lakebase_ods_agent Lakebase PostgreSQL]
```

## 2. Orchestration and Tool Call Sequence

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

## 3. Prompt and Policy Layering

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

## 4. Session and State Model

```mermaid
flowchart LR
    S[Chat Session] --> H[Conversation History]
    S --> T[Optional Forwarded Token]
    H --> R[Request Payload]
    T --> R
    R --> O[Orchestrator Execution]
    O --> U[Updated History]
```

## 5. Failure and Recovery Flow

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

## 6. Evaluation and Release Gate Flow

```mermaid
flowchart LR
    Code[Code and Config Change] --> Test[Automated Tests]
    Test --> Eval[Agent Evaluation Run]
    Eval --> KPI{KPI Thresholds Met}
    KPI -- Yes --> Promote[Deploy Promotion Allowed]
    KPI -- No --> Stop[Deployment Blocked]
```
