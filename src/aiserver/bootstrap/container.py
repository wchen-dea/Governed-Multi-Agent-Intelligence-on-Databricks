"""Application dependency composition for backend API handlers."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from databricks_openai import AsyncDatabricksOpenAI

from aiserver.application.auth.context import RuntimeAuthDependencies, build_runtime_auth_context
from aiserver.application.execution.service import (
    GovernedAgentService,
    GovernedAgentServiceDependencies,
)
from aiserver.application.guardrails.checks import (
    evaluate_input_guardrails,
    evaluate_response_guardrails,
)
from aiserver.application.orchestration.agent import (
    OrchestratorDependencies,
    build_lakebase_delegation_executors,
    build_lakebase_tools,
    build_mcp_servers,
    build_subagent_tools,
    connect_healthy_mcp_servers,
    create_orchestrator_agent,
)
from aiserver.application.orchestration.model import select_model
from aiserver.application.orchestration.routing import build_route_plan
from aiserver.application.ports.audit import MessageBus
from aiserver.application.ports.tasks import AgentTaskBus
from aiserver.application.runtime.identity import (
    build_request_identity_context,
    get_session_id,
)
from aiserver.config.settings import get_settings
from aiserver.contracts.subagents import SUBAGENTS
from aiserver.infrastructure.databricks.lakebase import connect_lakebase
from aiserver.infrastructure.messaging.bus import default_message_bus
from aiserver.infrastructure.observability.tracing import update_trace_metadata
from aiserver.infrastructure.persistence.memory import default_conversation_memory
from aiserver.infrastructure.persistence.routing import default_route_affinity_store
from aiserver.infrastructure.persistence.tasks import default_agent_task_bus
from aiserver.infrastructure.runtime.openai_agents import OpenAIAgentsRunner
from aiserver.infrastructure.runtime.request_identity import get_forwarded_access_token


@dataclass(frozen=True)
class AppDependencyContainer:
    """Top-level composed dependencies for backend services and handlers."""

    orchestrator: OrchestratorDependencies
    runtime_auth: RuntimeAuthDependencies
    execution_service: GovernedAgentService
    app_client: AsyncDatabricksOpenAI
    message_bus: MessageBus
    delegation_task_bus: AgentTaskBus


def build_dependency_container() -> AppDependencyContainer:
    """Build the default application dependency container.

    Centralizes service wiring and is the single place to override dependencies
    for custom environments or advanced integration testing.
    """
    settings = get_settings()
    app_client = _build_openai_client()
    bus = default_message_bus(settings)
    memory = default_conversation_memory(settings)
    route_affinity_store = default_route_affinity_store(settings)
    orchestrator_deps = OrchestratorDependencies(
        message_bus=bus,
        trace_metadata_updater=update_trace_metadata,
        lakebase_connection_factory=connect_lakebase,
    )
    delegation_task_bus = default_agent_task_bus(settings)

    runtime_auth_deps = RuntimeAuthDependencies(
        identity_context_provider=lambda: build_request_identity_context(
            get_forwarded_access_token()
        ),
        session_id_provider=lambda request: get_session_id(
            request,
            get_forwarded_access_token(),
        ),
        subagent_tools_builder=lambda subagents, app_client, obo_client: build_subagent_tools(
            subagents,
            app_client,
            obo_client,
            deps=orchestrator_deps,
        ),
        mcp_servers_builder=lambda subagents, identity_ctx: build_mcp_servers(
            subagents,
            identity_ctx,
            deps=orchestrator_deps,
        ),
        lakebase_tools_builder=lambda subagents, identity_ctx: build_lakebase_tools(
            subagents,
            identity_ctx,
            deps=orchestrator_deps,
        ),
        lakebase_delegation_executors_builder=lambda subagents, identity_ctx: (
            build_lakebase_delegation_executors(
                subagents,
                identity_ctx,
                deps=orchestrator_deps,
            )
        ),
        message_bus=bus,
        delegation_task_bus=delegation_task_bus,
        trace_metadata_updater=update_trace_metadata,
    )

    execution_service = GovernedAgentService(
        GovernedAgentServiceDependencies(
            settings=settings,
            subagents=tuple(SUBAGENTS),
            runtime_auth_builder=lambda request: build_runtime_auth_context(
                request,
                SUBAGENTS,
                app_client,
                deps=runtime_auth_deps,
            ),
            mcp_connector=connect_healthy_mcp_servers,
            orchestrator_factory=create_orchestrator_agent,
            route_planner=lambda question, subagents, conversation_id: build_route_plan(
                question,
                subagents,
                conversation_id,
                affinity_store=route_affinity_store,
                affinity_ttl_seconds=settings.route_affinity_ttl_seconds,
            ),
            model_selector=select_model,
            input_guardrails_evaluator=evaluate_input_guardrails,
            response_guardrails_evaluator=evaluate_response_guardrails,
            message_bus=bus,
            memory=memory,
            runner=OpenAIAgentsRunner(),
        )
    )

    return AppDependencyContainer(
        orchestrator=orchestrator_deps,
        runtime_auth=runtime_auth_deps,
        execution_service=execution_service,
        app_client=app_client,
        message_bus=bus,
        delegation_task_bus=delegation_task_bus,
    )


@lru_cache(maxsize=1)
def get_app_dependency_container() -> AppDependencyContainer:
    """Return the shared application dependency container for this process."""
    return build_dependency_container()


def get_execution_service() -> GovernedAgentService:
    """Return the shared governed execution service for delivery adapters."""
    return get_app_dependency_container().execution_service


def _build_openai_client() -> AsyncDatabricksOpenAI:
    settings = get_settings()
    kwargs: dict[str, Any] = {}
    if settings.openai_base_url.strip():
        kwargs["base_url"] = settings.openai_base_url.strip()
    elif settings.openai_use_ai_gateway_native_api:
        kwargs["use_ai_gateway_native_api"] = True
    elif settings.openai_use_ai_gateway:
        kwargs["use_ai_gateway"] = True
    if settings.openai_timeout_seconds > 0:
        kwargs["timeout"] = settings.openai_timeout_seconds
    return AsyncDatabricksOpenAI(**kwargs)
