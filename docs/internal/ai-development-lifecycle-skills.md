# Claude Code Skills Across the AI System Development Life Cycle

## Purpose

Map the project's Claude Code skills (`.claude/skills/`) to the stages of this repository's AI system development life cycle, and document the best practices for using each skill at its stage. This complements [claude.md](claude.md) (skill mechanics and invocation) with a life-cycle view for onboarding and process consistency.

## Scope

Covers the 11 active skills: `quickstart`, `discover-tools`, `create-tools`, `add-tools`, `modify-agent`, `runtime-routing`, `runtime-guardrails`, `runtime-auth-obo`, `runtime-audit-observability`, `run-locally`, `deploy`. Evaluation and production monitoring are governed by [quality/evaluation-spec.md](../quality/evaluation-spec.md) and [operations/ai-agent-monitoring-observability.md](../operations/ai-agent-monitoring-observability.md), not by a dedicated skill; they are included below only as the life-cycle stages that follow deployment.

## Life Cycle Stages and Skill Mapping

```mermaid
flowchart LR
    A[1. Environment Bootstrap] --> B[2. Capability Discovery]
    B --> C[3. Resource Provisioning]
    C --> D[4. Tool & Routing Integration]
    D --> E[5. Agent & Governance Behavior Development]
    E --> F[6. Local Validation]
    F --> G[7. Deployment & Promotion]
    G --> H[8. Evaluation & Release Gate]
    H --> I[9. Operate & Observe]
    I -->|change request| B
```

| Stage | Skill(s) | When Used | Key Outputs |
| --- | --- | --- | --- |
| 1. Environment bootstrap | `quickstart` | First-time setup, missing `.env`/auth profile/MLflow experiment | Working `.env`, Databricks auth profile, MLflow experiment id |
| 2. Capability discovery | `discover-tools` | Before adding or changing any tool/subagent | Genie `space_id`, serving endpoint names, UC resource identifiers |
| 3. Resource provisioning | `create-tools` | Required Genie space, endpoint, or app resource does not exist yet | New Genie Agent, serving endpoint, or Databricks app resource |
| 4. Tool & routing integration | `add-tools` | Wiring a discovered/created resource into the app | Updated `src/aiserver/contracts/subagents.<target>.json`, updated `resources/multiagent_app.yml` permissions |
| 5. Agent & governance behavior development | `modify-agent`, `runtime-routing`, `runtime-guardrails`, `runtime-auth-obo`, `runtime-audit-observability` | Changing orchestration logic, route selection, guardrail policy, auth-mode enforcement, or lifecycle/audit event behavior | Updated backend orchestration, routing rules, guardrail checks, auth validation, or message-bus/event schema code |
| 6. Local validation | `run-locally` | After any code change, before deploy | Healthy local app, passing `/invocations` smoke test, `runtime-preflight` checks |
| 7. Deployment & promotion | `deploy` | Shipping validated changes to `dev`/`qa`/`stg`/`prd` | Deployed Databricks app, bundle-applied resource grants, post-deploy health check |
| 8. Evaluation & release gate | *(no dedicated skill — see [quality/evaluation-spec.md](../quality/evaluation-spec.md))* | Before promoting past `dev`/`qa` | KPI evidence against release-gate thresholds |
| 9. Operate & observe | *(no dedicated skill — see [operations/ai-agent-monitoring-observability.md](../operations/ai-agent-monitoring-observability.md))* | Continuously in deployed environments | Lifecycle/audit events, MLflow traces, incident detection |

## Best Practices by Stage

### 1. Environment bootstrap (`quickstart`)
- Run once per developer machine or when `.env`/auth breaks; do not re-run just to "be safe" before every task.
- Verify with `databricks auth profiles`, `uv run runtime-preflight`, and `uv run runtime-serve-app` before moving to discovery.

