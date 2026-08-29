#!/bin/sh

set -eu

APP_NAME="${APP_NAME:-hitl-app-agent}"
PROFILE="${PROFILE:-DEFAULT}"
TARGET="${TARGET:-dev}"
HITL_ENV="${HITL_ENV:-$TARGET}"
DRY_RUN="${DRY_RUN:-false}"
WAREHOUSE_ID="${HITL_WAREHOUSE_ID:-b20f70f71c2f52e2}"
REVENUE_TABLE="${HITL_REVENUE_TABLE:-dt_${HITL_ENV}_platinum.enterprise.store_sales_performance}"
CDI_TABLE="${HITL_CDI_TABLE:-dt_${HITL_ENV}_gold.dwh.fct_cdi_daily}"
PEER_SET_TABLE="${HITL_PEER_SET_TABLE:-dt_${HITL_ENV}_gold.dwh.brg_store_cluster_membership_group}"
STORE_DIMENSION_TABLE="${HITL_STORE_DIMENSION_TABLE:-dt_${HITL_ENV}_gold.dwh.dim_store_active}"
ORCHESTRATOR_APP_NAME="${ORCHESTRATOR_APP_NAME:-}"

if [ "$DRY_RUN" = "true" ]; then
    run() {
        printf "DRY RUN:"; printf " %s" "$@"; printf "\n"
    }
else
    run() {
        "$@"
    }
fi

APP_JSON="$(databricks apps get "$APP_NAME" --profile "$PROFILE" --output json 2>/dev/null || true)"
SP_CLIENT_ID="$(printf '%s' "$APP_JSON" | jq -r '.service_principal_client_id // empty')"
if [ -z "$SP_CLIENT_ID" ] && [ "$DRY_RUN" = "true" ]; then
    SP_CLIENT_ID="dry-run-app-service-principal"
fi
if [ -z "$SP_CLIENT_ID" ]; then
    printf "Could not resolve service principal for App %s\n" "$APP_NAME" >&2
    exit 1
fi

grant_object() {
    object_type="$1"
    object_full_name="$2"
    privilege="$3"
    run databricks grants update "$object_type" "$object_full_name" --profile "$PROFILE" \
        --json "{\"changes\":[{\"principal\":\"$SP_CLIENT_ID\",\"add\":[\"$privilege\"]}]}"
    printf "Granted %s on %s %s\n" "$privilege" "$object_type" "$object_full_name"
}

grant_warehouse() {
    run databricks permissions update warehouses "$WAREHOUSE_ID" --profile "$PROFILE" \
        --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP_CLIENT_ID\",\"permission_level\":\"CAN_USE\"}]}"
    printf "Granted CAN_USE on warehouse %s\n" "$WAREHOUSE_ID"
}

grant_orchestrator_can_use() {
    if [ -z "$ORCHESTRATOR_APP_NAME" ]; then
        return
    fi
    orchestrator_json="$(databricks apps get "$ORCHESTRATOR_APP_NAME" --profile "$PROFILE" --output json 2>/dev/null || true)"
    orchestrator_sp="$(printf '%s' "$orchestrator_json" | jq -r '.service_principal_client_id // empty')"
    if [ -z "$orchestrator_sp" ] && [ "$DRY_RUN" = "true" ]; then
        orchestrator_sp="dry-run-orchestrator-service-principal"
    fi
    if [ -z "$orchestrator_sp" ]; then
        printf "Could not resolve service principal for orchestrator App %s\n" "$ORCHESTRATOR_APP_NAME" >&2
        exit 1
    fi
    run databricks apps update-permissions "$APP_NAME" --profile "$PROFILE" \
        --service-principal "$orchestrator_sp" \
        --permission-level CAN_USE
    printf "Granted orchestrator App %s CAN_USE on HITL App %s\n" "$ORCHESTRATOR_APP_NAME" "$APP_NAME"
}

grant_table_with_usage() {
    table_full_name="$1"
    table_catalog="${table_full_name%%.*}"
    table_rest="${table_full_name#*.}"
    table_schema="${table_rest%%.*}"
    if [ -z "$table_catalog" ] || [ -z "$table_schema" ] || [ "$table_catalog" = "$table_full_name" ] || [ "$table_schema" = "$table_rest" ]; then
        printf "Invalid fully qualified table name: %s\n" "$table_full_name" >&2
        exit 1
    fi
    grant_object catalog "$table_catalog" USE_CATALOG
    grant_object schema "$table_catalog.$table_schema" USE_SCHEMA
    grant_object table "$table_full_name" SELECT
}

printf "HITL App: %s\n" "$APP_NAME"
printf "Service principal: %s\n" "$SP_CLIENT_ID"
printf "Profile: %s\n" "$PROFILE"

grant_warehouse
grant_table_with_usage "$REVENUE_TABLE"
grant_table_with_usage "$CDI_TABLE"
grant_table_with_usage "$PEER_SET_TABLE"
grant_table_with_usage "$STORE_DIMENSION_TABLE"
grant_orchestrator_can_use

printf "HITL specialist privilege update completed%s.\n" \
    "$(if [ "$DRY_RUN" = "true" ]; then printf ' (dry run)'; fi)"