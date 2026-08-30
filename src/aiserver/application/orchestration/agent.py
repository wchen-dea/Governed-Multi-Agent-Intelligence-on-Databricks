"""Provide orchestration helpers for tools, MCP connectivity, and agent assembly."""

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

from agents import Agent, function_tool
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer

from aiserver.application.adapters.tools import DefaultToolRegistry
from aiserver.application.ports.audit import (
    MessageBus,
    NoOpMessageBus,
    TraceMetadataUpdater,
    noop_trace_metadata,
)
from aiserver.application.ports.lakebase import LakebaseConnectionFactory
from aiserver.application.ports.tools import (
    FunctionToolWrapper,
    McpServerFactory,
    ToolAdapter,
)
from aiserver.application.runtime.identity import RequestIdentityContext, build_mcp_url
from aiserver.contracts.subagents import SubagentConfig

logger = logging.getLogger(__name__)

MCP_CONNECT_TIMEOUT_SECONDS = float(os.getenv("MCP_CONNECT_TIMEOUT_SECONDS", "10"))
# Pre-flight health-check timeout for the initial `list_tools()` probe used to decide
# whether a tool is reported "unavailable" to the model before any real turn runs. A
# slow/cold Genie space (sales/CDI) can exceed a tight timeout here even though it would
# succeed on a real query, producing a false "please enable this agent" response. Kept
# below MCP_SESSION_TIMEOUT_SECONDS since this only gates the pre-flight probe.
MCP_LIST_TOOLS_TIMEOUT_SECONDS = float(os.getenv("MCP_LIST_TOOLS_TIMEOUT_SECONDS", "30"))
MCP_HEALTH_TTL_SECONDS = float(os.getenv("MCP_HEALTH_TTL_SECONDS", "30"))
MCP_HEALTH_FAILURE_TTL_SECONDS = float(os.getenv("MCP_HEALTH_FAILURE_TTL_SECONDS", "10"))
# Read timeout for the MCP ClientSession (covers list_tools/tool calls made on every agent
# turn, not just the pre-flight health check). databricks_openai's McpServer defaults this
# to 20.0s if unset, which can be too tight for a slow/cold Genie space and surfaces as an
# uncaught McpError mid-turn instead of a graceful "unavailable" degradation.
MCP_SESSION_TIMEOUT_SECONDS = float(os.getenv("MCP_SESSION_TIMEOUT_SECONDS", "45"))
ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE = int(os.getenv("ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE", "128"))


@dataclass(frozen=True)
class _McpHealthCacheEntry:
    """Represent a cached MCP health decision with expiration metadata."""

    healthy: bool
    reason: str
    expires_at_monotonic: float


_MCP_HEALTH_CACHE: dict[str, _McpHealthCacheEntry] = {}
_MCP_HEALTH_CACHE_LOCK = Lock()
_ORCHESTRATOR_INSTRUCTIONS_CACHE: dict[tuple[tuple[Any, ...], ...], str] = {}
_ORCHESTRATOR_INSTRUCTIONS_CACHE_LOCK = Lock()


def _missing_lakebase_connection(*args: Any, **kwargs: Any) -> Any:
    """Reject Lakebase execution when bootstrap did not inject an adapter."""
    del args, kwargs
    raise RuntimeError("Lakebase connection adapter is not configured")


def _cache_key_for_server(server: McpServer) -> str:
    """Build a stable cache key for an MCP server descriptor."""
    name = str(getattr(server, "name", "MCP server"))
    url = str(getattr(server, "url", ""))
    return f"{name}|{url}"


def _get_cached_mcp_health(cache_key: str) -> _McpHealthCacheEntry | None:
    """Return a fresh cached health decision for a server when available."""
    now = monotonic()
    with _MCP_HEALTH_CACHE_LOCK:
        entry = _MCP_HEALTH_CACHE.get(cache_key)
        if entry is None:
            return None
        if entry.expires_at_monotonic <= now:
            _MCP_HEALTH_CACHE.pop(cache_key, None)
            return None
        return entry


