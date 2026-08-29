#!/bin/sh

set -eu

APP_NAME="${APP_NAME:-hitl-app-agent}"
PROFILE="${PROFILE:-DEFAULT}"
DRY_RUN="${DRY_RUN:-false}"
WAREHOUSE_ID="${HITL_WAREHOUSE_ID:-b20f70f71c2f52e2}"
REVENUE_TABLE="${HITL_REVENUE_TABLE:-dt_dev_platinum.enterprise.store_sales_performance}"
CDI_TABLE="${HITL_CDI_TABLE:-dt_dev_gold.dwh.fct_cdi_daily}"
PEER_SET_TABLE="${HITL_PEER_SET_TABLE:-dt_dev_gold.dwh.brg_store_cluster_membership_group}"
STORE_DIMENSION_TABLE="${HITL_STORE_DIMENSION_TABLE:-dt_dev_gold.dwh.dim_store_active}"

if [ "$DRY_RUN" = "true" ]; then
    run() {
        printf "DRY RUN:"; printf " %s" "$@"; printf "\n"
    }
else
    run() {
        "$@"
    }
fi

APP_JSON="$(databricks apps get "$APP_NAME" --profile "$PROFILE" --output json)"
SP_CLIENT_ID="$(printf '%s' "$APP_JSON" | jq -r '.service_principal_client_id // empty')"
if [ -z "$SP_CLIENT_ID" ]; then
    printf "Could not resolve service principal for App %s\n" "$APP_NAME" >&2
    exit 1
fi

grant_object() {
    object_type="$1"
    full_name="$2"
    privilege="$3"
    run databricks grants update "$object_type" "$full_name" --profile "$PROFILE" \
        --json "{\"changes\":[{\"principal\":\"$SP_CLIENT_ID\",\"add\":[\"$privilege\"]}]}"
    printf "Granted %s on %s %s\n" "$privilege" "$object_type" "$full_name"
}

grant_warehouse() {
    run databricks permissions update warehouses "$WAREHOUSE_ID" --profile "$PROFILE" \
        --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP_CLIENT_ID\",\"permission_level\":\"CAN_USE\"}]}"
    printf "Granted CAN_USE on warehouse %s\n" "$WAREHOUSE_ID"
}

printf "HITL App: %s\n" "$APP_NAME"
printf "Service principal: %s\n" "$SP_CLIENT_ID"
printf "Profile: %s\n" "$PROFILE"

grant_warehouse
grant_object catalog dt_dev_platinum USE_CATALOG
grant_object schema dt_dev_platinum.enterprise USE_SCHEMA
grant_object table "$REVENUE_TABLE" SELECT
grant_object catalog dt_dev_gold USE_CATALOG
grant_object schema dt_dev_gold.dwh USE_SCHEMA
grant_object table "$CDI_TABLE" SELECT
grant_object table "$PEER_SET_TABLE" SELECT
grant_object table "$STORE_DIMENSION_TABLE" SELECT

printf "HITL specialist privilege update completed%s.\n" \
    "$(if [ "$DRY_RUN" = "true" ]; then printf ' (dry run)'; fi)"