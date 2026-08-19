# Concept Phase: High-Level Diagrams

This document captures high-level concept diagrams used to align stakeholders before implementation detail.

## 1. Business Capability Map

```mermaid
flowchart LR
    A[Conversational Access] --> B[Governed Routing]
    B --> C[Safe Response Generation]
    C --> D[Auditable Outcomes]
    D --> E[Reliable Multi-Environment Delivery]
```

## 2. Stakeholder and Actor Map

```mermaid
flowchart TB
    subgraph Business
        U1[Business User]
        U2[Analyst]
        U3[Executive]
    end

    subgraph Platform
        O1[Platform Engineer]
        O2[Operator]
        O3[Security and Governance]
    end

    U1 --> SYS[AI System]
    U2 --> SYS
    U3 --> SYS

    O1 --> SYS
    O2 --> SYS
    O3 --> SYS
```

## 3. System Context Diagram

```mermaid
flowchart LR
    User[User Channels] --> UI[Chat UI]
    UI --> AISYS[AI Orchestrator System]
    AISYS --> Genie[Genie Spaces Sales CDI]
    AISYS --> VS[Vector Search AI Search Indexes]
    AISYS --> LB[Lakebase PostgreSQL ODS]
    AISYS --> Models[Foundation Model APIs]
    AISYS --> Audit[Audit and Observability Sinks]
    AISYS --> Identity[Identity and Authorization Services]
```

## 4. Business Value and Decision Flow

```mermaid
flowchart TD
    Q[Business Question] --> Ctx[Context and Intent Understanding]
    Ctx --> Route[Tool and Agent Route Decision]
    Route --> Ans[Answer with Evidence]
    Ans --> Action[Business Action]
    Action --> Outcome[Measured Outcome and Feedback]
```
