# Logical Phase: Detailed Diagrams

This document captures detailed logical artifacts for engineering implementation and review.

## 1. Component Diagram: Backend Runtime

```mermaid
flowchart TB
    H[Invocation Handlers — invocations.py] --> D[Bootstrap Container — container.py]
    D --> RA[Auth Context — application/auth/context.py]
    D --> OR[Orchestration Agent — application/orchestration/agent.py]
    D --> PO[Auth Policy — application/auth/policy.py]
    D --> GR[Guardrail Checks — application/guardrails/checks.py]
    D --> MB[Messaging Bus — infrastructure/messaging/bus.py]
    D --> MR[Model Selection — application/orchestration/model.py]
    D --> DT[Delegation Policy and Task Store]
    DT --> DW[Bounded Delegation Worker]

    OR --> SC[Subagent Contracts — contracts/subagents.py]
    OR --> TL[Tool Builders — serving_endpoint / app]
    OR --> MCP[MCP Server Builders — genie / mcp]
    OR --> LB[Lakebase Tools Builder — psycopg2 + OAuth credentials]
    OR --> RP[Deterministic Routing — capability match or fallback]

    SC --> S1[sales_insights_agent — Genie — analyst, manager]
    SC --> S2[product_index_assistant — AI Search MCP — analyst, manager]
    SC --> S3[flink_support_agent — AI Search MCP RAG — analyst, operator, manager, engineer]
    SC --> S4[cdi_agent — Genie — manager only]
    SC --> S5[lakebase_ods_agent — Lakebase PostgreSQL — analyst, manager, engineer]
```

## 2. Orchestration and Tool Call Sequence

```mermaid
sequenceDiagram
    participant H as Handler
    participant RA as Runtime Auth
    participant POL as Policy Service
    participant OR as Orchestrator
    participant MCP as MCP Connector
    participant TS as Tool / Genie / Lakebase
    participant GR as Guardrails
    participant MB as Message Bus

    H->>MB: request.invoke.started
    H->>RA: Build auth context (identity + persona)
    RA->>POL: Evaluate policy per subagent
    POL-->>RA: PolicyDecision[] (allow/deny + reason)
    RA-->>H: RuntimeAuthContext (tools, mcp_servers, unavailable)
    H->>MCP: Connect healthy policy-approved MCP servers (TTL-cached)
    MCP-->>H: Connected servers + unavailable_health
    H->>OR: Build RoutePlan and candidate tools
    OR-->>H: low_confidence_fallback when intent is uncertain
    H->>OR: create_orchestrator_agent(model, candidates, servers, tools)
    OR->>TS: Native Runner tool/MCP call
    TS-->>OR: Tool results
    OR-->>H: Response items / stream events
    H->>GR: Finalize buffered stream and evaluate response budget/guardrails
    GR-->>H: GuardrailResult (blocked/reasons)
    H->>MB: response envelope (status, sources, truncation, guardrails)
    H->>MB: request.invoke.succeeded / failed
```

## 3. Policy Rules Decision Tree

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

## 4. Prompt and Policy Layering

```mermaid
flowchart TD
    A[Orchestrator System Instructions — cached per subagent config] --> B[Per-subagent system_prompt]
    B --> C[User messages — normalized via to_messages]
    C --> D[Model Router then configured Databricks model]

    P1[Request-time Policy — persona + auth_mode + classification] --> G[Allowed Tool Set]
    G --> C
    D --> SRC[Source Suffix — governed_source_suffix]
    SRC --> P2[Response-time Guardrails — evidence + unsafe patterns]
    P2 --> E[Allowed Response — pass]
    P2 --> F[Blocked Response — UserError / guardrail delta]
```

## Current Alignment

Native `delegate_to_agent` handoffs are bounded app-auth tasks. Native handoffs synchronously settle their submitted task; the optional backend lifespan worker leases queued work and status lookup remains redacted. Tool-call accuracy is monitored but non-blocking while nested tool spans cannot be scored reliably.

## 5. Session and State Model

```mermaid
flowchart LR
    S[Chat Session — React UI] --> H[Conversation History — messages array]
    S --> T[Optional Forwarded Token — /token command]
    S --> PR[Persona — /persona command]
    H --> R[ResponsesAgentRequest — POST /invocations]
    T --> R
    PR --> R
    R --> O[Orchestrator Execution — Runner.run]
    O --> U[ResponsesAgentResponse — appended to history]
```

## 6. Failure and Recovery Flow

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
    Ok -- No MCP error --> MCPErr[Log warning — extract_mcp_errors]
    Ok -- No other --> FailOpen{Message bus fail_open?}
    FailOpen -- Yes --> Fallback[Structured logging fallback — continue]
    FailOpen -- No --> Error[Raise exception]
    Ok -- Yes --> Guard{Guardrail pass?}
    Guard -- No --> Block[Invoke: raise UserError / Stream: emit block delta]
    Guard -- Yes --> Success[Return response with source suffix]
```

## 7. Evaluation and Release Gate Flow

```mermaid
flowchart LR
    Code[Code + Config Change] --> Test[pytest — unit + integration]
    Test --> Eval[agent-evaluate — MLflow evaluation]
    Eval --> KPI{KPI Thresholds Met?}
    KPI -- Yes --> Bundle[databricks bundle validate]
    Bundle --> Deploy[databricks bundle deploy -t dev]
    KPI -- No --> Stop[Promotion Blocked by auth correctness safety or groundedness]
```
