#!/bin/sh

set -eu

usage() {
  printf '%s\n' \
    'Runtime core commands:' \
    '  runtime-serve-app      Start backend and React UI' \
    '  runtime-serve-backend  Start the backend only' \
    '  runtime-preflight      Validate local startup and invocation path' \
    '  runtime-build-source   Build the deployable wheel and React assets'
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

command="$1"
shift

case "$command" in
  runtime-serve-app) exec uv run runtime-serve-app "$@" ;;
  runtime-serve-backend) exec uv run runtime-serve-backend "$@" ;;
  runtime-preflight) exec uv run runtime-preflight "$@" ;;
  runtime-build-source) exec uv run runtime-build-source "$@" ;;
  help|-h|--help) usage ;;
  *) printf 'Unknown runtime core command: %s\n\n' "$command" >&2; usage >&2; exit 2 ;;
esac