SHELL := /bin/sh

.PHONY: help test lint-markdown evaluate evaluate-strict build-app-source validate bundle-deploy bundle-deploy-optional import ensure-running stop deploy grant-runtime-permissions redeploy health smoke smoke-governance query-dev logs status

PROFILE ?= DEFAULT
TARGET ?= dev
APP_NAME ?= multiagent-app-$(TARGET)
APP_START_MAX_ATTEMPTS ?= 30
APP_START_POLL_SECONDS ?= 2
APP_DEPLOY_MAX_ATTEMPTS ?= 60
APP_DEPLOY_POLL_SECONDS ?= 2
PERMISSIONS_FAIL_OPEN ?= true
PERMISSIONS_DRY_RUN ?= false
QUERY ?= ping
QUERY_PERSONA ?= manager

APP_GET_JSON = databricks apps get "$(APP_NAME)" --profile "$(PROFILE)" --output json

help:
	@printf "Local dev Databricks app workflow\n\n"
	@printf "Targets:\n"
	@printf "  make test              Run local test suite\n"
	@printf "  make lint-markdown     Run pinned Markdown lint checks\n"
	@printf "  make evaluate          Run MLflow GenAI evaluation and release gate\n"
	@printf "  make evaluate-strict   Run evaluation with all KPI gates required\n"
	@printf "  make build-app-source  Build wheel + React UI app source payload\n"
	@printf "  make validate          Validate Databricks bundle for TARGET\n"
	@printf "  make bundle-deploy     Try bundle deploy for TARGET (may fail on Terraform registry)\n"
	@printf "  make import            Upload .databricks_app_source into app workspace path\n"
	@printf "  make stop              Stop app compute for APP_NAME\n"
	@printf "  make deploy            Deploy uploaded app source with Databricks Apps\n"
	@printf "  make grant-runtime-permissions  Grant app SP permissions on Genie Agents/UC/AI Search/serving/warehouse\n"
	@printf "  make redeploy          Full redeploy with auto fallback: validate, try bundle deploy, then import/deploy/permissions/health/smoke\n"
	@printf "  make health            Verify app deployment/app state is healthy\n"
	@printf "  make smoke            Smoke-check app URL, React index shell, and /invocations route\n"
	@printf "  make query-dev        Invoke /invocations with bearer auth (QUERY, QUERY_PERSONA)\n"
	@printf "  make status            Print current app status JSON\n"
	@printf "  make logs              Tail recent app logs\n"
	@printf "\n"
	@printf "Examples:\n"
	@printf "  make redeploy TARGET=dev APP_NAME=multiagent-app-dev\n"
	@printf "  make health TARGET=qa APP_NAME=multiagent-app-qa\n"
	@printf "  make query-dev TARGET=dev APP_NAME=multiagent-app-dev QUERY='top stores by revenue' QUERY_PERSONA=manager\n"

test:
	uv run pytest -q

lint-markdown:
	./scripts/lint_markdown.sh

evaluate:
	uv run agent-evaluate

evaluate-strict:
	EVAL_REQUIRE_ALL_KPIS=true uv run agent-evaluate

build-app-source:
	uv run prepare-app-source

validate:
	databricks bundle validate -t "$(TARGET)" --profile "$(PROFILE)"

bundle-deploy:
	@databricks bundle deploy -t "$(TARGET)" --profile "$(PROFILE)" || \
		(printf "bundle deploy failed; use make redeploy for the Terraform-free fallback path\n" && exit 1)

bundle-deploy-optional:
	@databricks bundle deploy -t "$(TARGET)" --profile "$(PROFILE)" || \
		printf "bundle deploy failed; continuing with Terraform-free fallback path (import -> deploy -> permissions -> health -> smoke)\n"

import: build-app-source
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_SRC="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	databricks workspace import-dir .databricks_app_source "$$APP_SRC" --overwrite --profile "$(PROFILE)"

ensure-running:
	@printf "Ensuring app %s is RUNNING...\n" "$(APP_NAME)"; \
	databricks apps start "$(APP_NAME)" --profile "$(PROFILE)" >/dev/null 2>&1 || true; \
	APP_STATE=""; \
	ATTEMPT=0; \
	while [ $$ATTEMPT -lt "$(APP_START_MAX_ATTEMPTS)" ]; do \
		APP_STATE="$$($(APP_GET_JSON) | jq -r '.app_status.state')"; \
		printf "  start-check attempt=%s/%s state=%s\n" "$$((ATTEMPT + 1))" "$(APP_START_MAX_ATTEMPTS)" "$$APP_STATE"; \
		if [ "$$APP_STATE" = "RUNNING" ]; then \
			printf "App %s is RUNNING.\n" "$(APP_NAME)"; \
			exit 0; \
		fi; \
		ATTEMPT=$$((ATTEMPT + 1)); \
		sleep "$(APP_START_POLL_SECONDS)"; \
	done; \
	printf "App $(APP_NAME) is not RUNNING (state=%s)\n" "$$APP_STATE" >&2; \
	exit 1

