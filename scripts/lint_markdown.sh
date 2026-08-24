#!/bin/sh

set -eu

cd "$(dirname "$0")/.."

exec npx --yes markdownlint-cli2@0.18.1 \
  'README.md' \
  'CONTRIBUTING.md' \
  'docs/**/*.md' \
  'src/**/*.md' \
  '!**/node_modules/**' \
  '!**/dist/**' \
  '!**/.databricks_app_source/**'