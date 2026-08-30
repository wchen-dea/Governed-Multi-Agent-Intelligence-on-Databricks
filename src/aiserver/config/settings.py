"""Runtime settings for backend services."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Typed runtime settings loaded from environment."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore", populate_by_name=True)

    orchestrator_model: str = "databricks-gpt-5-6-luna"
    model_routing_enabled: bool = True
    model_routing_default_model: str = Field(
        "databricks-gpt-5-6-luna",
        validation_alias=AliasChoices("MODEL_ROUTING_DEFAULT_MODEL", "ORCHESTRATOR_MODEL"),
    )
    model_routing_reasoning_model: str = "databricks-claude-sonnet-5"
    model_routing_quality_model: str = "databricks-claude-sonnet-5"
    openai_base_url: str = Field("", validation_alias="DATABRICKS_OPENAI_BASE_URL")
    openai_timeout_seconds: float = Field(
        0.0, ge=0.0, validation_alias="DATABRICKS_OPENAI_TIMEOUT_SECONDS"
    )
    log_level: str = Field("INFO", validation_alias="BACKEND_LOG_LEVEL")
    log_format: str = Field(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        validation_alias="BACKEND_LOG_FORMAT",
    )
    log_date_format: str = Field("%Y-%m-%d %H:%M:%S", validation_alias="BACKEND_LOG_DATE_FORMAT")
    message_bus_backend: str = "structured_logging"
    message_bus_topic: str = "agent-lifecycle-events"
    message_bus_kafka_bootstrap_servers: str = Field(
        "", validation_alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    message_bus_kafka_client_id: str = Field(
        "multiagent-app", validation_alias="KAFKA_CLIENT_ID"
    )
    message_bus_rabbitmq_url: str = Field(
        "amqp://guest:guest@localhost:5672/", validation_alias="RABBITMQ_URL"
    )
    message_bus_fail_open: bool = True
    message_bus_uc_warehouse_id: str = Field("", validation_alias="UC_AUDIT_WAREHOUSE_ID")
    message_bus_uc_catalog: str = Field("", validation_alias="UC_AUDIT_CATALOG")
    message_bus_uc_schema: str = Field("", validation_alias="UC_AUDIT_SCHEMA")
    message_bus_uc_table: str = Field("agent_lifecycle_events", validation_alias="UC_AUDIT_TABLE")
    message_bus_async: bool = False
    message_bus_async_queue_size: int = Field(1000, ge=1)
    message_bus_async_drain_timeout_seconds: float = Field(2.0, ge=0.0)
    default_request_persona: str = "store-manager"
    max_input_chars: int = Field(12000, ge=1)
    max_response_chars: int = Field(20000, ge=1)
    agent_task_backend: str = "memory"
    agent_task_warehouse_id: str = ""
    agent_task_catalog: str = ""
    agent_task_schema: str = ""
    agent_task_table: str = "agent_delegation_tasks"
    agent_task_event_table: str = "agent_delegation_events"
    agent_task_worker_enabled: bool = False
    agent_task_worker_poll_seconds: float = Field(1.0, gt=0.0)
    memory_backend: str = "disabled"
    memory_project_id: str = ""
    memory_branch_id: str = ""
    memory_endpoint_id: str = ""
    memory_database: str = ""
    memory_pg_host: str = ""
    memory_pg_user: str = ""
    memory_conversation_table: str = "agent_conversations"
    memory_preference_table: str = "agent_preferences"
    memory_max_turns: int = Field(20, ge=0)
    memory_fail_open: bool = True
    approval_backend: str = "memory"
    approval_warehouse_id: str = ""
    approval_catalog: str = ""
    approval_schema: str = ""
    approval_table: str = "agent_approval_decisions"
    approval_fail_open: bool = False
    approval_delegation_enabled: bool = True
    approval_delegation_source_agent: str = "approval-api"
    approval_delegation_target_agent: str = "store-intervention-agent"
    approval_delegation_intent: str = "store_intervention_planning"
    mcp_connect_timeout_seconds: float = Field(10.0, ge=0.0)
    mcp_list_tools_timeout_seconds: float = Field(30.0, ge=0.0)
    mcp_health_ttl_seconds: float = Field(30.0, ge=0.0)
    mcp_health_failure_ttl_seconds: float = Field(10.0, ge=0.0)
    mcp_session_timeout_seconds: float = Field(45.0, gt=0.0)
    orchestrator_instructions_cache_size: int = Field(128, ge=1)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load backend runtime settings from environment variables."""
    return AppSettings()
