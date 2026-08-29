#!/bin/sh

set -eu

APP_NAME="${APP_NAME:-hitl-app-agent}"
PROFILE="${PROFILE:-DEFAULT}"
SOURCE_DIR="${HITL_SOURCE_DIR:-$(pwd)/src/hitl-agent}"
WORKSPACE_PATH="${HITL_WORKSPACE_PATH:-/Workspace/Users/$(databricks current-user me --profile "$PROFILE" --output json | jq -r '.userName')/hitl-app-agent}"

if [ ! -f "$SOURCE_DIR/app.py" ] || [ ! -f "$SOURCE_DIR/app.yaml" ] || [ ! -f "$SOURCE_DIR/requirements.txt" ]; then
    printf "HITL source directory is incomplete: %s\n" "$SOURCE_DIR" >&2
    printf "Expected app.py, app.yaml, and requirements.txt.\n" >&2
    exit 1
fi

printf "Updating App: %s\n" "$APP_NAME"
printf "Profile: %s\n" "$PROFILE"
printf "Local source: %s\n" "$SOURCE_DIR"
printf "Workspace source: %s\n" "$WORKSPACE_PATH"

databricks workspace import-dir "$SOURCE_DIR" "$WORKSPACE_PATH" --overwrite --profile "$PROFILE"

APP_EXISTS=false
BEFORE_SP=""
if APP_JSON="$(databricks apps get "$APP_NAME" --profile "$PROFILE" --output json 2>/dev/null)"; then
    APP_EXISTS=true
    BEFORE_SP="$(printf '%s' "$APP_JSON" | jq -r '.service_principal_client_id // empty')"
    printf "Existing App found; deploying update-only snapshot to preserve service principal.\n"
else
    printf "App %s does not exist; creating it once from imported source.\n" "$APP_NAME"
    databricks apps create "$APP_NAME" \
        --profile "$PROFILE" \
        --source-code-path "$WORKSPACE_PATH" \
        --description "HITL specialist that prepares governed store intervention packets"
fi

databricks apps deploy "$APP_NAME" --profile "$PROFILE" --source-code-path "$WORKSPACE_PATH"

printf "Verifying deployment...\n"
AFTER_JSON="$(databricks apps get "$APP_NAME" --profile "$PROFILE" --output json)"
AFTER_SP="$(printf '%s' "$AFTER_JSON" | jq -r '.service_principal_client_id // empty')"
if [ "$APP_EXISTS" = "true" ] && [ -n "$BEFORE_SP" ] && [ "$BEFORE_SP" != "$AFTER_SP" ]; then
    printf "App service principal changed unexpectedly: before=%s after=%s\n" "$BEFORE_SP" "$AFTER_SP" >&2
    exit 1
fi
printf '%s' "$AFTER_JSON" \
    | jq '{name,service_principal_client_id,app_status,compute_status,active_deployment:{deployment_id:.active_deployment.deployment_id,status:.active_deployment.status}}'