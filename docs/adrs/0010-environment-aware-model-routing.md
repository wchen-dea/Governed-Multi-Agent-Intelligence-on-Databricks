# ADR 0010: Use Environment-Aware Model Routing

## Status

Accepted

## Context

The orchestrator serves multiple workload types with different quality, latency, and cost requirements:

- Standard conversational and lookup turns need predictable latency and controlled cost.
- Operational reasoning tasks, such as SQL, appointments, orders, Flink, debugging, and incident analysis, need stronger planning reliability.
- Synthesis tasks, such as comparisons, executive summaries, recommendations, plans, and human-approval packets, need higher answer quality and better first-pass completeness.

Using one model for every request is operationally simple, but it does not reflect those different service-level objectives. It either over-spends on simple traffic or under-powers higher-risk reasoning and synthesis workflows.

The project already has a deterministic model router that runs before orchestrator construction and records the selected model in lifecycle metadata. The route choice is based on request task type and is configured through Databricks Asset Bundle target variables.

## Decision

Use deterministic, environment-aware model routing for runtime agent requests.

Runtime requests are classified into one of three active task routes:

| Route | Purpose | Default dev model |
| --- | --- | --- |
| standard | Ordinary conversation and simple lookup turns | `databricks-gpt-5-6-luna` |
| reasoning | Operational, SQL, support, troubleshooting, and incident tasks | `databricks-claude-sonnet-5` |
| synthesis | Analysis, comparison, executive-summary, recommendation, planning, and approval-oriented tasks | `databricks-claude-sonnet-5` |

Route rules are defined in one ordered rule table. Synthesis is evaluated before reasoning, and standard is the fallback. This means mixed prompts such as "analyze appointment trends and recommend a plan" choose the synthesis route rather than the operational reasoning route.

Each target environment may set its own model profile through:

- `MODEL_ROUTING_ENABLED`
- `MODEL_ROUTING_DEFAULT_MODEL`
- `MODEL_ROUTING_REASONING_MODEL`
- `MODEL_ROUTING_QUALITY_MODEL`

Current target posture:

| Target | SLA posture | Standard route | Reasoning route | Synthesis route |
| --- | --- | --- | --- | --- |
| dev | Fast iteration and cost control | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| qa | Production-parity regression checks | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| stg | Quality-first pre-production validation | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |
| prd | Balanced user-facing latency, cost, and quality | `databricks-gpt-5-6-luna` | `databricks-claude-sonnet-5` | `databricks-claude-sonnet-5` |

The runtime records `model`, `model_task_type`, `model_reason`, and `model_rationale` in routing lifecycle metadata and response governance metadata. These fields explain why a model was selected; they are not proof that the model called the correct tool.

LLM judge model selection remains separate from runtime model routing. Evaluation uses `EVAL_JUDGE_MODEL` for built-in MLflow LLM judge scorers and `EVAL_SIMULATOR_USER_MODEL` for simulated user turns.

## Rationale

### Quality

Higher-quality routes are reserved for tasks where reasoning depth or synthesis quality materially affects business trust, such as SQL generation, operational troubleshooting, executive summaries, recommendations, and approval packets.

### Cost

The standard route keeps common low-complexity traffic on the balanced default model. This avoids sending simple lookup or conversational turns to the highest-quality route when tool grounding and short responses are sufficient.

### Efficiency

The router avoids an extra model call by using deterministic local classification. Stronger models are used where they are expected to reduce retries, failed tool attempts, follow-up clarification, and manual triage.

## Alternatives Considered

- **Use one model for all runtime requests.** Rejected because it does not reflect different cost, latency, and quality needs across request classes and environments.
- **Use a model to choose the model.** Rejected for now because it adds latency, cost, and another failure mode before every request.
- **Use only environment-level single-model profiles.** Rejected because each environment still contains mixed traffic: simple lookup, operational reasoning, and higher-value synthesis.
- **Let AI Gateway decide the model without application routing metadata.** Rejected because this project needs explicit, auditable route decisions in application lifecycle events.

## Consequences

### Positive

- Aligns model cost with request complexity.
- Improves reasoning and synthesis quality for higher-risk workflows.
- Keeps routing explainable and auditable without an additional model call.
- Allows dev, QA, staging, and production to express different SLA postures through target overlays.
- Keeps runtime model routing separate from LLM judge and simulated-user model selection.

### Trade-offs

- More target configuration must be maintained and validated.
- Keyword-based task classification can miss novel phrasing until route tests and evaluation cases are expanded.
- Mixed-intent precedence must remain intentional and tested.
- Model-route metadata explains selection rationale but does not prove tool-call correctness or response groundedness.

## Implementation Notes

- Route rule implementation: [src/aiserver/application/orchestration/model.py](../../src/aiserver/application/orchestration/model.py)
- Runtime settings: [src/aiserver/config/settings.py](../../src/aiserver/config/settings.py)
- Route metadata emission: [src/aiserver/api/invocations.py](../../src/aiserver/api/invocations.py)
- Response metadata contract: [src/aiserver/contracts/responses.py](../../src/aiserver/contracts/responses.py)
- Dev target model profile: [targets/dev.yml](../../targets/dev.yml)
- QA/STG/PRD target model profiles: [targets/qa.yml](../../targets/qa.yml), [targets/stg.yml](../../targets/stg.yml), [targets/prd.yml](../../targets/prd.yml)
- Model route tests: [tests/test_model_routing_service.py](../../tests/test_model_routing_service.py)
- Evaluation judge model configuration: [src/operations/evaluate_agent.py](../../src/operations/evaluate_agent.py)

## Validation

Required checks before changing or promoting a model route:

```bash
uv run pytest tests/test_model_routing_service.py tests/test_api_handlers.py
uv run assistant-evaluate
databricks bundle validate -t <target> --profile <profile>
```

Promotion must preserve blocking auth correctness, safety, and groundedness KPI thresholds. Tool-call accuracy remains monitored but non-blocking until the MLflow nested-span scoring gap is resolved.
