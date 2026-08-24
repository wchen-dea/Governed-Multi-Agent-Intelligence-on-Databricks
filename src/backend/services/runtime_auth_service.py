"""Build request-scoped authorization state for hybrid app and OBO execution.

This module resolves request identity, applies policy gates, and wires each
subagent to either the shared app client or a user-scoped OBO client.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import mlflow
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.types.responses import ResponsesAgentRequest

from backend.domain.subagent_config import SubagentConfig
from backend.services.interfaces import (
    IdentityContextProvider,
    LakebaseToolsBuilder,
    McpServersBuilder,
    MessageBus,
    OboClientFactory,
    SessionIdProvider,
    SubagentToolsBuilder,
    TraceMetadataUpdater,
)
from backend.services.agent_handoff_service import build_delegation_tool
from backend.services.interfaces import AgentTaskBus
from backend.services.message_bus import NoOpMessageBus
from backend.services.orchestrator_service import (
    build_lakebase_delegation_executors,
    build_lakebase_tools,
    build_mcp_servers,
    build_subagent_tools,
)
from backend.services.policy_service import (
    PolicyDecision,
    PolicyContext,
    build_policy_context,
    filter_subagents_by_policy,
)
from backend.shared.runtime_utils import (
    RequestIdentityContext,
    build_request_identity_context,
    get_session_id,
)


def _update_trace_metadata(metadata: dict[str, str]) -> None:
    """Write authorization metadata to the active MLflow trace."""
    mlflow.update_current_trace(metadata=metadata)


@dataclass(frozen=True)
class RuntimeAuthContext:
    """Request-scoped authorization result used by the orchestrator.

    Attributes:
        subagent_tools: Tool callables that remain available after policy and
            runtime auth checks.
        mcp_servers: MCP server descriptors exposed for this request.
        unavailable_auth: Human-readable denial or unavailability reasons from
            policy and runtime auth checks.
        policy_allowed_subagents: Subagents that passed policy evaluation
            before tool and MCP wiring.
    """

    subagent_tools: list
    mcp_servers: list[McpServer]
    unavailable_auth: list[str]
    policy_allowed_subagents: list[SubagentConfig]


@dataclass(frozen=True)
class RuntimeAuthDependencies:
    """Injectable collaborators for building runtime authorization state.

    Attributes:
        identity_context_provider: Resolves app identity plus any forwarded
            user identity for the current request.
        session_id_provider: Extracts the trace session id from request
            metadata.
        trace_metadata_updater: Records authorization metadata on the active
            trace.
        obo_client_factory: Creates a Databricks OpenAI client bound to the
            forwarded user identity.
        subagent_tools_builder: Builds tool callables for the allowed
            subagents.
        mcp_servers_builder: Builds MCP server descriptors for the allowed
            subagents.
        policy_context_builder: Derives the policy input for the current
            request.
        subagent_policy_filter: Evaluates which subagents remain allowed after
            policy checks.
        message_bus: Publishes auth and policy lifecycle events for auditing
            and diagnostics.
    """

    identity_context_provider: IdentityContextProvider = build_request_identity_context
    session_id_provider: SessionIdProvider = get_session_id
    trace_metadata_updater: TraceMetadataUpdater = _update_trace_metadata
    obo_client_factory: OboClientFactory = AsyncDatabricksOpenAI
    subagent_tools_builder: SubagentToolsBuilder = build_subagent_tools
    mcp_servers_builder: McpServersBuilder = build_mcp_servers
    lakebase_tools_builder: LakebaseToolsBuilder = build_lakebase_tools
    policy_context_builder: Callable[
        [ResponsesAgentRequest, RequestIdentityContext], PolicyContext
    ] = build_policy_context
    subagent_policy_filter: Callable[
        [list[SubagentConfig], PolicyContext], tuple[list[SubagentConfig], list[PolicyDecision]]
    ] = filter_subagents_by_policy
    message_bus: MessageBus = NoOpMessageBus()
    delegation_task_bus: AgentTaskBus | None = None


def _build_trace_metadata(
    subagents: list[SubagentConfig],
    request: ResponsesAgentRequest,
    identity_ctx: RequestIdentityContext,
    deps: RuntimeAuthDependencies,
) -> dict[str, str]:
    """Build and emit trace metadata for authorization decisions.

    Args:
        subagents: Subagents considered for the request before final auth
            wiring.
        request: Responses API request payload.
        identity_ctx: Resolved request identity, including user-token
            availability.
        deps: Runtime collaborators for trace and lifecycle emission.

    Returns:
        Normalized metadata dictionary written to tracing and the message bus.

    Side Effects:
        Updates the current trace and publishes an auth metadata event.
    """
    metadata: dict[str, str] = {
        "auth.user_token_present": str(identity_ctx.has_user_identity).lower(),
        "auth.subagents_total": str(len(subagents)),
        "auth.subagents_obo": str(sum(1 for s in subagents if s.is_obo)),
        "auth.subagents_app": str(sum(1 for s in subagents if not s.is_obo)),
    }
    if session_id := deps.session_id_provider(request):
        metadata["mlflow.trace.session"] = session_id
    deps.trace_metadata_updater(metadata=metadata)
    deps.message_bus.publish("auth.trace.metadata.updated", dict(metadata))
    return metadata


def build_runtime_auth_context(
    request: ResponsesAgentRequest,
    subagents: list[SubagentConfig],
    app_client: AsyncDatabricksOpenAI,
    deps: RuntimeAuthDependencies | None = None,
) -> RuntimeAuthContext:
    """Build request-scoped authorization state for orchestrator execution.

    Args:
        request: Incoming Responses API request.
        subagents: Configured subagents available to the orchestrator.
        app_client: Databricks OpenAI client running as the app identity.
        deps: Optional dependency overrides, primarily used for tests and
            instrumentation.

    Returns:
        Authorization results containing allowed tools, MCP servers, and
        unavailability reasons for this request.

    Side Effects:
        Publishes auth and policy lifecycle events and updates trace metadata.

    Notes:
        The function first resolves identity and policy outcomes, then builds
        tool and MCP wiring with the correct identity. OBO clients are created
        only when a forwarded user identity is present.
    """
    dependencies = deps or RuntimeAuthDependencies()
    identity_ctx = dependencies.identity_context_provider()
    policy_ctx = dependencies.policy_context_builder(request, identity_ctx)

    allowed_subagents, policy_decisions = dependencies.subagent_policy_filter(subagents, policy_ctx)
    denied_by_policy = [d.reason for d in policy_decisions if not d.allowed]

    for decision in policy_decisions:
        dependencies.message_bus.publish(
            "policy.subagent.decision",
            {
                "result": "allow" if decision.allowed else "deny",
                "subagent": decision.subagent_name,
                "tool_name": decision.tool_name,
                "reason_code": decision.reason_code,
                "reason": decision.reason,
                "persona": policy_ctx.persona or "<missing>",
                "has_user_identity": policy_ctx.has_user_identity,
                "requested_tool": policy_ctx.requested_tool or "<unspecified>",
                "request_confidence": policy_ctx.request_confidence,
            },
        )

    dependencies.message_bus.publish(
        "auth.identity.resolved",
        {
            "has_user_identity": identity_ctx.has_user_identity,
            "subagents_total": len(subagents),
        },
    )
    _build_trace_metadata(subagents, request, identity_ctx, dependencies)

    # Only construct a user-scoped client when the request includes a
    # forwarded identity; OBO-only subagents remain unavailable otherwise.
    obo_client = (
        dependencies.obo_client_factory(workspace_client=identity_ctx.user_workspace_client)
        if identity_ctx.has_user_identity
        else None
    )

    subagent_tools = dependencies.subagent_tools_builder(allowed_subagents, app_client, obo_client)
    lakebase_tools = dependencies.lakebase_tools_builder(allowed_subagents, identity_ctx)
    if dependencies.delegation_task_bus is not None:
        delegation_tool = build_delegation_tool(
            task_bus=dependencies.delegation_task_bus,
            subagents=allowed_subagents,
            executors=build_lakebase_delegation_executors(allowed_subagents, identity_ctx),
            message_bus=dependencies.message_bus,
            correlation_id=dependencies.session_id_provider(request) or "request",
        )
        if delegation_tool is not None:
            subagent_tools.append(delegation_tool)
    mcp_servers, unavailable_auth = dependencies.mcp_servers_builder(allowed_subagents, identity_ctx)
    unavailable = denied_by_policy + unavailable_auth
    dependencies.message_bus.publish(
        "auth.context.built",
        {
            "subagent_tools": len(subagent_tools) + len(lakebase_tools),
            "mcp_servers": len(mcp_servers),
            "unavailable_auth": len(unavailable),
        },
    )
    return RuntimeAuthContext(
        subagent_tools=subagent_tools + lakebase_tools,
        mcp_servers=mcp_servers,
        unavailable_auth=unavailable,
        policy_allowed_subagents=allowed_subagents,
    )
