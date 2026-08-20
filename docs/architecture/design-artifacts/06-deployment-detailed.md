# Deployment Phase: Detailed Diagrams

This document captures detailed deployment and operations diagrams.

## 1. Network and Security Topology

```mermaid
flowchart LR
    User[Enterprise Users] --> Ingress[Databricks App Ingress — usage_policy_id]
    Ingress --> FE[React Frontend — static assets]
    FE --> BE[Backend — FastAPI + MLflow Agent Server]

    BE --> IDP[Workspace Identity — app service principal]
    BE --> OBO[OBO — x-forwarded-access-token]
    BE --> GENIE[Genie MCP — /api/2.0/mcp/genie/]
    BE --> AIS[AI Search MCP — /api/2.0/mcp/ai-search/]
    BE --> LB[Lakebase — ep-falling-cake-d1j29nc5.database.us-west-2.cloud.databricks.com]
    BE --> FM[Model Serving — databricks-claude-sonnet-4]
    BE --> UC[UC Audit Table — SQL Statement API — warehouse b20f70f71c2f52e2]

    SEC[Platform Security] --> Ingress
    SEC --> UC
```

## 2. CI/CD and Promotion Pipeline

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

## 3. Observability Architecture

```mermaid
flowchart TB
    Req[Request Lifecycle Events] --> MB[Message Bus — default_message_bus]
    Tool[Tool Lifecycle Events] --> MB
    Pol[Policy + Guardrail Decisions] --> MB

    MB --> Log[StructuredLoggingMessageBus — JSON logs]
    MB --> Kafka[KafkaMessageBus — confluent-kafka]
    MB --> Rabbit[RabbitMQMessageBus — pika]
    MB --> UCT[UcAuditTableMessageBus — SQL Statement API]

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
        V2[orchestrator_model = databricks-claude-sonnet-4]
        V3[openai_base_url = empty — direct to model serving]
        V4[message_bus_backend = uc_table]
        V5[genie_space_id = 01f159f5...]
        V6[cdi_genie_space_id = 01f19b2a...]
        V7[lakebase_project_id = 3ab05603...]
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
