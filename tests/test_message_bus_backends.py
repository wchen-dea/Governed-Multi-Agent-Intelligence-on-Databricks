from aiserver.services.message_bus import (
    AsyncMessageBus,
    KafkaMessageBus,
    NoOpMessageBus,
    RabbitMQMessageBus,
    StructuredLoggingMessageBus,
    UcAuditTableMessageBus,
    default_message_bus,
)
from aiserver.shared.settings import AppSettings


def _settings(**kwargs) -> AppSettings:
    values = AppSettings().__dict__.copy()
    values.update(kwargs)
    return AppSettings(**values)


def test_default_message_bus_structured_logging_backend():
    bus = default_message_bus(_settings(message_bus_backend="structured_logging"))
    assert isinstance(bus, StructuredLoggingMessageBus)


def test_default_message_bus_noop_backend():
    bus = default_message_bus(_settings(message_bus_backend="noop"))
    assert isinstance(bus, NoOpMessageBus)


def test_default_message_bus_unknown_backend_falls_back_to_structured_logging():
    bus = default_message_bus(_settings(message_bus_backend="unknown"))
    assert isinstance(bus, StructuredLoggingMessageBus)


def test_default_message_bus_async_wraps_structured_logging_backend():
    bus = default_message_bus(
        _settings(
            message_bus_backend="structured_logging",
            message_bus_async=True,
            message_bus_async_queue_size=16,
        )
    )
    assert isinstance(bus, AsyncMessageBus)


def test_default_message_bus_kafka_backend_fail_open_falls_back_without_kafka_dependency():
    bus = default_message_bus(
        _settings(
            message_bus_backend="kafka",
            message_bus_kafka_bootstrap_servers="localhost:9092",
            message_bus_fail_open=True,
        )
    )
    assert isinstance(bus, StructuredLoggingMessageBus)


def test_default_message_bus_kafka_backend_fail_closed_raises_without_dependency():
    settings = _settings(
        message_bus_backend="kafka",
        message_bus_kafka_bootstrap_servers="localhost:9092",
        message_bus_fail_open=False,
    )
    try:
        default_message_bus(settings)
    except RuntimeError:
        return
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"Expected RuntimeError, got {type(exc).__name__}") from exc
    raise AssertionError("Expected RuntimeError for fail-closed Kafka backend")


def test_kafka_message_bus_requires_bootstrap_servers():
    try:
        KafkaMessageBus(bootstrap_servers="", topic="events", client_id="app")
    except ValueError:
        return
    raise AssertionError("Expected ValueError when bootstrap servers are missing")


def test_default_message_bus_rabbitmq_backend_fail_open_falls_back_without_rabbitmq():
    bus = default_message_bus(
        _settings(
            message_bus_backend="rabbitmq",
            message_bus_rabbitmq_url="amqp://guest:guest@localhost:5672/",
            message_bus_fail_open=True,
        )
    )
    assert isinstance(bus, StructuredLoggingMessageBus)


def test_default_message_bus_rabbitmq_backend_fail_closed_raises_on_init_error():
    settings = _settings(
        message_bus_backend="rabbitmq",
        message_bus_rabbitmq_url="amqp://guest:guest@localhost:5672/",
        message_bus_fail_open=False,
    )
    try:
        default_message_bus(settings)
    except Exception:
        return
    raise AssertionError("Expected initialization error for fail-closed RabbitMQ backend")


def test_rabbitmq_message_bus_requires_url():
    try:
        RabbitMQMessageBus(url="", exchange="events")
    except ValueError:
        return
    raise AssertionError("Expected ValueError when RabbitMQ URL is missing")


def test_default_message_bus_uc_backend_fail_open_falls_back_without_config():
    bus = default_message_bus(
        _settings(
            message_bus_backend="uc_table",
            message_bus_uc_warehouse_id="",
            message_bus_uc_catalog="main",
            message_bus_uc_schema="audit",
            message_bus_uc_table="agent_lifecycle_events",
            message_bus_fail_open=True,
        )
    )
    assert isinstance(bus, StructuredLoggingMessageBus)


def test_default_message_bus_uc_backend_fail_closed_raises_without_config():
    settings = _settings(
        message_bus_backend="uc_table",
        message_bus_uc_warehouse_id="",
        message_bus_uc_catalog="main",
        message_bus_uc_schema="audit",
        message_bus_uc_table="agent_lifecycle_events",
        message_bus_fail_open=False,
    )
    try:
        default_message_bus(settings)
    except ValueError:
        return
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"Expected ValueError, got {type(exc).__name__}") from exc
    raise AssertionError("Expected ValueError for fail-closed UC backend")


def test_uc_message_bus_requires_warehouse_id():
    try:
        UcAuditTableMessageBus(
            warehouse_id="",
            catalog="main",
            schema="audit",
            table="agent_lifecycle_events",
            fail_open=True,
        )
    except ValueError:
        return
    raise AssertionError("Expected ValueError when UC warehouse id is missing")