stop:
	@databricks apps stop "$(APP_NAME)" --profile "$(PROFILE)" >/dev/null 2>&1 || true; \
	APP_STATE="$$($(APP_GET_JSON) | jq -r '.app_status.state')"; \
	COMPUTE_STATE="$$($(APP_GET_JSON) | jq -r '.compute_status.state')"; \
	printf "app=%s\ncompute=%s\n" "$$APP_STATE" "$$COMPUTE_STATE"; \
	if [ "$$COMPUTE_STATE" != "STOPPED" ]; then \
		printf "App $(APP_NAME) compute is not STOPPED (compute=%s)\n" "$$COMPUTE_STATE" >&2; \
		exit 1; \
	fi

deploy:
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_SRC="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	APP_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.app_status.state // "UNKNOWN"')"; \
	DEPLOY_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status.state // "NONE"')"; \
	ATTEMPT=0; \
	if [ -z "$$APP_SRC" ] || [ "$$APP_SRC" = "null" ]; then \
		printf "Could not resolve default_source_code_path for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	if [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App %s is in state=%s; continuing deploy without RUNNING precondition.\n" "$(APP_NAME)" "$$APP_STATE"; \
		databricks apps start "$(APP_NAME)" --profile "$(PROFILE)" >/dev/null 2>&1 || true; \
	fi; \
	while [ "$$DEPLOY_STATE" = "IN_PROGRESS" ] && [ $$ATTEMPT -lt "$(APP_DEPLOY_MAX_ATTEMPTS)" ]; do \
		printf "Waiting for active deployment lock to clear: attempt=%s/%s state=%s\n" "$$((ATTEMPT + 1))" "$(APP_DEPLOY_MAX_ATTEMPTS)" "$$DEPLOY_STATE"; \
		ATTEMPT=$$((ATTEMPT + 1)); \
		sleep "$(APP_DEPLOY_POLL_SECONDS)"; \
		APP_JSON="$$($(APP_GET_JSON))"; \
		DEPLOY_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status.state // "NONE"')"; \
	done; \
	if [ "$$DEPLOY_STATE" = "IN_PROGRESS" ]; then \
		printf "Active deployment still in progress for %s after %s attempts.\n" "$(APP_NAME)" "$(APP_DEPLOY_MAX_ATTEMPTS)" >&2; \
		exit 1; \
	fi; \
	printf "Deploying app %s from source path: %s\n" "$(APP_NAME)" "$$APP_SRC"; \
	databricks apps deploy "$(APP_NAME)" --profile "$(PROFILE)" --source-code-path "$$APP_SRC" --mode SNAPSHOT

grant-runtime-permissions:
	@set -e; \
	FLAGS=""; \
	if [ "$(PERMISSIONS_DRY_RUN)" = "true" ]; then FLAGS="$$FLAGS --dry-run"; fi; \
	if [ "$(PERMISSIONS_FAIL_OPEN)" = "true" ]; then FLAGS="$$FLAGS --fail-open"; fi; \
	uv run python src/scripts/grant_app_runtime_permissions.py \
		--app-name "$(APP_NAME)" \
		--target "$(TARGET)" \
		--profile "$(PROFILE)" \
		$$FLAGS

redeploy: build-app-source validate bundle-deploy-optional import deploy grant-runtime-permissions health smoke

