SHELL := /bin/sh
.DEFAULT_GOAL := help
MAKEFLAGS += --no-builtin-rules

PROFILE ?= DEFAULT
TARGET ?= dev
APP_NAME ?= multiagent-app-dev
HITL_APP_NAME ?= hitl-app-agent

.PHONY: help test lint lint-markdown format runtime-core assistant-tools evaluate evaluate-strict triage-evaluation build-app-source stop deploy source-data-tables ai-search-index ai-search metric-view genie-agents delta-table hitl-app apps wheel-package-upload app-deployment

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
	@printf "\nOrdered deployment workflow (TARGET=$(TARGET), PROFILE=$(PROFILE)):\n"
	@printf "  make deploy            Run the complete dependency-ordered deployment\n"
	@printf "  make source-data-tables  Verify upstream source-table prerequisites\n"
	@printf "  make ai-search-index   Build/refresh AI Search indexes\n"
	@printf "  make ai-search         Verify AI Search endpoints after indexes\n"
	@printf "  make metric-view       Build/refresh the CDI metric view\n"
	@printf "  make genie-agents      Verify externally owned Genie Agent spaces\n"
	@printf "  make delta-table       Refresh the HITL Delta snapshot table\n"
	@printf "  make hitl-app          Stage the HITL app dependency\n"
	@printf "  make apps              Stage bundle app resources\n"
	@printf "  make wheel-package-upload  Build and upload the wheel artifact\n"
	@printf "  make app-deployment    Deploy the HITL and main apps\n"
	@printf "  make stop               Stop Databricks Apps\n"
	@printf "\nUse TARGET=<dev|qa|stg|prd> and PROFILE=<databricks-profile> as needed.\n"

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

# The upstream ingestion projects own these tables. Keep this prerequisite in
# the graph so the deployment order is explicit without recreating their data.
source-data-tables:
	@printf "Source tables are upstream prerequisites for TARGET=%s; no local creation step is configured.\n" "$(TARGET)"

ai-search-index: source-data-tables
	databricks bundle run create-gmai-mcp-agent-product-search-index -t "$(TARGET)" -p "$(PROFILE)"
	databricks bundle run create-gmai-mcp-agent-flink-support-index -t "$(TARGET)" -p "$(PROFILE)"

# The AI Search endpoints are configured by target variables and consumed by
# the index jobs; the bundle does not own endpoint creation.
ai-search: ai-search-index
	@printf "AI Search indexes and configured endpoints are ready for TARGET=%s.\n" "$(TARGET)"

metric-view: ai-search
	databricks bundle run create-gmai-genie-agent-cdi-metric-view -t "$(TARGET)" -p "$(PROFILE)"

# Genie Agent spaces are owned externally; this target preserves their place in
# the dependency graph before HITL data and app deployment.
genie-agents: metric-view
	@printf "Genie Agent spaces are externally managed prerequisites for TARGET=%s.\n" "$(TARGET)"

delta-table: genie-agents
	databricks bundle run refresh-hitl-source-snapshot -t "$(TARGET)" -p "$(PROFILE)"

hitl-app: delta-table
	@printf "HITL app dependency is ready for TARGET=%s.\n" "$(TARGET)"

apps: hitl-app
	@printf "Bundle app resources are staged for TARGET=%s.\n" "$(TARGET)"

wheel-package-upload: apps
	TARGET="$(TARGET)" uv run runtime-build-source
	databricks bundle deploy -t "$(TARGET)" -p "$(PROFILE)"

app-deployment: wheel-package-upload
	databricks bundle run create-or-deploy-multiagent-app -t "$(TARGET)" -p "$(PROFILE)"

deploy: app-deployment

stop:
	@for app in "$(APP_NAME)" "$(HITL_APP_NAME)"; do \
		databricks apps stop "$$app" --profile "$(PROFILE)"; \
	done
