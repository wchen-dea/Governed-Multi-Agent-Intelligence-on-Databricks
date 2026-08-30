"""Provide concrete tool adapters used by orchestration."""

import asyncio
import logging
from collections.abc import Callable
from time import monotonic
from typing import Any, cast

from agents.exceptions import UserError
from databricks_openai import AsyncDatabricksOpenAI

from aiserver.application.ports.tools import ToolAdapter
from aiserver.contracts.responses import ToolExecutionResult
from aiserver.contracts.subagents import SubagentConfig

logger = logging.getLogger(__name__)


class McpToolAdapter:
    """Adapter for MCP-connected Genie and external tool subagents."""

    def supports(self, subagent: SubagentConfig) -> bool:
        return subagent.is_genie or subagent.is_mcp

    def build(
        self,
        *,
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
        deps: Any,
    ) -> Any:
        del app_client, obo_client, deps
        raise ValueError(f"MCP subagent {subagent.name!r} is not built as a function tool")


class LakebaseToolAdapter:
    """Adapter for Lakebase SQL execution tools."""

    def __init__(
        self,
        execute_query: Callable[[Any, Any, SubagentConfig, str], str] | None = None,
        failure_result: Callable[[Exception], tuple[str, str]] | None = None,
    ) -> None:
        self._execute_query = execute_query
        self._failure_result = failure_result

    def supports(self, subagent: SubagentConfig) -> bool:
        return subagent.is_lakebase

    def build(
        self,
        *,
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
        deps: Any,
    ) -> Any:
        del app_client, obo_client
        if self._execute_query is None or self._failure_result is None:
            raise RuntimeError("Lakebase tool adapter is missing execution collaborators")

        async def _call(sql_query: str, cfg_param: SubagentConfig = subagent) -> str:
            deps.message_bus.publish(
                "tool.call.started",
                {
                    "tool_name": cfg_param.tool_name,
                    "subagent": cfg_param.name,
                    "auth_mode": cfg_param.auth_mode,
                },
            )
            try:
                result = await asyncio.to_thread(
                    self._execute_query,
                    deps.lakebase_connection_factory,
                    None,
                    cfg_param,
                    sql_query,
                )
                deps.message_bus.publish(
                    "tool.call.succeeded",
                    {
                        "tool_name": cfg_param.tool_name,
                        "subagent": cfg_param.name,
                        "auth_mode": cfg_param.auth_mode,
                    },
                )
                return result
            except Exception as exc:
                result, failure_category = self._failure_result(exc)
                deps.message_bus.publish(
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

        _call.__name__ = subagent.tool_name
        _call.__doc__ = subagent.description
        return _call


class AppToolAdapter:
    """Adapter for app-backed and serving-endpoint tools configured in the registry."""

    def supports(self, subagent: SubagentConfig) -> bool:
        return not (subagent.is_genie or subagent.is_mcp or subagent.is_lakebase)

    def build(
        self,
        *,
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
        deps: Any,
    ) -> Any:
        async def _call(question: str, cfg_param: SubagentConfig = subagent) -> str:
            started_at = monotonic()
            deps.message_bus.publish(
                "tool.call.started",
                {
                    "tool_name": cfg_param.tool_name,
                    "subagent": cfg_param.name,
                    "auth_mode": cfg_param.auth_mode,
                },
            )
            selected_client = self._select_client(cfg_param, app_client, obo_client)
            deps.trace_metadata_updater(
                metadata={
                    "auth.tool_name": cfg_param.tool_name,
                    "auth.auth_mode_selected": cfg_param.auth_mode,
                    "auth.user_token_present": str(obo_client is not None).lower(),
                }
            )
            try:
                tool_input = [{"role": "user", "content": question}]
                if cfg_param.system_prompt:
                    tool_input = [
                        {"role": "system", "content": cfg_param.system_prompt},
                        *tool_input,
                    ]
                response = await selected_client.responses.create(
                    model=cfg_param.model_name,
                    input=cast(Any, tool_input),
                )
                execution = ToolExecutionResult(
                    tool_name=cfg_param.tool_name,
                    status="succeeded",
                    latency_ms=(monotonic() - started_at) * 1000,
                    auth_mode=cfg_param.auth_mode,
                )
                deps.message_bus.publish(
                    "tool.call.succeeded",
                    {
                        "tool_name": cfg_param.tool_name,
                        "subagent": cfg_param.name,
                        "auth_mode": cfg_param.auth_mode,
                        "status": execution.status,
                        "latency_ms": execution.latency_ms,
                        "attempt_count": execution.attempt_count,
                    },
                )
                return response.output_text
            except Exception as exc:
                execution = ToolExecutionResult(
                    tool_name=cfg_param.tool_name,
                    status="failed",
                    latency_ms=(monotonic() - started_at) * 1000,
                    auth_mode=cfg_param.auth_mode,
                    error_code=type(exc).__name__,
                )
                deps.message_bus.publish(
                    "tool.call.failed",
                    {
                        "tool_name": cfg_param.tool_name,
                        "subagent": cfg_param.name,
                        "auth_mode": cfg_param.auth_mode,
                        "error_type": type(exc).__name__,
                        "status": execution.status,
                        "latency_ms": execution.latency_ms,
                        "attempt_count": execution.attempt_count,
                        "error_code": execution.error_code,
                    },
                )
                raise

        _call.__name__ = subagent.tool_name
        _call.__doc__ = subagent.description
        return _call

    @staticmethod
    def _select_client(
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
    ) -> AsyncDatabricksOpenAI:
        if not subagent.is_obo:
            return app_client
        if obo_client is None:
            raise UserError(
                "This tool requires user authorization (OBO), but no forwarded "
                "access token was provided. Re-authenticate and try again."
            )
        return obo_client


class DelegationToolAdapter:
    """Adapter for delegation-capable app-auth tool routing."""

    def supports(self, subagent: SubagentConfig) -> bool:
        return bool(subagent.accepts_delegations_from)

    def build(
        self,
        *,
        subagent: SubagentConfig,
        app_client: AsyncDatabricksOpenAI,
        obo_client: AsyncDatabricksOpenAI | None,
        deps: Any,
    ) -> Any:
        del subagent, app_client, obo_client, deps
        raise ValueError("Delegation tools are built through the task-bus handoff flow")


class ToolRegistry:
    """Resolve the first adapter that matches a subagent, in a deterministic order."""

    def __init__(
        self,
        adapters: tuple[ToolAdapter, ...] | None = None,
        *,
        lakebase_execute_query: Callable[[Any, Any, SubagentConfig, str], str] | None = None,
        lakebase_failure_result: Callable[[Exception], tuple[str, str]] | None = None,
    ) -> None:
        if adapters is not None:
            self._adapters = adapters
        else:
            self._adapters = (
                McpToolAdapter(),
                LakebaseToolAdapter(lakebase_execute_query, lakebase_failure_result),
                AppToolAdapter(),
                DelegationToolAdapter(),
            )

    def register(self, adapter: ToolAdapter) -> "ToolRegistry":
        self._adapters = (*self._adapters, adapter)
        return self

    def resolve(self, subagent: SubagentConfig) -> ToolAdapter | None:
        for adapter in self._adapters:
            if adapter.supports(subagent):
                return adapter
        return None


class DefaultToolRegistry(ToolRegistry):
    """Default runtime registry for subagent tool adapters."""