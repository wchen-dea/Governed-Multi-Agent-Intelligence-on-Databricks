# ADR 0006: Persist Lifecycle Events to Unity Catalog Audit Table

## Status

Accepted

## Context

Lifecycle telemetry was available through logging and broker backends (ADR 0004), but compliance and lineage analytics require governed, queryable, durable storage accessible via standard SQL and subject to Unity Catalog access controls.

## Decision

Add a `uc_table` message bus backend (`UcAuditTableMessageBus`) that writes normalized lifecycle events into a Unity Catalog Delta table through the Databricks SQL Statement Execution API.

### Persisted schema

| Column | Type | Notes |
|--------|------|-------|
| `event_date` | DATE | Partition column, derived from `event_ts` |
| `event_id` | STRING | UUID per event |
| `event_type` | STRING | e.g., `request.invoke.started` |
| `event_ts` | TIMESTAMP | ISO 8601 timestamp |
| `event_payload` | STRING | JSON-serialized payload dict |

### Runtime behavior

- Auto-creates schema and table if missing (using `CREATE TABLE IF NOT EXISTS`).
- Validates catalog/schema/table identifiers against SQL injection patterns via `_validate_identifier()`.
- Writes via SQL `INSERT INTO` through the Statement Execution API using a configured SQL warehouse.
- Respects `MESSAGE_BUS_FAIL_OPEN` — on failure, falls back to structured logging without blocking the request.

### Current dev configuration

```
UC_AUDIT_WAREHOUSE_ID=b20f70f71c2f52e2
UC_AUDIT_CATALOG=quickstart_catalog
UC_AUDIT_SCHEMA=multi_agent_schema
UC_AUDIT_TABLE=agent_lifecycle_events
```

Full table path: `quickstart_catalog.multi_agent_schema.agent_lifecycle_events`

## Alternatives Considered

- Keep telemetry in broker/log sinks only and query externally.
- Push events through batch ETL instead of direct write at publish time.
- Use a non-governed application database table (e.g., Lakebase).
- Use Databricks App telemetry tables (`app_logs`, `app_metrics`) instead of custom audit table.

## Consequences

### Positive

- Provides governed, auditable, and SQL-queryable lifecycle history.
- Subject to Unity Catalog access controls and lineage tracking.
- Improves compliance posture and post-incident forensic analysis.
- Consistent event envelope format across all message bus backends.
- Partitioned by date for efficient time-range queries.

### Trade-offs

- Requires SQL warehouse to be running and UC grants to be configured.
- Adds write latency to the message publishing path (mitigated by fail-open + async wrapper option).
- Warehouse cold-start can delay first event write.

## Implementation Notes

- Backend implementation: [src/aiserver/services/message_bus.py](../../src/aiserver/services/message_bus.py) (`UcAuditTableMessageBus`)
- Settings fields: `message_bus_uc_warehouse_id`, `message_bus_uc_catalog`, `message_bus_uc_schema`, `message_bus_uc_table` in [src/aiserver/shared/settings.py](../../src/aiserver/shared/settings.py)
- Bundle variables: `uc_audit_warehouse_id`, `uc_audit_catalog`, `uc_audit_schema`, `uc_audit_table` in [databricks.yml](../../databricks.yml)
- Per-target values: [targets/dev.yml](../../targets/dev.yml), [targets/qa.yml](../../targets/qa.yml), [targets/stg.yml](../../targets/stg.yml), [targets/prd.yml](../../targets/prd.yml)
- Tests: [tests/test_message_bus_backends.py](../../tests/test_message_bus_backends.py)