def _set_cached_mcp_health(cache_key: str, healthy: bool, reason: str) -> None:
    """Store MCP health status with different TTL for success vs failure."""
    ttl = MCP_HEALTH_TTL_SECONDS if healthy else MCP_HEALTH_FAILURE_TTL_SECONDS
    expires_at = monotonic() + max(ttl, 0.0)
    with _MCP_HEALTH_CACHE_LOCK:
        _MCP_HEALTH_CACHE[cache_key] = _McpHealthCacheEntry(
            healthy=healthy,
            reason=reason,
            expires_at_monotonic=expires_at,
        )


def _subagent_instruction_signature(subagent: SubagentConfig) -> tuple[Any, ...]:
    """Return a stable, hashable signature used for instruction caching."""
    return (
        subagent.name,
        subagent.kind,
        subagent.auth_mode,
        subagent.data_classification,
        subagent.requires_evidence,
        subagent.description,
        subagent.system_prompt or "",
        subagent.tool_name,
        bool(subagent.is_genie),
        bool(subagent.is_mcp),
    )


def _build_base_orchestrator_instructions(subagents: list[SubagentConfig]) -> str:
    """Build static orchestrator instructions derived from subagent config."""
    tool_lines: list[str] = []
    for subagent in subagents:
        if subagent.is_genie or subagent.is_mcp:
            base = (
                "- MCP tools "
                f"({subagent.name}, auth={subagent.auth_mode}, "
                f"classification={subagent.data_classification}, evidence={subagent.requires_evidence}): "
                f"{subagent.description}"
            )
        elif subagent.is_lakebase:
            base = (
                f"- {subagent.tool_name} (auth={subagent.auth_mode}, "
                f"classification={subagent.data_classification}, evidence={subagent.requires_evidence}, "
                f"type=lakebase, database={subagent.database}): "
                f"{subagent.description}"
            )
        else:
            base = (
                f"- {subagent.tool_name} (auth={subagent.auth_mode}, "
                f"classification={subagent.data_classification}, evidence={subagent.requires_evidence}): "
                f"{subagent.description}"
            )

        if subagent.system_prompt:
            base += f"\n  System prompt: {subagent.system_prompt}"
        tool_lines.append(base)

    if tool_lines:
        return (
            "You are an orchestrator agent. Route the user's request to the most "
            "appropriate tool:\n"
            + "\n".join(tool_lines)
            + "\nFor requests about business, product, operational, scheduling, appointment, "
            "order, invoice, or support data, you MUST call the matching configured tool "
            "before answering. Do not claim that data is unavailable, inaccessible, missing, "
            "or that you cannot fulfill the request unless a tool call was attempted and "
            "returned an error or insufficient data."
            + "\nCall a given tool at most once per user request, except Lakebase may use "
            "one schema-discovery query followed by one data query. For appointment or order "
            "requests, if schema discovery is needed, use its result to issue the data query; "
            "do not stop after returning schema metadata. If a Lakebase tool result starts with "
            "LAKEBASE_QUERY_FAILED, do not retry it. Explain its category (authorization, "
            "authentication, connectivity, or execution) concisely."
            + "\nFor composite requests that require comparing results from two different "
            "tools (for example, cross-referencing the top appointment-count stores against "
            "the top sales-performing stores), call each relevant tool once in sequence to "
            "gather both result sets, then compute the requested comparison or intersection "
            "yourself. State clearly which items appear in both lists and which do not before "
            "giving the final answer."
            + "\nEach configured tool above lists its freshness SLA. When a composite request "
            "combines tools with different freshness SLAs (for example, a 15-minute sales feed "
            "compared against a 4-hour CDI feed or a 1-hour operational feed), do not present "
            "the combined result as one single as-of snapshot. State each source's freshness "
            "SLA next to its contribution (e.g., 'sales data as of the last 15 minutes; CDI "
            "data as of the last 4 hours') so the user understands the two figures may not "
            "reflect the same point in time."
            + "\nUse native tool calling only. Never write pseudo-tool syntax such as "
            "`to=query_*`, `code:`, or a tool-call JSON payload in assistant text."
            + "\nFor an approved cross-agent handoff, use the native delegate_to_agent tool. "
            "Never simulate delegation in assistant text."
            + "\nIf no configured tool covers the request, ask the user for clarification."
            + "\nFor any answer grounded in a tool marked evidence=true, include evidence in the final answer."
            + "\nUse either inline citations like `[1]` or end with a `Source:` line naming the tool and freshness SLA."
            + "\nDo not give a governed final answer without that evidence line."
        )

    return (
        "You are an assistant. No routing tools are configured. Answer based on your own knowledge."
    )


