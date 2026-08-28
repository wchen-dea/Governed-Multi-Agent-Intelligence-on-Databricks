"""Provide message bus implementations for request-scoped lifecycle event publishing."""

import atexit
import json
import logging
import re
from datetime import UTC, datetime
from importlib import import_module
from queue import Empty, Full, Queue
from threading import Event, Thread
from uuid import uuid4

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

from aiserver.services.interfaces import MessageBus
from aiserver.shared.settings import AppSettings, get_settings

logger = logging.getLogger(__name__)


class NoOpMessageBus:
    """Discard all events when message bus emission is disabled."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Drop a lifecycle event without further processing.

        Args:
            event_type: Event type identifier.
            payload: Event payload.

        Side Effects:
            Discards all event data.
        """
        del event_type, payload


class StructuredLoggingMessageBus:
    """Publish events as structured JSON log records."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Publish a lifecycle event to structured logs.

        Args:
            event_type: Event type identifier.
            payload: Event payload.

        Side Effects:
            Emits a JSON-formatted log record.
        """
        event = _build_event(event_type, payload)
        logger.info("message_bus_event %s", json.dumps(event, sort_keys=True, default=str))


class AsyncMessageBus:
    """Publish events asynchronously through a background worker queue."""

    _SENTINEL = object()

    def __init__(
        self,
        inner: MessageBus,
        queue_size: int,
        fail_open: bool,
        drain_timeout_seconds: float,
    ) -> None:
        self._inner = inner
        self._queue: Queue[object] = Queue(maxsize=max(queue_size, 1))
        self._fail_open = fail_open
        self._drain_timeout_seconds = max(drain_timeout_seconds, 0.0)
        self._stopped = Event()
        self._worker = Thread(target=self._run, name="message-bus-worker", daemon=True)
        self._worker.start()
        atexit.register(self.close)

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except Empty:
                if self._stopped.is_set():
                    return
                continue

            try:
                if item is self._SENTINEL:
                    return
                event_type, payload = item
                self._inner.publish(event_type, payload)
            except Exception:
                if self._fail_open:
                    logger.exception(
                        "Async message bus publish failed; dropping event due to fail-open policy"
                    )
                else:
                    logger.exception("Async message bus publish failed")
            finally:
                self._queue.task_done()

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Queue a lifecycle event for asynchronous publishing."""
        item = (event_type, dict(payload))
        try:
            self._queue.put_nowait(item)
        except Full:
            if self._fail_open:
                logger.warning(
                    "Async message bus queue full; dropping event",
                    extra={"event_type": event_type},
                )
                return
            raise RuntimeError("Async message bus queue is full")

    def close(self) -> None:
        """Stop the worker with best-effort queue drain."""
        if self._stopped.is_set():
            return
        self._stopped.set()
        try:
            self._queue.put_nowait(self._SENTINEL)
        except Full:
            # Worker will stop after queue drains.
            pass
        self._worker.join(timeout=self._drain_timeout_seconds)


class KafkaMessageBus:
    """Publish lifecycle events to Kafka.

    Args:
        bootstrap_servers: Kafka bootstrap servers list.
        topic: Topic used for event publishing.
        client_id: Kafka producer client id.

    Raises:
        ValueError: If bootstrap servers are missing.
        RuntimeError: If kafka dependency is not installed.
    """

    def __init__(self, bootstrap_servers: str, topic: str, client_id: str) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS must be set when MESSAGE_BUS_BACKEND=kafka")

        try:
            producer_module = import_module("confluent_kafka")
        except Exception as exc:
            raise RuntimeError(
                "Kafka backend requires confluent-kafka. Install with `uv add confluent-kafka`."
            ) from exc

        producer_cls = getattr(producer_module, "Producer")
        self._producer = producer_cls(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
            }
        )
        self._topic = topic

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Publish a lifecycle event to Kafka.

        Args:
            event_type: Event type identifier.
            payload: Event payload.

        Side Effects:
            Sends an event message to the configured Kafka topic.
        """
        event = _build_event(event_type, payload)
        self._producer.produce(
            self._topic,
            value=json.dumps(event, default=str).encode("utf-8"),
            key=event_type.encode("utf-8"),
        )
        self._producer.poll(0)


