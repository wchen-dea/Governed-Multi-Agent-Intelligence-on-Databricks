# Script Catalog

Project commands are grouped into runtime core and assistant/operations support.
This file is the command-group index and compatibility reference. The
[operations runbook](operations-runbook.md) owns deployment sequencing and
recovery, while the [UI deployment guide](ui-deployment-guide.md) owns frontend
development and packaging details.

## Runtime Core

Use [scripts/runtime_core.sh](../../scripts/runtime_core.sh) for the commands needed to run, validate, and package the application:

```bash
./scripts/runtime_core.sh runtime-serve-app
./scripts/runtime_core.sh runtime-serve-backend
./scripts/runtime_core.sh runtime-preflight
./scripts/runtime_core.sh runtime-build-source
```

The equivalent Make target displays the group:

```bash
make runtime-core
```

## Assistant And Operations

Use [scripts/assistant_tools.sh](../../scripts/assistant_tools.sh) for evaluation, discovery, resource setup, permissions, and diagnostics:

```bash
./scripts/assistant_tools.sh assistant-bootstrap
./scripts/assistant_tools.sh assistant-evaluate
./scripts/assistant_tools.sh assistant-discover-tools
./scripts/assistant_tools.sh assistant-setup-flink
./scripts/assistant_tools.sh assistant-setup-cdi
./scripts/assistant_tools.sh assistant-grant-app-permissions --help
./scripts/assistant_tools.sh assistant-grant-lakebase-memory --help
./scripts/assistant_tools.sh assistant-benchmark-stream
./scripts/assistant_tools.sh assistant-triage-evaluation
```

The equivalent Make target displays the group:

```bash
make assistant-tools
```

## Compatibility

The original `uv run` entry points in `pyproject.toml` remain as compatibility commands. The grouped dispatchers accept only the canonical names above and forward all arguments to the existing command implementations.

## Release Commands

| Command | Purpose |
| --- | --- |
| `make test` | Run the full Python test suite. |
| `make lint` | Run Ruff Python checks, React Prettier verification, and Markdown lint. |
| `make format` | Apply Ruff Python formatting and React Prettier formatting. |
| `make lint-markdown` | Validate authored Markdown only. |
| `make evaluate` | Run MLflow evaluation and enforce configured KPI gates. |
| `make redeploy TARGET=<target> APP_NAME=<app> PROFILE=<profile>` | Full validation, bundle attempt, source deploy, grants, health, and smoke workflow. |
| `make upload-wheel TARGET=<target> APP_NAME=<app> PROFILE=<profile>` | Versioned source-only app deployment fallback; does not apply bundle resources or grants. |

See the [operations guide](README.md) and [operations runbook](operations-runbook.md) for command prerequisites and recovery boundaries.