# AI Technologies and Patterns

## Purpose

Provide a concise, current inventory of the AI frameworks, architectural patterns, tools, skills, and governance controls used by this project. This is an implementation summary; use the linked documents for configuration, operations, and detailed contracts.

## AI Frameworks and Runtime

| Technology | Usage in this project |
| --- | --- |
| Databricks Apps | Hosts the backend and bundled React UI as the managed application runtime. |
| MLflow Agent Server | Exposes the Responses-compatible invoke and stream API. |
| OpenAI Agents SDK | Runs the orchestrator agent loop, native function tools, MCP tools, and streaming. |
| Databricks OpenAI-compatible API | Calls foundation models, serving endpoints, and Databricks Apps through one Responses API contract. |
| Pydantic and Pydantic Settings | Validates external HTTP payloads and typed runtime environment settings. |
| React, TypeScript, and Vite | Provide the browser chat experience that renders finalized streamed response text. |

## AI Design Patterns

| Pattern | Usage in this project |
| --- | --- |
| Orchestrator and specialist tools | A central agent selects policy-approved Genie, AI Search, Lakebase, serving-endpoint, and App capabilities. |
| Tool-augmented generation | The model uses native function or MCP calls for governed data instead of relying on model-only answers. |
| Adapter and port | `application/ports/tools.py` defines tool contracts; `application/adapters/tools.py` supplies default direct-tool behavior. |
| Registry | `DefaultToolRegistry` provides ordered direct-tool adapter selection. MCP and Lakebase retain dedicated builders; delegation uses the task bus. |
| Deterministic routing | Capability matching and task-type rules choose candidate subagents and the standard, reasoning, or synthesis model route. |
| Hybrid authorization | Each subagent declares app identity or on-behalf-of-user execution; policy evaluates persona, classification, and token availability before assembly. |
| Guardrails | Input and response checks enforce evidence requirements, response limits, and sensitive-output protections. |
| Human-in-the-loop | Store intervention recommendations require durable manager approval before any planning-only follow-up task. |
| Bounded delegation | Typed tasks use explicit source, target, intent, idempotency, leases, expiry, retries, and dead-letter state. |
| Observability and release gates | Lifecycle events, MLflow traces, evaluation scorers, and promotion KPIs provide runtime and release evidence. |

## AI Tools and Data Capabilities

| Capability | Integration and usage |
| --- | --- |
| Genie Agents | MCP-connected business analytics over governed semantic sources. |
| AI Search and Vector Search | MCP-connected retrieval for product knowledge and Flink support. |
| Lakebase PostgreSQL | OAuth-authenticated SQL access to current operational data; also an optional isolated conversation-memory store. |
| Databricks serving endpoints | Direct Responses API specialist calls. |
| Databricks App specialist | Direct Responses API call to `hitl-app-agent` for evidence-backed intervention packets. |
| Unity Catalog Metric Views | Reusable governed metrics exposed to Genie-owned semantic spaces. |
| Unity Catalog audit and approval tables | Durable lifecycle events and manager approval decisions. |
| Unity AI Gateway | Optional OpenAI-compatible control point set through the configured base URL and timeout. |

The active tool names, targets, owners, identities, classifications, and freshness SLAs are maintained in the [Tool and model registry](tool-and-model-registry.md).

## Project Skills and Operational Playbooks

| Skill or playbook | Usage |
| --- | --- |
| `add-tools` | Wires Databricks capabilities and grants application permissions. |
| `create-tools` | Prepares required Genie, serving endpoint, and related resources. |
| `discover-tools` | Finds target-workspace resource identifiers for configuration. |
| `modify-agent` | Changes orchestrator behavior, subagent routing, and request handling. |
| `deploy` | Validates and deploys the Databricks bundle by target. |
| `quickstart` | Bootstraps local development and baseline Databricks configuration. |
| `run-locally` | Starts and validates backend and frontend runtime paths. |
| [runtime-routing](../../.claude/skills/runtime-routing/SKILL.md) | Implements and validates policy-aware routing. |
| [runtime-guardrails](../../.claude/skills/runtime-guardrails/SKILL.md) | Implements response-policy and evidence controls. |
| [runtime-auth-obo](../../.claude/skills/runtime-auth-obo/SKILL.md) | Implements app/OBO authorization behavior. |
| [runtime-audit-observability](../../.claude/skills/runtime-audit-observability/SKILL.md) | Implements lifecycle audit and observability behavior. |

## Related Documents

- [Runtime technical specifications](runtime-technical-specs.md): implemented runtime facts and configuration behavior.
- [Tool and model registry](tool-and-model-registry.md): active tool and model inventory by target.
- [Low-level design](low-level-design.md): module responsibilities and detailed design patterns.
- [Governance guide](../governance/README.md): policy, security, semantics, and approval controls.
- [Operations guide](../operations/README.md): deployment, observability, and incident procedures.
