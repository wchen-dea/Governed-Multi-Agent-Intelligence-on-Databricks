SHELL := /bin/sh
.DEFAULT_GOAL := help
MAKEFLAGS += --no-builtin-rules

.PHONY: help test lint lint-markdown format runtime-core assistant-tools evaluate evaluate-strict triage-evaluation build-app-source

help:
	@printf "Local development workflow\n\n"
	@printf "Targets:\n"
	@printf "  make test              Run the local test suite\n"
	@printf "  make lint              Run local Python, React, and Markdown lint checks\n"
	@printf "  make lint-markdown     Run local Markdown lint checks\n"
	@printf "  make format            Apply local Python and React formatting\n"
	@printf "  make runtime-core      Show local runtime-core commands\n"
	@printf "  make assistant-tools   Show local assistant/operations commands\n"
	@printf "  make evaluate          Run the local MLflow GenAI evaluation\n"
	@printf "  make evaluate-strict   Run evaluation with all KPI gates required\n"
	@printf "  make triage-evaluation Classify a local evaluation run\n"
	@printf "  make build-app-source  Build the local wheel + React app-source payload\n"
	@printf "\nDeployment is owned by the DAB and CI/CD workflow.\n"

test:
	uv run python -m pytest -q

lint:
	./scripts/lint_code.sh

lint-markdown:
	./scripts/lint_markdown.sh

format:
	./scripts/format_code.sh

runtime-core:
	./scripts/runtime_core.sh help

assistant-tools:
	./scripts/assistant_tools.sh help

evaluate:
	uv run assistant-evaluate

evaluate-strict:
	EVAL_REQUIRE_ALL_KPIS=true uv run assistant-evaluate

triage-evaluation:
	uv run assistant-triage-evaluation $(if $(RUN_ID),--run-id $(RUN_ID)) $(if $(EXPERIMENT_ID),--experiment-id $(EXPERIMENT_ID))

build-app-source:
	TARGET="$(TARGET)" uv run runtime-build-source
