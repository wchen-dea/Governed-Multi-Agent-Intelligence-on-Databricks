import asyncio

from aiserver.contracts.public_api import ChatRequest
from aiserver.infrastructure.runtime.mlflow import MlflowAgentRuntime


def _request() -> ChatRequest:
    return ChatRequest(
        messages=[{"role": "user", "content": "Hello"}],
        conversation_id="conversation-1",
        persona="store-manager",
    )


def test_public_stream_exposes_only_text_and_governance_metadata():
    async def stream_handler(_request):
        yield {
            "type": "response.output_text.delta",
            "delta": "Hello",
        }
        yield {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "content": [{"text": "Hello"}],
            },
        }
        yield {
            "type": "response.completed",
            "response": {
                "instructions": "internal orchestrator prompt",
                "tools": [{"name": "query_internal", "parameters": {}}],
            },
        }
        yield {
            "type": "response.governance",
            "response_envelope": {
                "status": "succeeded",
                "openai_run": {"selected_tool_names": ["query_sales"]},
            },
        }

    async def invoke_handler(_request):
        return {}

    runtime = MlflowAgentRuntime(invoke_handler, stream_handler)

    async def collect():
        return [event async for event in runtime.stream(_request())]

    assert asyncio.run(collect()) == [
        {"type": "text_delta", "delta": "Hello"},
        {
            "type": "metadata",
            "metadata": {
                "status": "succeeded",
                "openai_run": {"selected_tool_names": ["query_sales"]},
            },
        },
        {"type": "completed"},
    ]
