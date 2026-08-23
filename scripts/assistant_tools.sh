#!/bin/sh

set -eu

usage() {
  printf '%s\n' \
    'Assistant and operations commands:' \
    '  assistant-bootstrap             Bootstrap local Databricks development' \
    '  assistant-evaluate              Run MLflow agent evaluation' \
    '  assistant-discover-tools        Discover configured Databricks tools' \
    '  assistant-setup-flink           Prepare Flink support RAG assets' \
    '  assistant-setup-cdi             Prepare the CDI Genie agent' \
    '  assistant-grant-app-permissions Grant app runtime permissions' \
    '  assistant-grant-lakebase-memory Grant Lakebase memory permissions' \
    '  assistant-benchmark-stream      Benchmark stream parsing helpers'
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

command="$1"
shift

case "$command" in
  assistant-bootstrap) exec uv run assistant-bootstrap "$@" ;;
  assistant-evaluate) exec uv run assistant-evaluate "$@" ;;
  assistant-discover-tools) exec uv run assistant-discover-tools "$@" ;;
  assistant-setup-flink) exec uv run assistant-setup-flink "$@" ;;
  assistant-setup-cdi) exec uv run assistant-setup-cdi "$@" ;;
  assistant-grant-app-permissions) exec uv run assistant-grant-app-permissions "$@" ;;
  assistant-grant-lakebase-memory) exec uv run assistant-grant-lakebase-memory "$@" ;;
  assistant-benchmark-stream) exec uv run assistant-benchmark-stream "$@" ;;
  help|-h|--help) usage ;;
  *) printf 'Unknown assistant command: %s\n\n' "$command" >&2; usage >&2; exit 2 ;;
esac