def _base_orchestrator_instructions(subagents: list[SubagentConfig]) -> str:
    """Return cached static orchestrator instructions for the subagent set."""
    key = tuple(_subagent_instruction_signature(subagent) for subagent in subagents)
    with _ORCHESTRATOR_INSTRUCTIONS_CACHE_LOCK:
        cached = _ORCHESTRATOR_INSTRUCTIONS_CACHE.get(key)
        if cached is not None:
            return cached

    built = _build_base_orchestrator_instructions(subagents)

    with _ORCHESTRATOR_INSTRUCTIONS_CACHE_LOCK:
        if len(_ORCHESTRATOR_INSTRUCTIONS_CACHE) >= max(ORCHESTRATOR_INSTRUCTIONS_CACHE_SIZE, 1):
            _ORCHESTRATOR_INSTRUCTIONS_CACHE.clear()
        _ORCHESTRATOR_INSTRUCTIONS_CACHE[key] = built
    return built


def _format_unavailable_reason(name: str, exc: Exception) -> str:
    """Format a concise unavailable reason with exception details.

    Args:
        name: Display name of the unavailable dependency.
        exc: Original exception raised during availability check.

    Returns:
        Human-readable unavailable reason including exception type and detail.

    Notes:
        Appends cause details when present and distinct from the top-level
        exception message.
    """
    detail = str(exc).strip() or "no error details"
    reason = f"{name} unavailable: {type(exc).__name__}: {detail}"
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        cause_detail = str(cause).strip()
        if cause_detail and cause_detail != detail:
            reason += f" (caused by {type(cause).__name__}: {cause_detail})"
    return reason


@dataclass(frozen=True)
class OrchestratorDependencies:
    """Group injectable dependencies used by orchestration helpers.

    Attributes:
        trace_metadata_updater: Callable that records tool/auth metadata in the
            active trace span.
        function_tool_wrapper: Wrapper used to expose async callables as OpenAI
            function tools.
        mcp_server_factory: Factory used to construct MCP server descriptors.
        message_bus: Event sink for tool and MCP lifecycle signals.
    """

    trace_metadata_updater: TraceMetadataUpdater = noop_trace_metadata
    lakebase_connection_factory: LakebaseConnectionFactory = _missing_lakebase_connection
    function_tool_wrapper: FunctionToolWrapper = function_tool
    mcp_server_factory: McpServerFactory = McpServer
    message_bus: MessageBus = NoOpMessageBus()


def _resolve_tool_adapter(
    subagent: SubagentConfig,
    tool_adapters: tuple[ToolAdapter, ...] | None,
    tool_registry: Any | None = None,
) -> ToolAdapter | None:
    """Choose the first adapter that can handle the subagent."""
    if tool_registry is not None:
        return tool_registry.resolve(subagent)
    registry = DefaultToolRegistry(tool_adapters)
    return registry.resolve(subagent)


def build_subagent_tools(
    subagents: list[SubagentConfig],
    app_client: AsyncDatabricksOpenAI,
    obo_client: AsyncDatabricksOpenAI | None,
    deps: OrchestratorDependencies | None = None,
    *,
    tool_adapters: tuple[ToolAdapter, ...] | None = None,
    tool_registry: Any | None = None,
) -> list:
    """Build function tools for non-MCP subagents via a registered adapter chain.

    The adapter boundary keeps subagent-specific execution logic separate from
    orchestration while preserving the existing app/OB0 request flow.
    """
    dependencies = deps or OrchestratorDependencies()
    tools = []

    for subagent in subagents:
        if subagent.is_genie or subagent.is_mcp or subagent.is_lakebase:
            continue
        adapter = _resolve_tool_adapter(subagent, tool_adapters, tool_registry=tool_registry)
        if adapter is None:
            continue
        tool = adapter.build(
            subagent=subagent,
            app_client=app_client,
            obo_client=obo_client,
            deps=dependencies,
        )
        tools.append(dependencies.function_tool_wrapper(tool))
    return tools


