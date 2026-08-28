"""Normalize agent streaming events for API delivery."""

from collections.abc import AsyncGenerator, AsyncIterator

from agents.result import StreamEvent
from mlflow.types.responses import ResponsesAgentStreamEvent


async def process_agent_stream_events(
    async_stream: AsyncIterator[StreamEvent],
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    """Normalize streamed item identifiers for downstream consumers."""
    item_counter = 0
    curr_item_id = f"item_{item_counter}"
    async for event in async_stream:
        if event.type == "raw_response_event":
            event_data = event.data.model_dump()
            if event_data["type"] == "response.output_item.added":
                item_counter += 1
                curr_item_id = f"item_{item_counter}"
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item") is not None and event_data["item"].get("id") is not None:
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item_id") is not None:
                event_data["item_id"] = curr_item_id
            yield event_data
        elif event.type == "run_item_stream_event" and event.item.type == "tool_call_output_item":
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=event.item.to_input_item(),
            )