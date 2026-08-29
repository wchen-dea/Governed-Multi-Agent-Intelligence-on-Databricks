#!/bin/sh

set -eu

APP_NAME="${APP_NAME:-hitl-app-agent}"
PROFILE="${PROFILE-DEFAULT}"
TARGET="${TARGET:-dev}"
HITL_ENV="${HITL_ENV:-$TARGET}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="${HITL_SOURCE_DIR:-$REPO_ROOT/src/hitl-agent}"

databricks_cli() {
    if [ -n "$PROFILE" ]; then
        databricks "$@" --profile "$PROFILE"
    else
        databricks "$@"
    fi
}

if [ -n "${HITL_WORKSPACE_PATH:-}" ]; then
    WORKSPACE_PATH="$HITL_WORKSPACE_PATH"
else
    CURRENT_USER="$(databricks_cli current-user me --output json | jq -r '.userName')"
    WORKSPACE_PATH="/Workspace/Users/$CURRENT_USER/hitl-app-agent"
fi

if [ -n "${HITL_WAREHOUSE_ID:-}" ]; then
    SQL_WAREHOUSE_ID="$HITL_WAREHOUSE_ID"
elif [ "$HITL_ENV" = "dev" ]; then
    SQL_WAREHOUSE_ID="b20f70f71c2f52e2"
else
    printf "HITL_WAREHOUSE_ID is required for HITL_ENV=%s\n" "$HITL_ENV" >&2
    exit 1
fi

REVENUE_TABLE="${HITL_REVENUE_TABLE:-dt_${HITL_ENV}_platinum.enterprise.store_sales_performance}"
CDI_TABLE="${HITL_CDI_TABLE:-dt_${HITL_ENV}_gold.dwh.fct_cdi_daily}"
PEER_SET_TABLE="${HITL_PEER_SET_TABLE:-dt_${HITL_ENV}_gold.dwh.brg_store_cluster_membership_group}"
STORE_DIMENSION_TABLE="${HITL_STORE_DIMENSION_TABLE:-dt_${HITL_ENV}_gold.dwh.dim_store_active}"
TREND_WINDOW_DAYS="${HITL_TREND_WINDOW_DAYS:-90}"

if [ ! -f "$SOURCE_DIR/app.py" ] || [ ! -f "$SOURCE_DIR/app.yaml" ] || [ ! -f "$SOURCE_DIR/requirements.txt" ]; then
    printf "HITL source directory is incomplete: %s\n" "$SOURCE_DIR" >&2
    printf "Expected app.py, app.yaml, and requirements.txt.\n" >&2
    exit 1
fi

printf "Updating App: %s\n" "$APP_NAME"
printf "Profile: %s\n" "$PROFILE"
printf "Local source: %s\n" "$SOURCE_DIR"
printf "Workspace source: %s\n" "$WORKSPACE_PATH"
printf "HITL env: %s\n" "$HITL_ENV"
printf "SQL warehouse: %s\n" "$SQL_WAREHOUSE_ID"

DEPLOY_SOURCE_DIR="$(mktemp -d)"
trap 'rm -rf "$DEPLOY_SOURCE_DIR"' EXIT HUP INT TERM
cp -R "$SOURCE_DIR/." "$DEPLOY_SOURCE_DIR/"
cat > "$DEPLOY_SOURCE_DIR/app.yaml" <<EOF
command:
    - uvicorn
    - app:app
    - --host
    - 0.0.0.0
    - --port
    - "8000"
env:
    - name: HITL_ENV
        value: "$HITL_ENV"
    - name: REVENUE_TABLE
        value: "$REVENUE_TABLE"
    - name: CDI_TABLE
        value: "$CDI_TABLE"
    - name: PEER_SET_TABLE
        value: "$PEER_SET_TABLE"
    - name: STORE_DIMENSION_TABLE
        value: "$STORE_DIMENSION_TABLE"
    - name: SQL_WAREHOUSE_ID
        value: "$SQL_WAREHOUSE_ID"
    - name: TREND_WINDOW_DAYS
        value: "$TREND_WINDOW_DAYS"
resources:
    - name: hitl_sql_warehouse
        sql_warehouse:
            sql_warehouse_id: "$SQL_WAREHOUSE_ID"
            permission: CAN_USE
    - name: platinum_revenue_source
        uc_securable:
            securable_full_name: "$REVENUE_TABLE"
            securable_type: TABLE
            permission: SELECT
    - name: gold_cdi_source
        uc_securable:
            securable_full_name: "$CDI_TABLE"
            securable_type: TABLE
            permission: SELECT
    - name: gold_peer_set_source
        uc_securable:
            securable_full_name: "$PEER_SET_TABLE"
            securable_type: TABLE
            permission: SELECT
    - name: gold_store_dimension_source
        uc_securable:
            securable_full_name: "$STORE_DIMENSION_TABLE"
            securable_type: TABLE
            permission: SELECT
EOF

databricks_cli workspace import-dir "$DEPLOY_SOURCE_DIR" "$WORKSPACE_PATH" --overwrite

APP_EXISTS=false
BEFORE_SP=""
if APP_JSON="$(databricks_cli apps get "$APP_NAME" --output json 2>/dev/null)"; then
    APP_EXISTS=true
    BEFORE_SP="$(printf '%s' "$APP_JSON" | jq -r '.service_principal_client_id // empty')"
    printf "Existing App found; deploying update-only snapshot to preserve service principal.\n"
else
    printf "App %s does not exist; creating it once from imported source.\n" "$APP_NAME"
    databricks_cli apps create "$APP_NAME" \
        --source-code-path "$WORKSPACE_PATH" \
        --description "HITL specialist that prepares governed store intervention packets"
fi

databricks_cli apps deploy "$APP_NAME" --source-code-path "$WORKSPACE_PATH"

printf "Verifying deployment...\n"
AFTER_JSON="$(databricks_cli apps get "$APP_NAME" --output json)"
AFTER_SP="$(printf '%s' "$AFTER_JSON" | jq -r '.service_principal_client_id // empty')"
if [ "$APP_EXISTS" = "true" ] && [ -n "$BEFORE_SP" ] && [ "$BEFORE_SP" != "$AFTER_SP" ]; then
    printf "App service principal changed unexpectedly: before=%s after=%s\n" "$BEFORE_SP" "$AFTER_SP" >&2
    exit 1
fi
printf '%s' "$AFTER_JSON" \
    | jq '{name,service_principal_client_id,app_status,compute_status,active_deployment:{deployment_id:.active_deployment.deployment_id,status:.active_deployment.status}}'