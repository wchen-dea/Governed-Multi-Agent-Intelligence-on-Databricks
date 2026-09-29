"""Normalize request payloads and extract MCP-aware errors."""

from collections.abc import Iterable
from typing import Any

from agents.items import TResponseInputItem
from openai.types.responses.easy_input_message_param import EasyInputMessageParam

from aiserver.application.exceptions import GovernedExecutionError


def to_messages(input_items: Iterable[Any]) -> list[TResponseInputItem]:
    """Normalize MLflow response items to typed Responses input messages.

    Args:
        input_items: MLflow input items from a Responses request.

    Returns:
        List of typed Responses input items.
    """
    messages: list[TResponseInputItem] = []
    for item in input_items:
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if not isinstance(data, dict):
            continue

        role = data.get("role")
        if not role:
            continue

        content = data.get("content", "")
        if isinstance(content, list):
            texts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            ]
            content = " ".join(filter(None, texts))

        messages.append(EasyInputMessageParam(role=str(role), content=str(content)))

    return messages


def extract_mcp_errors(exc: Exception) -> list[GovernedExecutionError]:
    """Extract governed execution errors from an exception or exception group.

    Args:
        exc: Raised exception captured from handler execution.

    Returns:
        List of governed execution errors found within the exception.
    """
    if isinstance(exc, GovernedExecutionError):
        return [exc]
    if isinstance(exc, BaseExceptionGroup):
        return [
            err for err in exc.exceptions if isinstance(err, GovernedExecutionError)
        ]
    return []
