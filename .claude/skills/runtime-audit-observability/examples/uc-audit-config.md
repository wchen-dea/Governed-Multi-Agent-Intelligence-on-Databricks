# UC Audit Config Example

Use this baseline for target overlays:

```yaml
message_bus_backend: uc_table
uc_audit_warehouse_id: <warehouse-id>
uc_audit_catalog: main
uc_audit_schema: observability
uc_audit_table: agent_lifecycle_events
```

Before promotion, confirm placeholders are replaced and writes succeed in target.
