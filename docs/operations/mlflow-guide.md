# MLflow in This Project

This project uses MLflow across three areas: runtime tracing, agent evaluation, and release gating.

## 1. Runtime Tracing

Every request to the app generates an MLflow trace automatically.

### How it works

`mlflow.openai.autolog()` in [handlers.py](../../src/backend/api/handlers.py) captures every `AsyncDatabricksOpenAI` call as a traced span. The `@invoke()` and `@stream()` decorators from `mlflow.genai.agent_server` register the handlers and wrap each request in a trace context.

`set_trace_processors([])` clears the OpenAI Agents SDK's own trace sinks so MLflow is the single tracing backend — no duplicate trace output.

### What gets captured per request

- Full span tree: handler → orchestrator → tool calls (Genie / AI Search / Lakebase)
- Per-span latency and token counts (input + output)
- Request and response payloads
- Git commit SHA and branch (via `setup_mlflow_git_based_version_tracking()` in [server.py](../../src/backend/api/server.py))

### Where traces land

Traces route to the experiment specified by `MLFLOW_EXPERIMENT_ID`:

| Environment | Experiment ID | Experiment Path |
|-------------|--------------|-----------------|
| dev | `3025644123415124` | `/Shared/multiagent-app-dev` |
| qa/stg/prod | Set per target | See `targets/*.yml` |

Configuration chain: `targets/dev.yml` → `databricks.yml` variable → `resources/multiagent_app.yml` env injection → `app.yml` deployed to Databricks App.

### Viewing traces

Open the MLflow Experiments UI in the workspace, select the experiment, and click the **Traces** tab. Each trace shows a span hierarchy:

```
ResponsesAgent (root span)
├── LLM call → foundation model (prompt + completion)
├── Tool: sales_insights_agent (Genie MCP)
├── Tool: product_index_assistant (AI Search MCP)
└── LLM call → final response generation
```

Click any span to see latency, token counts, and full input/output text.

## 2. Agent Evaluation

The evaluation pipeline in [evaluate_agent.py](../../src/backend/evaluate_agent.py) runs multi-turn conversations against the deployed agent and scores the results.

### Running evaluation

```bash
# Local
make evaluate

# CI (runs automatically before deploy)
uv run agent-evaluate
```

### What happens during evaluation

1. Creates an MLflow run named `agent-quality-evaluation`
2. Logs test parameters (case count, max turns, KPI thresholds)
3. Runs `mlflow.genai.evaluate()` with a `ConversationSimulator` (LLM-as-judge using `databricks-claude-sonnet-5`)
4. Scores each conversation with 10 built-in scorers + 1 custom scorer:

| Scorer | What It Measures |
|--------|-----------------|
| `ToolCallCorrectness` | Did the agent call the right tool? |
| `Safety` | Is the response free of harmful content? |
| `ConversationalSafety` | Multi-turn safety across the conversation |
| `RelevanceToQuery` | Does the response address the question? |
| `Completeness` | Is the answer thorough? |
| `ConversationCompleteness` | Multi-turn completeness |
| `Fluency` | Is the language natural and clear? |
| `KnowledgeRetention` | Does the agent retain context across turns? |
| `UserFrustration` | Does the user show signs of frustration? |
| `auth_correctness_scorer` | Custom — validates policy-denied tools aren't invoked |

5. Logs aggregate metrics back to the MLflow run
6. Enforces release gate (see below)

### Viewing evaluation results

In the MLflow Experiments UI, switch to the **Runs** tab. Each evaluation run shows:
- Logged parameters (case count, thresholds)
- Logged metrics (per-scorer aggregates)
- `gate.release_passed` metric (1.0 = passed, 0.0 = failed)
- Per-conversation scorer results in a table view

## 3. Release Gate

Evaluation doubles as a CI/CD quality gate via `enforce_release_gate()`. If any KPI falls below its threshold, the pipeline fails.

### KPI thresholds

| KPI | Env Var | Default | Metric Candidates |
|-----|---------|---------|-------------------|
| Tool-call accuracy | `EVAL_MIN_TOOL_CALL_ACCURACY` | 0.80 | `toolcallcorrectness/mean`, `tool_call_correctness` |
| Auth correctness | `EVAL_MIN_AUTH_CORRECTNESS` | 0.90 | `authcorrectness/mean`, `auth_correctness` |
| Safety | `EVAL_MIN_SAFETY` | 0.95 | `safety/mean`, `safety` |
| Groundedness | `EVAL_MIN_GROUNDEDNESS` | 0.80 | `relevance_to_query/mean`, `groundedness` |

Set `EVAL_REQUIRE_ALL_KPIS=true` (CI default) to also fail when expected metrics are missing.

### CI enforcement

In [.github/workflows/databricks-cicd.yml](../../.github/workflows/databricks-cicd.yml), evaluation runs in both PR checks and deploy jobs. Gate failure blocks PR merge and deployment.

## 4. Configuration Reference

### Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MLFLOW_TRACKING_URI` | MLflow tracking backend | `databricks` (workspace-native) |
| `MLFLOW_REGISTRY_URI` | Model registry backend | `databricks-uc` (Unity Catalog) |
| `MLFLOW_EXPERIMENT_ID` | Target experiment for traces | Per-environment (see `targets/*.yml`) |

### Local development

Copy `.env.example` to `.env` and set `MLFLOW_EXPERIMENT_ID` to a valid experiment. Run `uv run quickstart` to auto-create one.

Traces from `uv run start-server` will appear in the configured experiment when `MLFLOW_TRACKING_URI=databricks` and you have valid Databricks auth.

### Platform telemetry (separate from MLflow)

The app also exports platform-level telemetry to Unity Catalog tables (configured in `resources/multiagent_app.yml`):

```yaml
telemetry_export_destinations:
- unity_catalog:
    logs_table: quickstart_catalog.multi_agent_schema.app_logs
    metrics_table: quickstart_catalog.multi_agent_schema.app_metrics
    traces_table: quickstart_catalog.multi_agent_schema.app_traces
```

This is **separate** from MLflow traces — it captures Databricks App platform telemetry (container logs, HTTP metrics), not agent-level spans.

## 5. Two Observability Streams

The project has two independent telemetry paths:

| Stream | Captures | Storage | Access |
|--------|----------|---------|--------|
| **MLflow traces** | LLM calls, spans, latency, tokens, inputs/outputs | MLflow Experiment | Experiments UI → Traces tab |
| **Lifecycle message bus** | Domain events (`request.invoke.started`, `response.guardrail.blocked`) | UC audit table | SQL queries on `quickstart_catalog.multi_agent_schema.agent_lifecycle_events` |

MLflow traces answer "what did the LLM do?" — the message bus answers "what did the orchestrator decide?"
