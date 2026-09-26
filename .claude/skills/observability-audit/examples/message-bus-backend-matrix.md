# Message Bus Backend Matrix

| Backend | Primary Use | Required Config |
|---|---|---|
| structured_logging | default local/runtime logs | MESSAGE_BUS_BACKEND=structured_logging |
| noop | disable publishing | MESSAGE_BUS_BACKEND=noop |
| kafka | event streaming integration | KAFKA_BOOTSTRAP_SERVERS, KAFKA_CLIENT_ID |
| rabbitmq | AMQP integration | RABBITMQ_URL |
| uc_table | governed audit persistence | UC_AUDIT_WAREHOUSE_ID, UC_AUDIT_CATALOG, UC_AUDIT_SCHEMA, UC_AUDIT_TABLE |