### 2. Capability discovery (`discover-tools`)
- Always run discovery before `add-tools` or `create-tools` so IDs/endpoint names come from the actual target workspace, not assumptions.
- Store discovered identifiers in `targets/*.yml` variables, never hardcode them in application code.

### 3. Resource provisioning (`create-tools`)
- Only invoke when discovery confirms the resource is genuinely missing; do not provision duplicate Genie spaces or endpoints.
- Record ownership, risk classification, and freshness expectations for any new resource in [architecture/tool-and-model-registry.md](../architecture/tool-and-model-registry.md).

### 4. Tool & routing integration (`add-tools`)
- Never change routing (`subagents.<target>.json`) without a matching permission update in `resources/multiagent_app.yml` — routing and permission changes must land together.
- Match subagent type to its required fields (`genie` → `space_id`, `serving_endpoint`/`app` → `endpoint`, `mcp` → `mcp_url`, `lakebase` → `project_id`/`branch_id`/`endpoint_id`/`database`/`pg_host`).

### 5. Agent & governance behavior development
- Use `modify-agent` for orchestration/request-handling changes; use the `runtime-*` skills for policy-scoped changes (routing rules, guardrails, auth mode, audit/observability) so each change stays scoped to its owning module and playbook.
- Keep direct function-tool changes in `application/adapters/tools.py`; MCP and Lakebase use dedicated builders in `application/orchestration/agent.py`; delegation uses the task-bus handoff flow. Do not blur these boundaries.
- Validate with `python -m py_compile src/aiserver/*.py src/operations/*.py` and `uv run runtime-preflight` before moving to local validation.

### 6. Local validation (`run-locally`)
- Run after every behavior change, not only before deploy — catching regressions locally is cheaper than catching them at `deploy`.
- Exercise both `uv run runtime-serve-app` (bundled) and `uv run runtime-serve-backend --reload` (iterative) paths, and hit `http://localhost:8000/invocations` as a smoke test.

### 7. Deployment & promotion (`deploy`)
- Use `make redeploy TARGET=<target> APP_NAME=<app-name> PROFILE=<profile>` so validation, deploy, permissions, and smoke checks run as one flow instead of ad hoc steps.
- Prefer binding an existing app over deleting it on name conflicts; only fall back to `make upload-wheel` when Terraform Registry is unavailable, and still apply the bundle for resource-grant changes.
- Always pass `--profile` explicitly; never rely on an implicit default profile across targets.

### 8. Evaluation & release gate
- Do not promote past `dev`/`qa` without KPI evidence meeting the thresholds in [quality/evaluation-spec.md](../quality/evaluation-spec.md); this is a gate, not a formality.

### 9. Operate & observe
- Confirm lifecycle/audit events are flowing (message bus backend healthy) after every deploy, per [operations/ai-agent-monitoring-observability.md](../operations/ai-agent-monitoring-observability.md).
- Feed production incidents or drift back into stage 2 (discovery) rather than patching runtime behavior directly in production.

## Cross-Cutting Practice

- Explicitly name the skill(s) in your prompt (see the prompt template in [claude.md](claude.md)) so execution stays aligned with the stage's expected inputs/outputs.
- Do not skip stages backward-to-forward (e.g., `deploy` before `run-locally`) except for explicitly read-only or rollback operations.
- Every skill invocation that changes routing, permissions, guardrails, or auth must be traceable to an updated file listed in its "Key Outputs" column above — an agent behavior change with no corresponding file diff should be treated as incomplete.

## Related Docs

- [claude.md](claude.md): skill matrix, invocation mechanics, and per-skill commands.
- [architecture/ai-technologies-and-patterns.md](../architecture/ai-technologies-and-patterns.md): skills inventory alongside frameworks, patterns, and tools.
- [quality/evaluation-spec.md](../quality/evaluation-spec.md): release-gate KPIs and evidence requirements.
- [operations/ai-agent-monitoring-observability.md](../operations/ai-agent-monitoring-observability.md): production observability posture.
