# Deployment Phase: High-Level Diagrams

This document captures high-level deployment architecture across environments.

## 1. Environment Topology

```mermaid
flowchart LR
    Dev[dev — dbc-baff2b7f-4402] --> QA[qa]
    QA --> STG[stg]
    STG --> PRD[prod]

    Dev -. bundle validate .-> QA
    QA -. bundle deploy .-> STG
    STG -. release gate .-> PRD
```

## 2. Runtime Deployment Map

```mermaid
flowchart TB
    subgraph DatabricksApp[Databricks App — multiagent-app-dev]
        FE[React Chat UI — Vite build]
        BE[Backend — MLflow Agent Server — uvicorn]
    end

    FE --> BE
    BE --> FM[Foundation Model — databricks-claude-sonnet-4]
    FM -.-> AIGW[AI Gateway — optional DATABRICKS_OPENAI_BASE_URL]
    BE --> GENIE[Genie MCP — Sales Space / CDI Space]
    BE --> AIS[AI Search MCP — Product Index / Flink Support Index]
    BE --> LB[Lakebase PostgreSQL — ep-falling-cake-d1j29nc5]
    BE --> AUD[UC Audit Table — quickstart_catalog.multi_agent_schema.agent_lifecycle_events]
    BE --> OBS[MLflow Tracing — experiment 2041388166228723]
```

## 3. Subagent Resource Mapping (dev)

```mermaid
flowchart TB
    subgraph GenieSpaces
        S1[sales_insights_agent — space 01f159f5...]
        S2[cdi_agent — space 01f19b2a...]
    end

    subgraph AISearchMCP
        S3[product_index_assistant — dim_product_search_index]
        S4[flink_support_agent — flink_support_index]
    end

    subgraph Lakebase
        S5[lakebase_ods_agent — operationaldatastore DB]
    end

    BE[Backend] --> S1
    BE --> S2
    BE --> S3
    BE --> S4
    BE --> S5
```
