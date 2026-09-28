# AI Systems Architecture Diagram

The diagram represents a current AWS and Databricks hybrid architecture for governed,
tool-using, retrieval-augmented AI systems. It treats **Amazon Bedrock AgentCore**
and the **Databricks Agent Framework** as complementary runtimes.

```mermaid
flowchart TB
  subgraph L1[User and Channel Layer]
    U1[Business Users]
    U2[Internal Web Apps]
    U3[Databricks Apps]
    U4[Service Portals and APIs]
  end

  subgraph L2[Application, API, and Identity Layer]
    A1[Enterprise IdP and OIDC]
    A2[API Gateway or Databricks App Route]
    A3[Lambda, ECS, EKS, or Databricks Services]
    A4[Rate Limits and Request Logging]
    A5[User and Workload Identity]
  end

  subgraph L3[Agent Runtime and Orchestration Layer]
    O1[Databricks Agent Framework]
    O2[Bedrock AgentCore Runtime]
    O3[AgentCore Harness]
    O4[Prompt, Route, and Policy Engine]
    O5[Tool and Agent Registry]
    O6[AgentCore Memory]
    O7[Managed MCP and A2A Tools]
  end

  subgraph L4[Tools, Retrieval, and Knowledge Layer]
    T1[Unity Catalog Functions and Connections]
    T2[Databricks AI Search or Vector Search]
    T3[Amazon Bedrock Managed Knowledge Bases]
    T4[Amazon Bedrock AgentCore Gateway]
    T5[OpenSearch Serverless, Aurora, or Neptune]
    T6[Delta Lake, S3, and Enterprise Sources]
    T7[ACL, Entitlement, and Metadata Filters]
  end

  subgraph L5[Data, Streaming, and Semantic Layer]
    D1[Amazon MSK]
    D2[Managed Flink or Spark Structured Streaming]
    D3[AWS Glue and Batch Pipelines]
    D4[Delta Tables, Features, Embeddings, and Graphs]
    D5[Unity Catalog Governance Catalog]
    D6[Lakehouse Monitoring and Data Quality]
  end

  subgraph L6[Model and Inference Layer]
    M1[Databricks Model Serving]
    M2[Unity AI Gateway]
    M3[Databricks and Open Foundation Models]
    M4[Amazon Bedrock Foundation Models]
    M5[Model Routing and Runtime Context]
  end

  subgraph L7[Governance, Safety, and Security Layer]
    G1[AWS IAM, AgentCore Identity, and Entitlements]
    G2[Databricks OBO, Service Principals, and UC Permissions]
    G3[KMS, Secrets, Private Networking, and Key Policies]
    G4[Bedrock Guardrails]
    G5[AgentCore Policy and Tool Authorization]
    G6[Databricks Guardrails and Application Policy Checks]
    G7[Row Filters, Column Masks, and ACLs]
    G8[Audit Logs, Inference Tables, and Lineage]
  end

  subgraph L8[Evaluation, Observability, and Operations Layer]
    P1[MLflow Tracing and Evaluation]
    P2[Databricks System Tables and Inference Tables]
    P3[AgentCore Observability and Traces]
    P4[AgentCore Evaluations and Optimization]
    P5[CloudWatch and CloudTrail]
    P6[Dashboards, Alerts, Runbooks, and Release Gates]
  end

  U1 --> A2
  U2 --> A2
  U3 --> A2
  U4 --> A2
  A1 --> A5 --> A2
  A2 --> A3 --> A4 --> O4

  O4 --> O1
  O4 --> O2
  O2 --> O3
  O3 --> O6
  O1 --> O5
  O2 --> O5
  O5 --> O7

  O1 --> T1
  O1 --> T2
  O2 --> T4
  O7 --> T4
  O7 --> T1
  T7 --> T2
  T7 --> T3
  T2 --> T6
  T3 --> T6
  T3 --> T5
  T4 --> T5
  T1 --> D5

  O1 --> M5
  O2 --> M5
  M5 --> M2
  M5 --> M4
  M2 --> M1
  M1 --> M3
  M4 --> M3
  T2 --> M5
  T3 --> M5

  D1 --> D2 --> D4
  D3 --> D4
  D5 --> D4
  D4 --> T2
  D4 --> T3
  D6 --> D5

  G1 --> A2
  G1 --> O2
  G2 --> O1
  G2 --> T1
  G3 --> M1
  G3 --> M4
  G4 --> M4
  G4 --> O2
  G5 --> T4
  G5 --> O5
  G6 --> O1
  G7 --> T7
  G8 --> P2

  O1 --> P1
  M1 --> P1
  M2 --> P2
  O2 --> P3
  T3 --> P3
  P3 --> P4
  P1 --> P4
  P1 --> P6
  P2 --> P6
  P3 --> P6
  P4 --> P6
  P5 --> P6
  A4 --> P6
```

## Current platform notes

- **Amazon Bedrock AgentCore** provides modular Runtime, Gateway, Identity, Memory,
  Policy, Registry, and Observability capabilities for agents built with supported
  frameworks and models. AgentCore Gateway can expose APIs, Lambda functions, and
  existing MCP servers as agent tools.
- **Amazon Bedrock Managed Knowledge Bases** support managed ingestion, indexing,
  retrieval, multimodal data, agentic retrieval, document-level permission filtering,
  citations, and AgentCore Gateway and Observability integration.
- **Amazon Bedrock Guardrails** can filter harmful content, denied topics, custom
  words, sensitive information, ungrounded responses, and responses that fail
  configured automated-reasoning checks.
- **Databricks Agent Framework** remains the Databricks-native orchestration boundary,
  with Unity Catalog-backed tools and data permissions, AI Search or Vector Search,
  Model Serving, MLflow tracing and evaluation, and application-level guardrails.
- **Bedrock Agents Classic** should be shown only when maintaining an existing
  deployment; AWS documentation identifies it as unavailable to new customers and
  directs new implementations toward AgentCore.

## Reference documentation

- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Databricks AI and machine learning](https://docs.databricks.com/aws/en/machine-learning/)