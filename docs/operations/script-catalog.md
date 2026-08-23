# Script Catalog

Project commands are grouped into runtime core and assistant/operations support. Existing individual commands remain available for compatibility.

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
```

The equivalent Make target displays the group:

```bash
make assistant-tools
```

## Compatibility

The original `uv run` entry points in `pyproject.toml` remain as compatibility commands. The grouped dispatchers accept only the canonical names above and forward all arguments to the existing command implementations.