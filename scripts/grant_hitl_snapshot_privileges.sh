#!/bin/sh

set -eu

PROFILE="${PROFILE-DEFAULT}"
DRY_RUN="${DRY_RUN:-false}"
SNAPSHOT_TABLE="${HITL_SNAPSHOT_TABLE:-quickstart_catalog.multi_agent_schema.hitl_source_snapshot}"
JOB_PRINCIPAL="${HITL_SNAPSHOT_JOB_SERVICE_PRINCIPAL:?HITL_SNAPSHOT_JOB_SERVICE_PRINCIPAL is required}"
WAREHOUSE_ID="${HITL_WAREHOUSE_ID:?HITL_WAREHOUSE_ID is required}"

databricks_cli() {
    if [ -n "$PROFILE" ]; then databricks "$@" --profile "$PROFILE"; else databricks "$@"; fi
}

run() {
    if [ "$DRY_RUN" = "true" ]; then printf "DRY RUN:"; printf " %s" "$@"; printf "\n"; else "$@"; fi
}

catalog="${SNAPSHOT_TABLE%%.*}"
rest="${SNAPSHOT_TABLE#*.}"
schema="${rest%%.*}"
principal="$(printf '%s' "$JOB_PRINCIPAL" | tr -d '`')"

grant_sql() {
    run databricks_cli statement-execution execute --warehouse-id "$WAREHOUSE_ID" \
        --statement "$1"
}

grant_sql "GRANT USE CATALOG ON CATALOG \`$catalog\` TO \`$principal\`"
grant_sql "GRANT USE SCHEMA ON SCHEMA \`$catalog\`.\`$schema\` TO \`$principal\`"
grant_sql "GRANT SELECT ON ALL TABLES IN SCHEMA \`$catalog\`.\`$schema\` TO \`$principal\`"
grant_sql "GRANT CREATE TABLE ON SCHEMA \`$catalog\`.\`$schema\` TO \`$principal\`"
grant_sql "GRANT MODIFY ON TABLE \`$SNAPSHOT_TABLE\` TO \`$principal\`"

printf 'Snapshot refresh privileges granted to %s for %s.\n' "$JOB_PRINCIPAL" "$SNAPSHOT_TABLE"