# Request Execution Flow: Class Diagram

These diagrams focus on request execution in `src/backend/api/handlers.py` using the staged-pipeline pattern.
They separate the invoke and stream pipeline views while showing the shared stages.

## Invoke Pipeline

```mermaid
classDiagram
direction LR

class ResponsesAgentRequest {
    +input: list
    +custom_inputs: dict?
}
class ResponsesAgentResponse {
    +output: list
}
class AsyncExitStack

class RequestStage {
    +request: ResponsesAgentRequest
    +runtime_auth: RuntimeAuthContext
    +messages: list
}

class ConnectedStage {
    +runtime_auth: RuntimeAuthContext
    +unavailable: list~str~
    +agent: Agent
}

class InvokeFinalizedStage {
    +output_items: list~dict~
    +unavailable: list~str~
}

class HandlerDependencies {
    +runtime_auth_builder(request, subagents, client)
    +mcp_connector(stack, mcp_servers)
    +orchestrator_factory(model, subagents, servers, tools, unavailable)
    +guardrails_evaluator(text, subagents)
    +message_bus: MessageBus
}

class InvokePipeline {
    +_prepare_request_stage(request) RequestStage
    +_connect_request_stage(stack, prepared) ConnectedStage
    +_execute_invoke_stage(connected, messages) RunnerResult
    +_finalize_invoke_stage(result, connected) InvokeFinalizedStage
}

class GuardrailHelpers {
    +_guardrail_scope_subagents(payloads, subagents)
    +_governed_source_suffix_with_fallback(payloads, subagents)
    +_append_source_to_output_items(items, suffix)
}

HandlerDependencies ..> InvokePipeline : drives
InvokePipeline ..> RequestStage : prepare
InvokePipeline ..> ConnectedStage : connect
InvokePipeline ..> InvokeFinalizedStage : finalize
InvokePipeline --> ResponsesAgentResponse : returns
InvokePipeline ..> GuardrailHelpers : evaluate + attribute
RequestStage --> ResponsesAgentRequest
InvokePipeline ..> AsyncExitStack : MCP lifecycle
```

## Stream Pipeline

```mermaid
classDiagram
direction LR

class ResponsesAgentRequest {
    +input: list
    +custom_inputs: dict?
}
class ResponsesAgentStreamEvent
class AsyncExitStack

class RequestStage {
    +request: ResponsesAgentRequest
    +runtime_auth: RuntimeAuthContext
    +messages: list
}

class ConnectedStage {
    +runtime_auth: RuntimeAuthContext
    +unavailable: list~str~
    +agent: Agent
}

class StreamExecutedStage {
    +event_count: int
    +buffered_events: list
    +streamed_text_parts: list~str~
    +used_subagents: list~SubagentConfig~
    +has_tool_activity: bool
}

class StreamFinalizedStage {
    +event_count: int
    +buffered_events: list
    +source_suffix: str
    +unavailable: list~str~
    +guardrail_blocked: bool
    +guardrail_reasons: tuple~str~
}

class HandlerDependencies {
    +runtime_auth_builder(request, subagents, client)
    +mcp_connector(stack, mcp_servers)
    +orchestrator_factory(model, subagents, servers, tools, unavailable)
    +guardrails_evaluator(text, subagents)
    +message_bus: MessageBus
}

class StreamPipeline {
    +_prepare_request_stage(request) RequestStage
    +_connect_request_stage(stack, prepared) ConnectedStage
    +_execute_stream_stage(connected, messages) StreamExecutedStage
    +_finalize_stream_stage(executed, connected) StreamFinalizedStage
}

class StreamHelpers {
    +_text_from_stream_event(event) str
    +_candidate_tool_names(data) list~str~
    +_resolve_subagent(candidate, subagents) SubagentConfig?
    +_governed_source_suffix(used_subagents) str
}

HandlerDependencies ..> StreamPipeline : drives
StreamPipeline ..> RequestStage : prepare
StreamPipeline ..> ConnectedStage : connect
StreamPipeline ..> StreamExecutedStage : execute
StreamPipeline ..> StreamFinalizedStage : finalize
StreamPipeline --> ResponsesAgentStreamEvent : yields
StreamPipeline ..> StreamHelpers : track + attribute
RequestStage --> ResponsesAgentRequest
StreamPipeline ..> AsyncExitStack : MCP lifecycle
```

## Notes

- Shared stages (`_prepare_request_stage`, `_connect_request_stage`) enforce a common pipeline contract for invoke and stream.
- Stream path buffers all events in one pass, tracks `used_subagents` and `has_tool_activity`, then applies guardrails post-execution.
- Guardrail block behavior diverges by mode:
  - invoke: raises `UserError` — caller sees authorization error
  - stream: emits `response.output_text.delta` with block message and terminates
- Source attribution (`_governed_source_suffix`) appends Genie space freshness SLA citations for governed subagents.