health:
	@APP_JSON="$$($(APP_GET_JSON))"; \
	DEPLOY_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status.state')"; \
	APP_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.app_status.state')"; \
	COMPUTE_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.compute_status.state')"; \
	SOURCE_PATH="$$(printf "%s" "$$APP_JSON" | jq -r '.default_source_code_path')"; \
	printf "deployment=%s\napp=%s\ncompute=%s\nsource=%s\n" "$$DEPLOY_STATE" "$$APP_STATE" "$$COMPUTE_STATE" "$$SOURCE_PATH"; \
	if [ "$$DEPLOY_STATE" != "SUCCEEDED" ] || [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App health check failed for $(APP_NAME)\n" >&2; \
		printf "%s" "$$APP_JSON" | jq -r '.active_deployment.status, .app_status, .compute_status' >&2; \
		exit 1; \
	fi

smoke:
	@APP_JSON="$$($(APP_GET_JSON))"; \
	APP_URL="$$(printf "%s" "$$APP_JSON" | jq -r '.url')"; \
	APP_STATE="$$(printf "%s" "$$APP_JSON" | jq -r '.app_status.state')"; \
	if [ -z "$$APP_URL" ] || [ "$$APP_URL" = "null" ]; then \
		printf "Could not resolve app URL for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	if [ "$$APP_STATE" != "RUNNING" ]; then \
		printf "App $(APP_NAME) is not RUNNING (state=%s)\n" "$$APP_STATE" >&2; \
		exit 1; \
	fi; \
	ROOT_TMP="$$(mktemp)"; \
	ROOT_CODE="$$(curl --noproxy '*' -sS -o "$$ROOT_TMP" -w '%{http_code}' "$$APP_URL")"; \
	printf "smoke.root.url=%s\nsmoke.root.code=%s\n" "$$APP_URL" "$$ROOT_CODE"; \
	case "$$ROOT_CODE" in \
		200|302|401|403) ;; \
		*) printf "Unexpected root status code: %s\n" "$$ROOT_CODE" >&2; rm -f "$$ROOT_TMP"; exit 1 ;; \
	esac; \
	if [ "$$ROOT_CODE" = "200" ]; then \
		if ! grep -q '<div id="root"></div>' "$$ROOT_TMP"; then \
			printf "Root page does not contain expected React shell marker\n" >&2; \
			rm -f "$$ROOT_TMP"; \
			exit 1; \
		fi; \
	fi; \
	rm -f "$$ROOT_TMP"; \
	INV_TMP="$$(mktemp)"; \
	INV_CODE="$$(curl --noproxy '*' -sS -o "$$INV_TMP" -w '%{http_code}' -X POST "$${APP_URL%/}/invocations" -H 'content-type: application/json' --data '{"input":[{"role":"user","content":"ping"}],"stream":false}')"; \
	printf "smoke.invocations.code=%s\n" "$$INV_CODE"; \
	if [ "$$INV_CODE" = "404" ] || [ "$$INV_CODE" = "000" ]; then \
		printf "/invocations route is not reachable through React UI proxy\n" >&2; \
		rm -f "$$INV_TMP"; \
		exit 1; \
	fi; \
	rm -f "$$INV_TMP"; \
	printf "Smoke checks passed for $(APP_NAME)\n"

smoke-governance:
	@set -e; \
	if [ -z "$(TOKEN)" ]; then printf "TOKEN is required for governance smoke checks\n" >&2; exit 1; fi; \
	APP_JSON="$$($(APP_GET_JSON))"; \
	APP_URL="$$(printf "%s" "$$APP_JSON" | jq -r '.url')"; \
	PAYLOAD='$${PAYLOAD:-{"input":[{"role":"user","content":"ping"}],"stream":false,"custom_inputs":{"persona":"manager"}}}'; \
	RESP_TMP="$$(mktemp)"; \
	CODE="$$(curl --noproxy '*' -sS -o "$$RESP_TMP" -w '%{http_code}' -X POST "$${APP_URL%/}/invocations" -H 'content-type: application/json' -H "authorization: Bearer $(TOKEN)" --data "$$PAYLOAD")"; \
	printf "governance.smoke.http_code=%s\n" "$$CODE"; cat "$$RESP_TMP"; printf "\n"; rm -f "$$RESP_TMP"; \
	if [ "$$CODE" != "200" ]; then printf "Governance smoke invocation failed\n" >&2; exit 1; fi

query-dev:
	@set -e; \
	APP_JSON="$$($(APP_GET_JSON))"; \
	APP_URL="$$(printf "%s" "$$APP_JSON" | jq -r '.url')"; \
	if [ -z "$$APP_URL" ] || [ "$$APP_URL" = "null" ]; then \
		printf "Could not resolve app URL for $(APP_NAME)\n" >&2; \
		exit 1; \
	fi; \
	TOKEN="$$(databricks auth token --profile "$(PROFILE)" --output json | jq -r '.access_token')"; \
	if [ -z "$$TOKEN" ] || [ "$$TOKEN" = "null" ]; then \
		printf "Could not resolve access token from databricks auth token for profile $(PROFILE)\n" >&2; \
		exit 1; \
	fi; \
	PAYLOAD="$$(jq -nc --arg q "$(QUERY)" --arg p "$(QUERY_PERSONA)" '{input:[{role:"user",content:$$q}],stream:false,custom_inputs:{persona:$$p}}')"; \
	RESP_TMP="$$(mktemp)"; \
	CODE="$$(curl --noproxy '*' -sS -o "$$RESP_TMP" -w '%{http_code}' -X POST "$${APP_URL%/}/invocations" -H 'content-type: application/json' -H "authorization: Bearer $$TOKEN" --data "$$PAYLOAD")"; \
	printf "query.url=%s\nquery.persona=%s\nquery.http_code=%s\n" "$$APP_URL" "$(QUERY_PERSONA)" "$$CODE"; \
	cat "$$RESP_TMP"; \
	printf "\n"; \
	rm -f "$$RESP_TMP"; \
	if [ "$$CODE" != "200" ]; then \
		printf "Invocation failed with HTTP %s\n" "$$CODE" >&2; \
		exit 1; \
	fi

status:
	$(APP_GET_JSON)

logs:
	databricks apps logs "$(APP_NAME)" --tail-lines 120 --profile "$(PROFILE)"