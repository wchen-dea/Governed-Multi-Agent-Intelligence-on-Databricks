"""Runtime settings for backend services."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class AppSettings:
    """Typed runtime settings loaded from environment."""

    orchestrator_model: str = "databricks-gpt-5-6-luna"
    openai_base_url: str = ""
    openai_timeout_seconds: float = 0.0
    log_level: str = "INFO"
    log_format: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    message_bus_backend: str = "structured_logging"
    message_bus_topic: str = "agent-lifecycle-events"
    message_bus_kafka_bootstrap_servers: str = ""
    message_bus_kafka_client_id: str = "multiagent-app"
    message_bus_rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    message_bus_fail_open: bool = True
    message_bus_uc_warehouse_id: str = ""
    message_bus_uc_catalog: str = ""
    message_bus_uc_schema: str = ""
    message_bus_uc_table: str = "agent_lifecycle_events"
    message_bus_async: bool = False
    message_bus_async_queue_size: int = 1000
    message_bus_async_drain_timeout_seconds: float = 2.0
    default_request_persona: str = "manager"
    max_input_chars: int = 12000
    max_response_chars: int = 20000


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load backend runtime settings from environment variables."""
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return AppSettings(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", "databricks-gpt-5-6-luna"),
        openai_base_url=os.getenv("DATABRICKS_OPENAI_BASE_URL", ""),
        openai_timeout_seconds=_env_float("DATABRICKS_OPENAI_TIMEOUT_SECONDS", 0.0),
        log_level=os.getenv("BACKEND_LOG_LEVEL", "INFO"),
        log_format=os.getenv(
            "BACKEND_LOG_FORMAT",
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
        ),
        log_date_format=os.getenv("BACKEND_LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"),
        message_bus_backend=os.getenv("MESSAGE_BUS_BACKEND", "structured_logging"),
        message_bus_topic=os.getenv("MESSAGE_BUS_TOPIC", "agent-lifecycle-events"),
        message_bus_kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
        message_bus_kafka_client_id=os.getenv("KAFKA_CLIENT_ID", "multiagent-app"),
        message_bus_rabbitmq_url=os.getenv(
            "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"
        ),
        message_bus_fail_open=os.getenv("MESSAGE_BUS_FAIL_OPEN", "true").lower()
        in {"1", "true", "yes", "on"},
        message_bus_uc_warehouse_id=os.getenv("UC_AUDIT_WAREHOUSE_ID", ""),
        message_bus_uc_catalog=os.getenv("UC_AUDIT_CATALOG", ""),
        message_bus_uc_schema=os.getenv("UC_AUDIT_SCHEMA", ""),
        message_bus_uc_table=os.getenv("UC_AUDIT_TABLE", "agent_lifecycle_events"),
        message_bus_async=os.getenv("MESSAGE_BUS_ASYNC", "false").lower()
        in {"1", "true", "yes", "on"},
        message_bus_async_queue_size=_env_int("MESSAGE_BUS_ASYNC_QUEUE_SIZE", 1000),
        message_bus_async_drain_timeout_seconds=_env_float(
            "MESSAGE_BUS_ASYNC_DRAIN_TIMEOUT_SECONDS", 2.0
        ),
        default_request_persona=os.getenv("DEFAULT_REQUEST_PERSONA", "manager"),
        max_input_chars=_env_int("MAX_INPUT_CHARS", 12000),
        max_response_chars=_env_int("MAX_RESPONSE_CHARS", 20000),
    )