def _format_lakebase_results(columns: list[str], rows: list[tuple]) -> str:
    """Format psycopg2 query results into a readable table string."""
    if not rows:
        return "Query returned 0 rows."
    header = " | ".join(columns)
    lines = [header, "-" * len(header)]
    for row in rows[:200]:
        lines.append(" | ".join(str(v) for v in row))
    result = "\n".join(lines)
    if len(rows) > 200:
        result += f"\n... ({len(rows) - 200} more rows truncated)"
    return result


def _execute_lakebase_query(
    lakebase_connection_factory: LakebaseConnectionFactory,
    ws_client: Any,
    cfg: SubagentConfig,
    sql_query: str,
) -> str:
    """Execute a SQL query against Lakebase via psycopg2 with OAuth credentials."""
    try:
        conn = lakebase_connection_factory(
            ws_client,
            project_id=cfg.project_id,
            branch_id=cfg.branch_id,
            endpoint_id=cfg.endpoint_id,
            database=cfg.database,
            pg_host=cfg.pg_host,
            pg_user=cfg.pg_user,
        )
    except Exception as conn_exc:
        logger.error(
            "Lakebase psycopg2 connection failed: host=%s user=%s db=%s error=%s",
            cfg.pg_host,
            cfg.pg_user,
            cfg.database,
            str(conn_exc)[:300],
        )
        raise
    try:
        with conn.cursor() as cur:
            cur.execute(sql_query)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(200)
                return _format_lakebase_results(columns, rows)
            return f"Statement executed successfully. Rows affected: {cur.rowcount}"
    finally:
        conn.close()


def build_lakebase_delegation_executors(
    subagents: list[SubagentConfig],
    identity_ctx: RequestIdentityContext,
    deps: OrchestratorDependencies | None = None,
) -> dict[str, Any]:
    """Build app-auth executors for explicitly delegated Lakebase tasks."""
    dependencies = deps or OrchestratorDependencies()
    executors: dict[str, Any] = {}
    for subagent in subagents:
        if not subagent.is_lakebase or subagent.is_obo:
            continue

        async def execute(
            payload: dict[str, Any], cfg: SubagentConfig = subagent
        ) -> dict[str, Any]:
            sql_query = payload.get("sql_query")
            if not isinstance(sql_query, str) or not sql_query.strip():
                raise ValueError("delegation_requires_sql_query")
            result = await asyncio.to_thread(
                _execute_lakebase_query,
                dependencies.lakebase_connection_factory,
                identity_ctx.app_workspace_client,
                cfg,
                sql_query,
            )
            return {"result": result}

        executors[subagent.name] = execute
    return executors


def _lakebase_failure_result(exc: Exception) -> tuple[str, str]:
    """Convert Lakebase failures into safe tool output and an audit category."""
    detail = str(exc).lower()
    if "not authorized" in detail or "permission denied" in detail:
        category = "authorization"
        guidance = "The app identity is not authorized for the configured Lakebase database."
    elif "authentication" in detail or "jwt" in detail or "credentials" in detail:
        category = "authentication"
        guidance = "The Lakebase authentication credential was rejected."
    elif "connection to server" in detail or "timeout" in detail:
        category = "connectivity"
        guidance = "The Lakebase PostgreSQL endpoint could not be reached."
    else:
        category = "execution"
        guidance = "The Lakebase query could not be completed."
    return (
        "LAKEBASE_QUERY_FAILED "
        f"category={category}. {guidance} Do not claim the query returned no data.",
        category,
    )


