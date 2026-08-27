# ADR 0004: Use Lifecycle Message Bus Abstraction with Pluggable Transports

## Status

Accepted

## Context

The orchestrator needed durable request and tool lifecycle telemetry without tightly coupling business logic to a specific transport. Different environments have different infrastructure (local dev has no Kafka; production needs UC audit tables).

## Decision

Introduce a `MessageBus` protocol and publish lifecycle events across handlers, runtime auth, and tool execution. Support multiple backends selected at runtime via environment configuration.

### Supported backends

| Backend | Class | Use Case |
|---------|-------|----------|
| `noop` | `NoOpMessageBus` | Discard events silently (testing) |
| `structured_logging` | `StructuredLoggingMessageBus` | JSON log records (default, local dev) |
| `kafka` | `KafkaMessageBus` | confluent-kafka producer to topic |
| `rabbitmq` | `RabbitMQMessageBus` | pika AMQP topic exchange |
| `uc_table` | `UcAuditTableMessageBus` | UC Delta table via SQL Statement API |

### Runtime behavior

- Backend selection: `MESSAGE_BUS_BACKEND` env var → `default_message_bus(settings)` factory.
- Fail-open: when `MESSAGE_BUS_FAIL_OPEN=true` (default), backend construction failure falls back to `StructuredLoggingMessageBus`.
- Async wrapper: when `MESSAGE_BUS_ASYNC=true`, wraps the chosen backend in `AsyncMessageBus` (background queue worker with configurable queue size and drain timeout).
- Event envelope: every event carries `event_id` (UUID), `event_type`, `ts` (ISO timestamp), `payload` (dict).

### Event types emitted

```
request.invoke.started / succeeded / failed
request.stream.started / succeeded / failed
response.guardrail.passed / blocked
auth.identity.resolved
auth.context.built
auth.trace.metadata.updated
policy.subagent.decision (result: allow | deny)
```

## Alternatives Considered

- Write lifecycle telemetry directly to logs only — rejected because it prevents durable querying and audit compliance.
- Couple telemetry emission directly to Kafka — rejected because not all environments have Kafka.
- Use OpenTelemetry as the bus protocol — rejected because lifecycle events are domain-scoped, not generic traces.

## Consequences

### Positive

- Consistent lifecycle event model independent of transport.
- Operational flexibility — swap backends per environment without code changes.
- Fail-open behavior prevents event infrastructure from taking down request paths.
- Async option avoids blocking request latency on slow backends.

### Trade-offs

- Additional config surface (6 env vars for Kafka/RabbitMQ/UC).
- Backend-specific runtime failure modes require runbook guidance.
- Fail-open can silently drop events if operators don't monitor fallback activation.

## Implementation Notes

- Protocol + all backends: [src/aiserver/services/message_bus.py](../../src/aiserver/services/message_bus.py)
- Settings fields: `message_bus_backend`, `message_bus_topic`, `message_bus_fail_open`, `message_bus_async`, `message_bus_async_queue_size`, `message_bus_async_drain_timeout_seconds` in [src/aiserver/shared/settings.py](../../src/aiserver/shared/settings.py)
- Current dev config: `MESSAGE_BUS_BACKEND=uc_table` (writes to `quickstart_catalog.multi_agent_schema.agent_lifecycle_events`)
- Handler publishing: [src/aiserver/api/handlers.py](../../src/aiserver/api/handlers.py)
- Tests: [tests/test_message_bus_backends.py](../../tests/test_message_bus_backends.py), [tests/test_message_bus_integration.py](../../tests/test_message_bus_integration.py)
