# Databricks Evaluation Automation

Databricks Job that runs `aiserver.evaluate_agent.evaluate()` on Databricks
compute instead of a local shell. This avoids local network/tracing-latency
failures because both the MLflow tracking server and Lakebase Postgres are
reached over the workspace's private network rather than the public internet.

## What it does

The job attaches the project wheel (built automatically by the bundle's
`multiagent_wheel` artifact) as a cluster library, then runs
[run_evaluation.py](run_evaluation.py), which sets the
required environment variables from job parameters and calls
`aiserver.evaluate_agent.evaluate()` directly — the same function `make
evaluate` / `uv run assistant-evaluate` invoke locally.

## Run it

```bash
databricks bundle deploy -t <target>
databricks bundle run run_agent_quality_evaluation -t <target>
```

Override KPI thresholds or the experiment id per invocation with
`--params key=value` (see `resources/evaluation_job.yml` for parameter names).

## Related

- [docs/quality/evaluation-spec.md](../../docs/quality/evaluation-spec.md): scorer definitions, KPI thresholds, and gate policy.
- `src/aiserver/evaluate_agent.py`: evaluation logic and test cases run by this job.