def build_lakebase_tools(
    subagents: list[SubagentConfig],
    identity_ctx: RequestIdentityContext,
    deps: OrchestratorDependencies | None = None,
) -> list:
    """Build function tools for Lakebase subagents.

    Each Lakebase subagent becomes a function tool that accepts a SQL query
    and executes it against the configured Lakebase project and branch.
    """
    dependencies = deps or OrchestratorDependencies()
    tools = []

    for subagent in subagents:
        if not subagent.is_lakebase:
            continue

        if subagent.is_obo:
            if not identity_ctx.has_user_identity:
                continue
            workspace_client = identity_ctx.user_workspace_client
        else:
            workspace_client = identity_ctx.app_workspace_client

        def _make_lakebase_tool(cfg: SubagentConfig, ws_client):
            async def _call(sql_query: str, cfg_param: SubagentConfig = cfg) -> str:
                """Execute a PostgreSQL SQL query against the Lakebase database.

                Args:
                    sql_query: A valid PostgreSQL SQL statement (SELECT, etc.). Do NOT pass natural language — generate SQL first.
                """
                dependencies.message_bus.publish(
                    "tool.call.started",
                    {
                        "tool_name": cfg_param.tool_name,
                        "subagent": cfg_param.name,
                        "auth_mode": cfg_param.auth_mode,
                    },
                )
                try:
                    result = await asyncio.to_thread(
                        _execute_lakebase_query,
                        dependencies.lakebase_connection_factory,
                        ws_client,
                        cfg_param,
                        sql_query,
                    )
                    dependencies.message_bus.publish(
                        "tool.call.succeeded",
                        {
                            "tool_name": cfg_param.tool_name,
                            "subagent": cfg_param.name,
                            "auth_mode": cfg_param.auth_mode,
                        },
                    )
                    return result
                except Exception as exc:
                    result, failure_category = _lakebase_failure_result(exc)
                    dependencies.message_bus.publish(
                        "tool.call.failed",
                        {
                            "tool_name": cfg_param.tool_name,
                            "subagent": cfg_param.name,
                            "auth_mode": cfg_param.auth_mode,
                            "error_type": type(exc).__name__,
                            "failure_category": failure_category,
                        },
                    )
                    logger.warning(
                        "Lakebase query failed: category=%s type=%s",
                        failure_category,
                        type(exc).__name__,
                    )
                    return result

            _call.__name__ = cfg.tool_name
            _call.__doc__ = cfg.description
            return _call

        tools.append(
            dependencies.function_tool_wrapper(_make_lakebase_tool(subagent, workspace_client))
        )

    return tools


def build_mcp_servers(
    subagents: list[SubagentConfig],
    identity_ctx: RequestIdentityContext,
    deps: OrchestratorDependencies | None = None,
) -> tuple[list[McpServer], list[str]]:
    """Build MCP server descriptors for Genie and generic MCP subagents.

    Args:
        subagents: Loaded and validated subagent configuration entries.
        identity_ctx: Request-scoped app and user identity clients.
        deps: Optional dependency overrides for testing and instrumentation.

    Returns:
        A tuple of:
        - MCP server descriptors eligible for connection attempts.
        - Human-readable unavailable reasons detected during pre-check.

    Side Effects:
        Publishes MCP registration/unavailable lifecycle events.

    Notes:
        OBO-configured MCP subagents are excluded when user identity is not
        available in the request context.
    """
    dependencies = deps or OrchestratorDependencies()
    servers: list[McpServer] = []
    unavailable: list[str] = []

    for subagent in subagents:
        if not subagent.is_genie and not subagent.is_mcp:
            continue

        if subagent.is_obo:
            if not identity_ctx.has_user_identity:
                unavailable.append(
                    f"Genie MCP tools ({subagent.name}) requires user authorization (OBO)"
                )
                dependencies.message_bus.publish(
                    "mcp.server.unavailable",
                    {
                        "subagent": subagent.name,
                        "auth_mode": subagent.auth_mode,
                        "reason": "missing_obo_identity",
                    },
                )
                continue
            workspace_client = identity_ctx.user_workspace_client
        else:
            workspace_client = identity_ctx.app_workspace_client

        if subagent.is_genie:
            url = build_mcp_url(
                f"/api/2.0/mcp/genie/{subagent.space_id}",
                workspace_client=workspace_client,
            )
            server_name = f"Genie:{subagent.name}"
        else:
            url = build_mcp_url(subagent.mcp_url or "", workspace_client=workspace_client)
            server_name = f"MCP:{subagent.name}"

        servers.append(
            dependencies.mcp_server_factory(
                url=url,
                name=server_name,
                workspace_client=workspace_client,
                timeout=MCP_SESSION_TIMEOUT_SECONDS,
            )
        )
        dependencies.message_bus.publish(
            "mcp.server.registered",
            {
                "subagent": subagent.name,
                "auth_mode": subagent.auth_mode,
                "space_id": subagent.space_id,
                "mcp_url": subagent.mcp_url,
            },
        )

    return servers, unavailable


