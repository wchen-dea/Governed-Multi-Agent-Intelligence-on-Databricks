#!/bin/sh
set -eu

uv run ruff format src tests
npm --prefix src/reactui run format