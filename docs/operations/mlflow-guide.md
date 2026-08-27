# MLflow in This Project

This project uses MLflow across three areas: runtime tracing, agent evaluation, and release gating.

## 1. Runtime Tracing

Every request to the app generates an MLflow trace automatically.

### How it works

`mlflow.openai.autolog()` in [handlers.py](../../src/aiserver/api/handlers.py) captures every `AsyncDatabricksOpenAI` call as a traced span. The `@invoke()` and `@stream()` decorators from `mlflow.genai.agent_server` register the handlers and wrap each request in a trace context.

`set_trace_processors([])` clears the OpenAI Agents SDK's own trace sinks so MLflow is the single tracing backend — no duplicate trace output.

### What gets captured per request

- Full span tree: handler → orchestrator → tool calls (Genie / AI Search / Lakebase)
- Per-span latency and token counts (input + output)
- Request and response payloads
- Git commit SHA and branch (via `setup_mlflow_git_based_version_tracking()` in [server.py](../../src/aiserver/api/server.py))

### Where traces land

Traces route to the experiment specified by `MLFLOW_EXPERIMENT_ID`:

| Environment | Experiment ID | Experiment Path |
|-------------|--------------|-----------------|
| dev | `3025644123415124` | `/Shared/multiagent-app-dev` |
| qa/stg/prd | Set per target | See `targets/*.yml` |

Configuration chain: `targets/dev.yml` variable → `databricks.yml` variable default (fallback) → `resources/multiagent_app.yml` `${var.x}` reference → `prepare_app_source.py` resolves and writes `.databricks_app_source/app.yml` on every `make build-app-source` run → deployed to the Databricks App and read by `launcher.py` at startup.

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

The evaluation pipeline in [evaluate_agent.py](../../src/aiserver/evaluate_agent.py) runs multi-turn conversations against the deployed agent and scores the results.

The simulator includes both tool-requiring and conversational turns. A failed tool-call KPI must therefore be investigated against individual traces rather than inferred from route-plan events alone. Route-plan events are diagnostic metadata; `ToolCallCorrectness` evaluates the actual model/tool behavior.

### Running evaluation

```bash
# Local
make evaluate

# CI (runs automatically before deploy)
uv run assistant-evaluate
```

### What happens during evaluation

1. Creates an MLflow run named `agent-quality-evaluation`
2. Logs test parameters (case count, max turns, KPI thresholds)
3. Runs `mlflow.genai.evaluate()` with a `ConversationSimulator` (LLM-as-judge using `databricks-claude-sonnet-5`)
4. Scores each conversation with 9 built-in scorers + 2 custom scorers:

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
| `direct_groundedness_scorer` | Custom — validates evidence markers and freshness metadata |

5. Logs aggregate metrics back to the MLflow run
6. Enforces release gate (see below)

### Viewing evaluation results

There are two options for viewing evaluation runs and scorer results:

#### Option A: Databricks workspace UI (recommended for team visibility)

Set `.env` to point to the workspace:

```bash
MLFLOW_TRACKING_URI=databricks
MLFLOW_EXPERIMENT_ID=3025644123415124
```

Run `make evaluate`. Results appear in the workspace at:
```
https://dbc-baff2b7f-4402.cloud.databricks.com/ml/experiments/3025644123415124
```

In the Experiments UI:
- **Runs tab** → select the `agent-quality-evaluation` run → view logged params, KPI metrics, and `gate.release_passed`
- **Evaluation tab** (inside the run) → per-conversation scorer breakdown table with 11 scorers

### Current failure baseline

On 2026-08-23, the evaluation completed with tool-call accuracy `0.400` against the `0.800` release threshold. The run also recorded failed completeness, fluency, and relevance scorer invocations. The gate remained blocked as designed. Use the MLflow run linked in the command output to inspect which turns expected a tool, which expected a direct answer, and which scorer calls failed independently.

The deterministic route planner is validated separately by [test_route_planner.py](../../tests/test_route_planner.py). That test suite proves capability matching for representative intents; it does not prove that the model will call the selected tool or refrain from calling tools on conversational turns. The latest planner implementation uses a `0.60` confidence threshold for hard narrowing.
- **Traces tab** → each simulated conversation generates a full trace with LLM call spans

#### Option B: Local MLflow UI (offline, no workspace auth needed)

Remove or comment out `MLFLOW_TRACKING_URI` in `.env` (or delete `.env`). Runs go to the local `mlruns/` directory.

```bash
# Run evaluation (results saved locally)
make evaluate

# Start local MLflow UI
uv run mlflow ui --port 5000
```

Open http://localhost:5000 → select the default experiment → click the evaluation run to see params, metrics, and scorer tables.

Both options show the same data: run parameters, aggregate KPI metrics, per-conversation scorer results, and the release gate outcome.

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

Copy `.env.example` to `.env` and set `MLFLOW_EXPERIMENT_ID` to a valid experiment. Run `uv run assistant-bootstrap` to auto-create one.

Traces from `uv run runtime-serve-backend` will appear in the configured experiment when `MLFLOW_TRACKING_URI=databricks` and you have valid Databricks auth.

### Viewing evaluation runs locally

When `MLFLOW_TRACKING_URI` is not set (or not in `.env`), evaluation runs are stored in the local `mlruns/` directory. To view them:

```bash
# Run evaluation (results go to ./mlruns/)
make evaluate

# Start local MLflow UI
uv run mlflow ui --port 5000
```

Open http://localhost:5000 to browse runs, metrics, and scorer results. The default experiment (`0`) will contain evaluation runs with logged parameters, KPI metrics, and `gate.release_passed` status.

### Viewing evaluation runs from Databricks Workspace

To send evaluation runs to the **Databricks workspace** instead (same experiment as the deployed app), create a `.env`:

```bash
MLFLOW_TRACKING_URI=databricks
MLFLOW_EXPERIMENT_ID=3025644123415124
```

With this set, `make evaluate` writes runs directly to the workspace experiment visible at the MLflow Experiments UI in Databricks.

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
