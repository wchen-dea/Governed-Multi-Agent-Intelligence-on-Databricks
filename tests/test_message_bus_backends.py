from aiserver.config.settings import AppSettings
from aiserver.infrastructure.messaging.bus import (
    AsyncMessageBus,
    KafkaMessageBus,
    NoOpMessageBus,
    RabbitMQMessageBus,
    StructuredLoggingMessageBus,
    UcAuditTableMessageBus,
    default_message_bus,
)
from aiserver.infrastructure.persistence.approvals import UcApprovalRepository
from aiserver.contracts.responses import ApprovalDecisionRecord


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


def test_async_message_bus_requires_fail_open_behavior():
    try:
        default_message_bus(
            _settings(
                message_bus_backend="structured_logging",
                message_bus_async=True,
                message_bus_fail_open=False,
            )
        )
    except ValueError as exc:
        assert "MESSAGE_BUS_ASYNC" in str(exc)
        return
    raise AssertionError("Expected async fail-closed configuration to be rejected")


def test_kafka_message_bus_flushes_on_close(monkeypatch):
    class FakeProducer:
        def __init__(self, config):
            del config
            self.flush_timeout = None

        def flush(self, timeout):
            self.flush_timeout = timeout

    producer = FakeProducer({})

    class FakeProducerModule:
        def Producer(self, config):
            del config
            return producer

    monkeypatch.setattr(
        "aiserver.infrastructure.messaging.bus.import_module",
        lambda name: FakeProducerModule(),
    )
    bus = KafkaMessageBus("localhost:9092", "events", "app")

    bus.close()

    assert producer.flush_timeout == 10.0


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


def test_uc_approval_repository_upserts_and_reads_decisions():
    class Result:
        data_array = [[
            "req-123",
            "store-intervention-agent",
            "store-123",
            "sam.manager",
            "approved",
            "Looks good",
            "Proceed",
            "approved",
        ]]

    class Response:
        result = Result()

    class StatementExecution:
        def __init__(self):
            self.statements = []

        def execute_statement(self, **kwargs):
            self.statements.append(kwargs)
            if kwargs["statement"].startswith("SELECT"):
                return Response()
            return None

    class Workspace:
        def __init__(self):
            self.statement_execution = StatementExecution()

    workspace = Workspace()
    repository = UcApprovalRepository(
        warehouse_id="wh-1",
        catalog="main",
        schema="audit",
        table="agent_approval_decisions",
        fail_open=False,
        workspace_client=workspace,
    )
    record = ApprovalDecisionRecord(
        request_id="req-123",
        agent_name="store-intervention-agent",
        store_id="store-123",
        approver="sam.manager",
        decision="approved",
        reason="Looks good",
        notes="Proceed",
        status="approved",
    )

    repository.save(record)
    loaded = repository.get("req-123")

    assert loaded == record
    assert any("MERGE INTO main.audit.agent_approval_decisions" in item["statement"]
               for item in workspace.statement_execution.statements)
    assert any("CREATE TABLE IF NOT EXISTS main.audit.agent_approval_decisions" in item["statement"]
               for item in workspace.statement_execution.statements)