async def connect_healthy_mcp_servers(
    stack: AsyncExitStack, servers: list[McpServer]
) -> tuple[list[McpServer], list[str]]:
    """Connect MCP servers and retain only healthy endpoints.

    Args:
        stack: Async context stack used to own connected server lifecycles.
        servers: Candidate MCP servers created from subagent configuration.

    Returns:
        A tuple of:
        - Connected MCP servers that successfully responded to `list_tools`.
        - Unavailable reason strings for failed connection attempts.

    Side Effects:
        Enters async contexts on successful servers and logs failures.
    """
    healthy: list[McpServer] = []
    unavailable: list[str] = []
    enter_lock = asyncio.Lock()

    async def _check_and_connect(server: McpServer) -> tuple[McpServer | None, str | None]:
        name = str(getattr(server, "name", "MCP server"))
        cache_key = _cache_key_for_server(server)
        cached = _get_cached_mcp_health(cache_key)

        if cached is not None and not cached.healthy:
            return None, cached.reason

        try:
            # AsyncExitStack mutation is serialized; network health checks run in parallel.
            async with enter_lock:
                connected = await asyncio.wait_for(
                    stack.enter_async_context(server),
                    timeout=max(MCP_CONNECT_TIMEOUT_SECONDS, 0.1),
                )

            probe_required = cached is None or not cached.healthy
            if probe_required:
                await asyncio.wait_for(
                    connected.list_tools(),
                    timeout=max(MCP_LIST_TOOLS_TIMEOUT_SECONDS, 0.1),
                )

            _set_cached_mcp_health(cache_key, healthy=True, reason="")
            return connected, None
        except Exception as exc:
            reason = _format_unavailable_reason(name, exc)
            _set_cached_mcp_health(cache_key, healthy=False, reason=reason)
            logger.warning(
                "MCP server %r unavailable (%s); continuing without it.",
                name,
                reason,
                exc_info=True,
            )
            return None, reason

    results = await asyncio.gather(*(_check_and_connect(server) for server in servers))
    for connected, reason in results:
        if connected is not None:
            healthy.append(connected)
        elif reason:
            unavailable.append(reason)

    return healthy, unavailable


def create_orchestrator_agent(
    model: str,
    subagents: list[SubagentConfig],
    mcp_servers: list,
    tools: list,
    unavailable_tools: list[str] | None = None,
) -> Agent:
    """Create an orchestrator agent with runtime-aware routing instructions.

    Args:
        model: Model identifier for orchestrator responses.
        subagents: Active subagent configuration entries used to derive
            tool-routing instructions.
        mcp_servers: Connected MCP servers attached to the orchestrator.
        tools: Wrapped function tools attached to the orchestrator.
        unavailable_tools: Optional unavailable tool/runtime reasons injected
            into instructions.

    Returns:
        A configured `Agent` instance ready for request handling.

    Notes:
        Instruction text enforces evidence requirements for tools marked with
        `requires_evidence=true`.
    """
    instructions = _base_orchestrator_instructions(subagents)

    if unavailable_tools:
        names = "\n- " + "\n- ".join(sorted(set(unavailable_tools)))
        instructions += (
            "\n\nUnavailable tool/runtime details:"
            f"{names}\n"
            "If answering requires one of them, tell the user it isn't available "
            "instead of guessing."
        )

    return Agent(
        name="Orchestrator",
        instructions=instructions,
        model=model,
        mcp_servers=mcp_servers,
        tools=tools,
    )
