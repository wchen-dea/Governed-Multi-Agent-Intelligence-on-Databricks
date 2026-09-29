# AI Systems Architecture Diagrams

The following views separate the two primary deployment patterns: a Databricks-native
AI system and an AWS Bedrock AgentCore AI system that can use Databricks data.

## 1. Databricks-native governed AI system

Use this architecture when orchestration, data permissions, retrieval, model serving,
evaluation, and audit should remain primarily inside Databricks and Unity Catalog.

```mermaid
flowchart TB
  U[Users and Applications] --> I[Enterprise IdP and OIDC]
  I --> E[Databricks Apps or API Route]
  E --> O[Databricks Agent Framework]

  subgraph Governance[Databricks Governance and Policy]
    UC[Unity Catalog Permissions]
    OBO[OBO and Service Principal Identity]
    GF[Application Guardrails and Policy Checks]
    IG[Unity AI Gateway]
  end

  subgraph Tools[Databricks Tools and Retrieval]
    UF[Unity Catalog Functions]
    MC[Managed MCP and UC Connections]
    VS[AI Search or Vector Search]
    G[Genie Spaces and Structured Data]
    DT[Delta Tables and Enterprise Data]
  end

  subgraph Models[Model and Inference]
    MS[Databricks Model Serving]
    FM[Databricks and Open Foundation Models]
    RT[Environment-aware Model Routing]
  end

  subgraph Ops[Evaluation and Operations]
    ML[MLflow Tracing and Evaluation]
    ST[System Tables and Inference Tables]
    LM[Lakehouse Monitoring and Data Quality]
    RG[Release Gates and Audit Dashboards]
  end

  O --> GF
  O --> UF
  O --> MC
  O --> VS
  O --> G
  G --> DT
  VS --> DT
  UC --> UF
  UC --> MC
  UC --> VS
  OBO --> O
  O --> RT --> IG --> MS --> FM
  O --> ML
  MS --> ML
  IG --> ST
  DT --> LM
  ML --> RG
  ST --> RG
  LM --> RG
```

## 2. AWS Bedrock AgentCore AI system

Use this architecture when the agent runtime, tool gateway, identity, memory,
policy, and operational controls should be primarily provided by AWS, while the
agent can still retrieve from Databricks or other enterprise data sources.

```mermaid
flowchart TB
  U[Users and Applications] --> I[Enterprise IdP]
  I --> API[API Gateway or Application Service]
  API --> R[AgentCore Runtime]
  API --> H[AgentCore Harness]

  subgraph AgentCore[Amazon Bedrock AgentCore]
    R
    H
    GW[AgentCore Gateway]
    MEM[AgentCore Memory]
    ID[AgentCore Identity]
    POL[AgentCore Policy]
    REG[AgentCore Registry]
    OBS[AgentCore Observability]
    EVAL[AgentCore Evaluations and Optimization]
  end

  subgraph Knowledge[Retrieval and Tools]
    KB[Managed Knowledge Bases]
    ACL[Document ACL and Permission Filtering]
    MCP[External MCP Servers]
    API2[APIs and Lambda Tools]
    DS[S3, SharePoint, Confluence, and Enterprise Sources]
    DBX[Databricks SQL, UC Functions, or MCP]
  end

  subgraph Models[Model and Safety]
    FM[Amazon Bedrock Foundation Models]
    GR[Amazon Bedrock Guardrails]
    AR[Grounding and Automated Reasoning Checks]
  end

  subgraph AWSOps[AWS Operations and Security]
    IAM[IAM and KMS]
    CW[CloudWatch and CloudTrail]
    NET[Private Networking and Secrets]
  end

  R --> H
  H --> MEM
  R --> GW
  H --> GW
  GW --> MCP
  GW --> API2
  GW --> DBX
  R --> KB
  KB --> ACL
  ACL --> DS
  KB --> FM
  R --> FM
  FM --> GR --> AR
  ID --> R
  POL --> GW
  REG --> GW
  OBS --> R
  OBS --> KB
  OBS --> EVAL
  EVAL --> R
  IAM --> ID
  IAM --> R
  NET --> R
  CW --> OBS
```

## Architecture selection

| Concern | Databricks-native system | AWS AgentCore system |
| --- | --- | --- |
| Primary agent runtime | Databricks Agent Framework | AgentCore Runtime or Harness |
| Data governance anchor | Unity Catalog | IAM, AgentCore Identity, and source ACLs |
| Retrieval | AI Search, Vector Search, Genie, and Delta | Managed Knowledge Bases, MCP, and enterprise connectors |
| Model access | Model Serving and Unity AI Gateway | Amazon Bedrock foundation models |
| Tool integration | UC Functions, managed MCP, and connections | AgentCore Gateway, APIs, Lambda, and MCP |
| Evaluation and tracing | MLflow, System Tables, and Lakehouse Monitoring | AgentCore Observability, Evaluations, CloudWatch, and CloudTrail |
| Best fit | Lakehouse-first governed AI | AWS-native agent operations and multi-framework agents |

## Shared design requirements

Both architectures should enforce identity-aware tool access, retrieval permissions,
input and output guardrails, model and prompt versioning, traceability, evaluation,
release gates, and auditable production operations.

## Reference documentation

- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Databricks AI and machine learning](https://docs.databricks.com/aws/en/machine-learning/)