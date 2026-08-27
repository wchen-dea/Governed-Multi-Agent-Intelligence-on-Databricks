#!/bin/sh
set -eu

uv run ruff check src tests
npm --prefix src/aiweb run lint
./scripts/lint_markdown.sh