class RabbitMQMessageBus:
    """Publish lifecycle events to RabbitMQ topic exchange.

    Args:
        url: AMQP connection URL.
        exchange: Exchange name used for topic routing.

    Raises:
        ValueError: If connection URL is missing.
        RuntimeError: If pika dependency is not installed.
    """

    def __init__(self, url: str, exchange: str) -> None:
        if not url.strip():
            raise ValueError("RABBITMQ_URL must be set when MESSAGE_BUS_BACKEND=rabbitmq")

        try:
            pika = import_module("pika")
        except Exception as exc:
            raise RuntimeError(
                "RabbitMQ backend requires pika. Install with `uv add pika`."
            ) from exc

        params = pika.URLParameters(url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)

        self._pika = pika
        self._params = params
        self._exchange = exchange
        self._conn = connection
        self._channel = channel

    def _ensure_connection(self) -> None:
        if getattr(self._conn, "is_closed", False):
            self._conn = self._pika.BlockingConnection(self._params)
            self._channel = self._conn.channel()
            self._channel.exchange_declare(
                exchange=self._exchange,
                exchange_type="topic",
                durable=True,
            )

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Publish a lifecycle event to RabbitMQ.

        Args:
            event_type: Event type identifier.
            payload: Event payload.

        Side Effects:
            Ensures an open AMQP connection and publishes to the topic exchange.
        """
        self._ensure_connection()
        event = _build_event(event_type, payload)
        self._channel.basic_publish(
            exchange=self._exchange,
            routing_key=event_type,
            body=json.dumps(event, default=str).encode("utf-8"),
            properties=self._pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )

    def close(self) -> None:
        """Close the RabbitMQ connection when it is open.

        Side Effects:
            Closes the underlying AMQP connection.
        """
        if self._conn and not self._conn.is_closed:
            self._conn.close()


class UcAuditTableMessageBus:
    """Persist lifecycle events to a UC-governed Delta audit table.

    Args:
        warehouse_id: SQL warehouse id used for statement execution.
        catalog: UC catalog name containing the audit table.
        schema: UC schema name containing the audit table.
        table: UC table name for audit events.
        fail_open: When true, drop failed writes and continue processing.
        workspace_client: Optional workspace client override.

    Raises:
        ValueError: If required UC or warehouse configuration is missing.
    """

    def __init__(
        self,
        warehouse_id: str,
        catalog: str,
        schema: str,
        table: str,
        fail_open: bool,
        workspace_client: WorkspaceClient | None = None,
    ) -> None:
        if not warehouse_id.strip():
            raise ValueError("UC_AUDIT_WAREHOUSE_ID must be set when MESSAGE_BUS_BACKEND=uc_table")
        if not catalog.strip() or not schema.strip() or not table.strip():
            raise ValueError(
                "UC_AUDIT_CATALOG, UC_AUDIT_SCHEMA, and UC_AUDIT_TABLE must all be set "
                "when MESSAGE_BUS_BACKEND=uc_table"
            )

        self._warehouse_id = warehouse_id
        self._catalog = _validate_identifier(catalog, "UC_AUDIT_CATALOG")
        self._schema = _validate_identifier(schema, "UC_AUDIT_SCHEMA")
        self._table = _validate_identifier(table, "UC_AUDIT_TABLE")
        self._fail_open = fail_open
        self._workspace_client = workspace_client or WorkspaceClient()
        self._ensure_table()

    @property
    def _table_fqn(self) -> str:
        return f"{self._catalog}.{self._schema}.{self._table}"

    def _execute(self, statement: str, parameters: list[StatementParameterListItem]) -> None:
        """Execute a parameterized SQL statement in the UC audit context.

        Args:
            statement: SQL statement text.
            parameters: SQL statement parameters.

        Side Effects:
            Executes a statement through the Databricks SQL statement API.
        """
        self._workspace_client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self._warehouse_id,
            parameters=parameters,
            wait_timeout="10s",
            catalog=self._catalog,
            schema=self._schema,
        )

    def _ensure_table(self) -> None:
        """Create audit schema/table if they do not already exist.

        Side Effects:
            Issues DDL statements for schema and table creation.
        """
        self._workspace_client.statement_execution.execute_statement(
            statement=f"CREATE SCHEMA IF NOT EXISTS {self._catalog}.{self._schema}",
            warehouse_id=self._warehouse_id,
            wait_timeout="10s",
        )
        self._workspace_client.statement_execution.execute_statement(
            statement=(
                f"CREATE TABLE IF NOT EXISTS {self._table_fqn} ("
                "event_date DATE, "
                "event_id STRING, "
                "event_type STRING, "
                "event_ts TIMESTAMP, "
                "event_payload STRING"
                ") USING DELTA PARTITIONED BY (event_date)"
            ),
            warehouse_id=self._warehouse_id,
            wait_timeout="10s",
        )

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Persist a lifecycle event to the UC audit table.

        Args:
            event_type: Event type identifier.
            payload: Event payload.

        Raises:
            Exception: Re-raises write failures when fail-open is disabled.

        Side Effects:
            Inserts an event row into the configured UC Delta table.

        Notes:
            When fail-open is enabled, write errors are logged and dropped.
        """
        event = _build_event(event_type, payload)
        try:
            self._execute(
                statement=(
                    f"INSERT INTO {self._table_fqn} "
                    "(event_date, event_id, event_type, event_ts, event_payload) "
                    "VALUES (CAST(:event_date AS DATE), :event_id, :event_type, "
                    "CAST(:event_ts AS TIMESTAMP), :event_payload)"
                ),
                parameters=[
                    StatementParameterListItem(
                        name="event_date", type="STRING", value=event["ts"][:10]
                    ),
                    StatementParameterListItem(
                        name="event_id", type="STRING", value=str(event["event_id"])
                    ),
                    StatementParameterListItem(
                        name="event_type", type="STRING", value=str(event["event_type"])
                    ),
                    StatementParameterListItem(
                        name="event_ts", type="STRING", value=str(event["ts"])
                    ),
                    StatementParameterListItem(
                        name="event_payload",
                        type="STRING",
                        value=json.dumps(event.get("payload", {}), default=str),
                    ),
                ],
            )
        except Exception:
            if self._fail_open:
                logger.exception(
                    "UC audit table write failed; dropping event due to fail-open policy",
                    extra={"event_type": event_type},
                )
                return
            raise


