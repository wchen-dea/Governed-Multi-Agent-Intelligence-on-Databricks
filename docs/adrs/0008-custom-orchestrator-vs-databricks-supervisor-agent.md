# ADR 0008: Keep Custom Orchestrator as Primary Runtime over Databricks Supervisor Agent

## Status

Accepted

## Context

The project runs a custom multi-agent orchestrator in Databricks Apps using the OpenAI Agents SDK (`openai-agents`) with:

- Staged pipeline execution (`Runner.run` / `Runner.run_streamed`)
- 6 subagents: 2 Genie MCP, 2 AI Search MCP, 1 Databricks App HITL specialist, 1 Lakebase PostgreSQL
- Persona-based policy enforcement with 4 personas (manager, analyst, operator, engineer)
- Hybrid app/OBO authorization
- Response guardrails with source attribution
- Lifecycle event bus with UC audit persistence

Databricks Supervisor Agent offers a managed supervisory orchestration model that can reduce custom runtime code, but introduces tighter platform opinionation over routing, auth, and orchestration behavior.

## Decision

Use the current custom orchestrator as the primary production runtime for governed enterprise workflows.

Adopt Supervisor Agent selectively for standardized, lower-risk use cases where reduced orchestration maintenance is more valuable than deep custom control.

### Comparison

| Dimension | Custom Orchestrator (current) | Databricks Supervisor Agent |
| --- | --- | --- |
| Routing control | Full — per-subagent policy rules, persona matrix | Platform-managed — less granular |
| Auth model | Hybrid app + OBO per subagent | Platform-managed identity |
| Guardrails | Custom evidence/safety/PII checks + AI Gateway | Platform guardrails only |
| Tool types | Genie MCP, AI Search MCP, Lakebase, serving endpoints, apps | Managed tool integrations |
| Observability | Custom message bus → UC audit table | Platform telemetry |
| Maintenance | Full ownership of pipeline code | Managed by Databricks |
| Governance precision | Exact — persona ACLs, confidence gating, source attribution | Coarser — platform defaults |

## Alternatives Considered

- Full migration to Databricks Supervisor Agent for all workflows.
- Continue with custom orchestrator only and do not evaluate Supervisor Agent.
- Hybrid model (chosen): retain custom runtime for governed paths and evaluate Supervisor Agent for standard paths.

## Consequences

### Positive

- Preserves governance precision already implemented (persona-based routing, evidence attribution).
- Keeps explicit control over auth-mode routing and OBO identity branching.
- Avoids immediate migration risk for critical enterprise paths.
- Enables incremental experimentation with Supervisor Agent where it is a strong fit.

### Trade-offs

- Ongoing ownership of custom orchestrator behavior and deployment operations.
- Feature parity with new managed orchestration capabilities must be monitored.
- Hybrid adoption increases architecture complexity if boundaries are not kept clear.

## Implementation Notes

- Orchestration agent: [src/aiserver/application/orchestration/agent.py](../../src/aiserver/application/orchestration/agent.py) (`create_orchestrator_agent`, `connect_healthy_mcp_servers`, `build_subagent_tools`, `build_lakebase_tools`)
- Pipeline execution: [src/aiserver/api/invocations.py](../../src/aiserver/api/invocations.py) (staged pipeline using `Runner.run` / `Runner.run_streamed`)
- Runtime auth and policy: [src/aiserver/application/auth/context.py](../../src/aiserver/application/auth/context.py), [src/aiserver/application/auth/policy.py](../../src/aiserver/application/auth/policy.py)
- Guardrails: [src/aiserver/application/guardrails/checks.py](../../src/aiserver/application/guardrails/checks.py)
- Subagent registry: [src/aiserver/contracts/subagents.dev.json](../../src/aiserver/contracts/subagents.dev.json) (6 subagents, per-persona access)
- Deployment: [Makefile](../../Makefile) (`make deploy`, `make redeploy`), [docs/operations/operations-runbook.md](../operations/operations-runbook.md)
