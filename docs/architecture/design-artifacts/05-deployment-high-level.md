# Deployment Phase: High-Level Diagrams

This document captures high-level deployment architecture across environments.

## 1. Environment Topology

```mermaid
flowchart LR
    Dev[dev] --> QA[qa]
    QA --> STG[stg]
    STG --> PRD[prod]

    Dev -. validate .-> QA
    QA -. promote .-> STG
    STG -. release .-> PRD
```

## 2. Runtime Deployment Map

```mermaid
flowchart TB
    subgraph DatabricksApp[Databricks App Runtime]
        FE[Frontend React UI]
        BE[Backend Agent Server]
    end

    FE --> BE
    BE --> MOD[Foundation Model APIs gpt-5.6-luna]
    BE --> GEN[Genie MCP Sales / CDI Spaces]
    BE --> VS[Vector Search MCP Product / Flink Support]
    BE --> AUD[Audit Storage UC Table]
    BE --> OBS[Observability / Telemetry Export]
```