def _build_event(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    """Create a normalized event envelope for all bus backends.

    Args:
        event_type: Event type identifier.
        payload: Event-specific payload.

    Returns:
        Event envelope with id, type, timestamp, and payload.
    """
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


def _validate_identifier(value: str, env_name: str) -> str:
    """Validate SQL identifier fragments for safe DDL/DML composition.

    Args:
        value: Candidate identifier value.
        env_name: Environment variable name used in error messages.

    Returns:
        The validated identifier string.

    Raises:
        ValueError: If identifier violates allowed pattern.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"{env_name} has invalid identifier: {value!r}")
    return value


def default_message_bus(settings: AppSettings | None = None) -> MessageBus:
    """Create the configured message bus implementation for runtime use.

    Args:
        settings: Optional preloaded app settings.

    Returns:
        A message bus implementation selected from runtime configuration.

    Notes:
        When fail-open is enabled and backend initialization fails, the function
        falls back to structured logging.
    """
    cfg = settings or get_settings()
    backend = cfg.message_bus_backend.strip().lower()

    if backend == "noop":
        return NoOpMessageBus()
    if backend == "structured_logging":
        return _maybe_wrap_async(StructuredLoggingMessageBus(), cfg)
    if backend == "kafka":
        try:
            bus = KafkaMessageBus(
                bootstrap_servers=cfg.message_bus_kafka_bootstrap_servers,
                topic=cfg.message_bus_topic,
                client_id=cfg.message_bus_kafka_client_id,
            )
            return _maybe_wrap_async(bus, cfg)
        except Exception:
            if cfg.message_bus_fail_open:
                logger.exception(
                    "Kafka message bus initialization failed; falling back to structured logging"
                )
                return _maybe_wrap_async(StructuredLoggingMessageBus(), cfg)
            raise
    if backend == "rabbitmq":
        try:
            bus = RabbitMQMessageBus(
                url=cfg.message_bus_rabbitmq_url,
                exchange=cfg.message_bus_topic,
            )
            return _maybe_wrap_async(bus, cfg)
        except Exception:
            if cfg.message_bus_fail_open:
                logger.exception(
                    "RabbitMQ message bus initialization failed; falling back to structured logging"
                )
                return _maybe_wrap_async(StructuredLoggingMessageBus(), cfg)
            raise
    if backend == "uc_table":
        try:
            bus = UcAuditTableMessageBus(
                warehouse_id=cfg.message_bus_uc_warehouse_id,
                catalog=cfg.message_bus_uc_catalog,
                schema=cfg.message_bus_uc_schema,
                table=cfg.message_bus_uc_table,
                fail_open=cfg.message_bus_fail_open,
            )
            return _maybe_wrap_async(bus, cfg)
        except Exception:
            if cfg.message_bus_fail_open:
                logger.exception(
                    "UC table message bus initialization failed; falling back to structured logging"
                )
                return _maybe_wrap_async(StructuredLoggingMessageBus(), cfg)
            raise

    logger.warning(
        "Unknown MESSAGE_BUS_BACKEND=%r; defaulting to structured logging", cfg.message_bus_backend
    )
    return _maybe_wrap_async(StructuredLoggingMessageBus(), cfg)


def _maybe_wrap_async(bus: MessageBus, settings: AppSettings) -> MessageBus:
    """Wrap a bus with async publishing when MESSAGE_BUS_ASYNC is enabled."""
    if not settings.message_bus_async:
        return bus
    if isinstance(bus, NoOpMessageBus):
        return bus
    return AsyncMessageBus(
        inner=bus,
        queue_size=settings.message_bus_async_queue_size,
        fail_open=settings.message_bus_fail_open,
        drain_timeout_seconds=settings.message_bus_async_drain_timeout_seconds,
    )
