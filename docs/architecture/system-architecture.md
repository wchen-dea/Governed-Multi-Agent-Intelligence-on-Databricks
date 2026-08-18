# Multiagent App on Databricks: Architecture (High Level)

## Purpose

Describe the system shape, major boundaries, and end-to-end request flow.

## Scope

This document covers high-level architecture only. Implementation-level details are in `docs/architecture/system-design.md`, and operational procedures are in `docs/operations/runbook.md`.

## Current Status

- Dev deployment is live with React UI as the primary client.
- Hosted runtime uses `uv run start-app`.
- Deployments may intermittently fail when Terraform provider registry is unreachable; direct app deploy is the operational fallback.

## Main Content

### Overview

This project is an MVP multi-agent orchestrator deployed on Databricks Apps.
It routes user requests across backend capabilities:

- Genie Agent tools (via MCP)
- Serving endpoint agents
- Optional app-based specialists

Authorization boundary:

- App identity is used for app-auth tools.
- User identity (OBO) is used for user-auth tools when a forwarded token is present.
- OBO token propagation uses `x-forwarded-access-token` from UI to backend.
- For non-interactive Databricks Apps invocation tests, use `Authorization: Bearer <token>`.

Runtime stack:

- MLflow Agent Server
- OpenAI Agents SDK
- Databricks OpenAI-compatible runtime clients
- Structured message bus events for request/tool lifecycle observability
- Optional async message-bus publishing mode to reduce request-path event I/O latency
- Governed policy and response-guardrail enforcement for sensitive routes

### Major Components

- Client: React UI static app + proxy
- Entry runtime: MLflow Agent Server (`ResponsesAgent`)
- Orchestration layer: tool selection and response composition
- Integration layer: MCP + serving endpoint calls
- Data and semantic layer: Genie Agent space, enterprise data assets

### Frameworks and Platform Stack

- FastAPI: backend API framework for agent runtime endpoints.
- Uvicorn: ASGI server for backend execution.
- MLflow Agent Server (`ResponsesAgent`): invoke/stream serving runtime.
- OpenAI Agents SDK: agent orchestration and tool-calling loop.
- Databricks OpenAI integration: Responses API client integration for Databricks-hosted models and endpoints.
- React UI (TypeScript): conversational frontend and streaming interaction layer.
- Databricks Apps: managed application hosting platform.
- Databricks Declarative Automation Bundles (DAB): deployment framework with target-based environment management.

### Deployment Diagram

```mermaid
flowchart LR
    subgraph Personas[Personas]
        P1[Business User]
        P2[Analyst]
        P3[Operator]
    end

    subgraph Client[Client UI]
        UI[React UI]
    end

    subgraph Platform[Databricks App Platform]
        AS[MLflow Agent Server ResponsesAgent]
        ORCH[Agent Orchestration Service]
        AUTH[Hybrid Auth Router auth_mode app or obo]
        MCP[MCP Integration Layer]
        LLM[Databricks-Provided LLM gpt-5.6-luna]

        APPID[App Identity Service Principal]
        OBOID[User Identity OBO Token]

        subgraph Agents[Multiple Agents]
            A1[Genie Sales Agent]
            A2[MCP Product Index Assistant AI Search]
            A3[MCP Flink Support Agent RAG]
            A4[Genie CDI Agent]
        end

        subgraph Semantic[Business Semantic Layer]
            BSL[Genie Agent Spaces / Semantic Models]
            VS[Vector Search Indexes]
        end
    end

    subgraph Data[Enterprise Data]
        KB[Support Knowledge Base Volume]
        MV[Materialized Views CDI Metrics]
        PT[Product Tables]
        ST[Sales Tables]
    end

    P1 --> UI
    P2 --> UI
    P3 --> UI

    UI --> AS
    AS --> ORCH
    ORCH --> AUTH
    AUTH -->|app| APPID
    AUTH -->|obo| OBOID
    ORCH --> A1
    ORCH --> A2
    ORCH --> A3
    ORCH --> A4

    ORCH --> LLM

    ORCH --> MCP
    APPID --> MCP
    OBOID --> MCP
    MCP --> BSL
    MCP --> VS
    BSL --> ST
    BSL --> MV
    VS --> PT
    VS --> KB

    classDef auth fill:#eef7ff,stroke:#2b6cb0,stroke-width:1px;
    class AUTH,APPID,OBOID auth;
```

### Request Flow

```mermaid
flowchart TD
    U[User]
    U --> UI[React UI]
    UI -.optional x-forwarded-access-token.-> APP
    UI --> APP[Databricks App Endpoint]
    APP --> S[MLflow Agent Server ResponsesAgent]
    S --> H[invoke_handler / stream_handler]
    H --> C[Build Runtime Identity Context]
    C --> D{Subagent auth_mode}
    D -->|app| AID[Use App Identity Client]
    D -->|obo + token| OID[Use User OBO Identity Client]
    D -->|obo + no token| ERR[Mark Tool Unavailable or Raise Auth Error]
    AID --> O[Orchestrator Agent via Responses API]
    OID --> O

    O --> G[Genie Sales Agent via MCP]
    O --> K[MCP AI Search product_index_assistant]
    O --> F[MCP AI Search flink_support_agent RAG]
    O --> CDI[Genie CDI Agent via MCP]

    G --> M[MCP Genie Space sales]
    K --> R1[Vector Search dim_product_search_index]
    F --> R3[Vector Search flink_support_search_index]
    CDI --> M2[MCP Genie Space CDI metrics]

    M --> R[Response Aggregation and Guardrails]
    R1 --> R
    R3 --> R
    M2 --> R
    ERR --> R
    R --> UI
    UI --> U

    classDef auth fill:#eef7ff,stroke:#2b6cb0,stroke-width:1px;
    class C,D,AID,OID,ERR auth;
```

### Authorization Routing

The orchestrator uses subagent-level auth configuration (`auth_mode`) to decide execution identity:

- `app`: run tool/MCP calls with app identity.
- `obo`: run tool/MCP calls with user identity derived from forwarded token.

If an `obo` tool is required but no forwarded token is available, the tool is marked unavailable or returns a clear authorization error.

### Message Bus Observability

The runtime publishes message-bus events at key orchestration points:

- Request lifecycle: invoke/stream started, succeeded, failed
- Runtime auth lifecycle: identity resolved, trace metadata updated, context built
- Policy lifecycle: subagent allow/deny decision events with reason codes
- Tool lifecycle: tool call started, succeeded, failed
- MCP lifecycle: server registered or unavailable
- Response lifecycle: guardrail pass/block decisions

Supported message bus backends:

- `structured_logging` (default)
- `noop`
- `kafka`
- `rabbitmq`
- `uc_table` for Unity Catalog-governed Delta audit persistence

Optional runtime mode:

- `MESSAGE_BUS_ASYNC=true` to enqueue lifecycle events for background publishing

### Environment Topology

| Environment | Target | Mode | Profile |
| ---- | ---- | ---- | ---- |
| Development | dev | development | dev |
| QA | qa | development | qa |
| Staging | stg | production | stg |
| Production | prod | production | prd |

## Related Docs

- `docs/product/business-specs.md`: business goals and requirements
- `docs/architecture/technical-specs.md`: centralized technical domain map
- `docs/architecture/system-design.md`: low-level implementation details
- `docs/architecture/design-artifacts/README.md`: centralized full design diagram set across concept, logical, and deployment phases
- `docs/architecture/design-artifacts/07-request-execution-flow-class-diagram.md`: simplified invoke/stream staged request execution class diagram
- `docs/operations/runbook.md`: operations and incident handling
