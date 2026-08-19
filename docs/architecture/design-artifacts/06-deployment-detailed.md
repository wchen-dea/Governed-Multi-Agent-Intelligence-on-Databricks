# Deployment Phase: Detailed Diagrams

This document captures detailed deployment and operations diagrams.

## 1. Network and Security Topology

```mermaid
flowchart LR
    User[Enterprise Users] --> Ingress[App Ingress]
    Ingress --> FE[Frontend Service]
    FE --> BE[Backend Service]

    BE --> IDP[Identity Provider]
    BE --> MCP[MCP and Tool Integrations]
    BE --> SEP[Serving Endpoints]
    BE --> LB[Lakebase PostgreSQL Endpoint]
    BE --> UC[UC Audit Table]

    SEC[Security Monitoring] --> Ingress
    SEC --> BE
    SEC --> UC
```

## 2. CI/CD and Promotion Pipeline

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

## 3. Observability Architecture

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

## 4. HA and DR Topology

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
