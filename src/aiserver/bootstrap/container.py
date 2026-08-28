"""Application dependency composition for backend API handlers."""

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from databricks_openai import AsyncDatabricksOpenAI
from mlflow.types.responses import ResponsesAgentRequest

from aiserver.application.auth.context import (
    RuntimeAuthContext,
    RuntimeAuthDependencies,
    build_runtime_auth_context,
)
from aiserver.application.guardrails.checks import (
    GuardrailResult,
    InputGuardrailResult,
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
from aiserver.application.ports.audit import MessageBus
from aiserver.application.ports.memory import ConversationMemory
from aiserver.application.ports.tasks import AgentTaskBus
from aiserver.config.settings import get_settings
from aiserver.contracts.subagents import SubagentConfig
from aiserver.infrastructure.databricks.lakebase import connect_lakebase
from aiserver.infrastructure.messaging.bus import default_message_bus
from aiserver.infrastructure.observability.tracing import update_trace_metadata
from aiserver.infrastructure.persistence.memory import default_conversation_memory
from aiserver.infrastructure.persistence.tasks import default_agent_task_bus


@dataclass(frozen=True)
class HandlerDependencies:
    """Injectable dependencies for invoke/stream orchestration handlers."""

    runtime_auth_builder: Callable[
        [ResponsesAgentRequest, list[SubagentConfig], AsyncDatabricksOpenAI],
        RuntimeAuthContext,
    ]
    mcp_connector: Callable[[AsyncExitStack, list], Awaitable[tuple[list, list[str]]]]
    orchestrator_factory: Callable[[str, list[SubagentConfig], list, list, list[str] | None], Any]
    guardrails_evaluator: Callable[[str, list[SubagentConfig]], GuardrailResult]
    input_guardrails_evaluator: Callable[..., InputGuardrailResult]
    message_bus: MessageBus
    memory: ConversationMemory


@dataclass(frozen=True)
class AppDependencyContainer:
    """Top-level composed dependencies for backend services and handlers."""

    orchestrator: OrchestratorDependencies
    runtime_auth: RuntimeAuthDependencies
    handlers: HandlerDependencies
    delegation_task_bus: AgentTaskBus


def build_dependency_container() -> AppDependencyContainer:
    """Build the default application dependency container.

    Centralizes service wiring and is the single place to override dependencies
    for custom environments or advanced integration testing.
    """
    settings = get_settings()
    bus = default_message_bus(settings)
    memory = default_conversation_memory(settings)
    orchestrator_deps = OrchestratorDependencies(
        message_bus=bus,
        trace_metadata_updater=update_trace_metadata,
        lakebase_connection_factory=connect_lakebase,
    )
    delegation_task_bus = default_agent_task_bus(settings)

    runtime_auth_deps = RuntimeAuthDependencies(
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

    handler_deps = HandlerDependencies(
        runtime_auth_builder=lambda request, subagents, app_client: build_runtime_auth_context(
            request,
            subagents,
            app_client,
            deps=runtime_auth_deps,
        ),
        mcp_connector=connect_healthy_mcp_servers,
        orchestrator_factory=create_orchestrator_agent,
        guardrails_evaluator=evaluate_response_guardrails,
        input_guardrails_evaluator=evaluate_input_guardrails,
        message_bus=bus,
        memory=memory,
    )

    return AppDependencyContainer(
        orchestrator=orchestrator_deps,
        runtime_auth=runtime_auth_deps,
        handlers=handler_deps,
        delegation_task_bus=delegation_task_bus,
    )


@lru_cache(maxsize=1)
def get_app_dependency_container() -> AppDependencyContainer:
    """Return the shared application dependency container for this process."""
    return build_dependency_container()


def get_handler_dependencies() -> HandlerDependencies:
    """Return handler dependencies from the default composition container."""
    return get_app_dependency_container().handlers
