# Deployment Network, CI/CD, and Observability

This document captures detailed deployment and operations diagrams.

## 1. Network and Security Topology

```mermaid
flowchart LR
    User[Enterprise Users] --> Ingress[Databricks App Ingress — usage_policy_id]
    Ingress --> FE[React Frontend — static assets]
    FE --> BE[Backend — FastAPI + MLflow Agent Server]

    BE --> IDP[Workspace Identity — app service principal]
    BE --> OBO[OBO — x-forwarded-access-token]
    BE --> ASM[Tool Assembly — Adapter Registry + Dedicated Builders]
    ASM --> GENIE[Genie MCP — /api/2.0/mcp/genie/]
    ASM --> AIS[AI Search MCP — /api/2.0/mcp/ai-search/]
    ASM --> LB[Lakebase — projects/ore/branches/production/databases/operations]
    ASM --> APP[App Endpoint — hitl-app-agent]
    BE --> OAuth[Postgres Credentials API — OAuth database token]
    BE --> TASKS[UC Delegation Task and Event Tables]
    BE --> STATUS[GET delegations task status payload-redacted]
    BE --> MR[Deterministic Model Router dev gpt-5-6-luna]
    MR --> FM[Configured Databricks Model Serving]
    BE --> UC[UC Audit Table — SQL Statement API — warehouse b20f70f71c2f52e2]

    SEC[Platform Security] --> Ingress
    SEC --> UC
```

## 2. CI/CD and Promotion Pipeline

```mermaid
flowchart TD
    Commit[Pull request or target branch push] --> Lint[Static Checks — ruff]
    Lint --> Unit[pytest — test_*.py]
    Unit --> Eval[make evaluate — MLflow KPI gate]
    Eval --> Decision{All required KPIs pass?}
    Decision -- No --> Block[Block promotion — auth correctness safety or groundedness]
    Decision -- Yes --> Validate[databricks bundle validate -t dev]
    Validate --> DeployDev[make redeploy or make upload-wheel — dev target]
    DeployDev --> Smoke[make health and make smoke]
    Smoke --> DeployQA[bundle deploy -t qa]
    DeployQA --> DeployStg[bundle deploy -t stg]
    DeployStg --> DeployProd[bundle deploy -t prd]
```

## 3. Observability Architecture

```mermaid
flowchart TB
    Req[Request Lifecycle Events] --> MB[Message Bus — default_message_bus]
    Tool[Tool Lifecycle Events] --> MB
    Pol[Policy + Guardrail Decisions] --> MB

    MB --> Select{Configured backend}
    Select --> Log[structured_logging — JSON logs]
    Select --> Kafka[kafka — confluent-kafka]
    Select --> Rabbit[rabbitmq — pika]
    Select --> UCT[uc_table — SQL Statement API]

    UCT --> Delta[quickstart_catalog.multi_agent_schema.agent_lifecycle_events]
    Delta --> Dash[Dashboards and Alerts]

    Trace[MLflow Tracing — openai.autolog] --> Exp[MLflow Experiment]
    Exp --> Dash
```

## 4. Bundle Variable Configuration (dev target)

```mermaid
flowchart LR
    subgraph BundleVars[databricks.yml + targets/dev.yml]
        V1[app_name = multiagent-app-dev]
        V2[orchestrator_model = target-configured model]
        V3[openai_base_url = empty — direct to model serving]
        V4[message_bus_backend = uc_table]
        V5[genie_space_id = 01f159f5...]
        V6[cdi_genie_space_id = 01f19b2a...]
        V7[lakebase_project_id = ore]
        V8[lakebase_branch_id = production]
        V9[lakebase_database = operations]
        V10[Lakebase postgres resource grant]
        V11[message_bus_async = false — optional fail-open queue]
        V12[agent_task_backend and worker_enabled]
        V13[model_routing_enabled and route models]
        V14[memory_backend and response budgets]
    end

    BundleVars --> App[Databricks App Environment Variables]
    App --> BE[Backend Runtime — get_settings]
```

## 5. HA and Recovery

```mermaid
flowchart LR
    subgraph Runtime[App Runtime]
        A1[Backend — auto-restart on crash]
        A2[MCP Health Cache — 30s success / 10s failure TTL]
        A3[Message Bus — fail_open fallback to structured_logging]
    end

    subgraph Platform[Platform Managed]
        B1[Model Serving — HA by Databricks]
        B2[Genie Spaces — HA by Databricks]
        B3[UC Audit Table — Delta reliability]
    end

    A2 -. degrade gracefully .-> A1
    A3 -. fallback .-> A1
```

## Current Alignment

The backend lifespan owns the optional bounded delegation worker. UC delegation state is fail-closed, uses leases and dead-letter states, and requires explicit warehouse/schema/table permissions. Auth correctness, safety, and groundedness block promotion; tool-call accuracy remains monitored but non-blocking while nested tool spans cannot be scored reliably.
