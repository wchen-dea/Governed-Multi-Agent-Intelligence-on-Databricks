# Runtime Invocation and Stream Pipeline

These diagrams show the delivery-neutral staged pipeline in
`src/aiserver/application/execution/service.py`. The MLflow adapter in
`src/aiserver/api/invocations.py` only translates requests, results, and stream
events.

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

class PreparedExecution {
    +request: GovernedExecutionRequest
    +runtime_auth: RuntimeAuthContext
}

class ConnectedExecution {
    +prepared: PreparedExecution
    +runtime_auth: RuntimeAuthContext
    +unavailable: list~str~
    +agent: Agent
}

class FinalizedInvoke {
    +output_items: list~dict~
    +unavailable: list~str~
    +envelope: ResponseEnvelope
}

class GovernedAgentServiceDependencies {
    +runtime_auth_builder(request)
    +mcp_connector(stack, mcp_servers)
    +orchestrator_factory(model, subagents, servers, tools, unavailable)
    +response_guardrails_evaluator(text, subagents)
    +input_guardrails_evaluator(input, max_input_chars)
    +message_bus: MessageBus
    +memory: ConversationMemory
    +runner: AgentRunner
}
class RuntimeAuthContext {
    +subagent_tools: list
    +mcp_servers: list~McpServer~
    +unavailable_auth: list~str~
}
class RuntimeAuthDependencies {
    +subagent_tools_builder: SubagentToolsBuilder
}
class SubagentToolsBuilder {
    <<protocol>>
}
class ToolRegistry {
    +resolve(subagent) ToolAdapter?
}
class AppToolAdapter {
    +build(subagent, app_client, obo_client, deps) Callable
}

class GovernedAgentService {
    +invoke(request) GovernedExecutionResult
    +_prepare(request) PreparedExecution
    +_connect(stack, prepared) ConnectedExecution
    +_run_with_retry(connected, request) RunnerExecutionResult
    +_finalize_invoke(items, connected) FinalizedInvoke
}

class GuardrailHelpers {
    +_guardrail_scope_subagents(payloads, subagents)
    +_governed_source_suffix_with_fallback(payloads, subagents)
    +_append_source_to_output_items(items, suffix)
}

GovernedAgentServiceDependencies ..> GovernedAgentService : configures
GovernedAgentService ..> PreparedExecution : prepare
GovernedAgentService ..> ConnectedExecution : connect
GovernedAgentService ..> FinalizedInvoke : finalize
GovernedAgentService --> ResponsesAgentResponse : adapter translates result
GovernedAgentService ..> GuardrailHelpers : evaluate + attribute
PreparedExecution --> RuntimeAuthContext
RuntimeAuthDependencies ..> SubagentToolsBuilder
SubagentToolsBuilder ..> ToolRegistry : builder implementation resolves direct tools
ToolRegistry --> AppToolAdapter : direct app/endpoint adapter
GovernedAgentService ..> AsyncExitStack : MCP lifecycle
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

class PreparedExecution {
    +request: GovernedExecutionRequest
    +runtime_auth: RuntimeAuthContext
}

class ConnectedExecution {
    +prepared: PreparedExecution
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
    +envelope: ResponseEnvelope
}

class GovernedAgentServiceDependencies {
    +runtime_auth_builder(request)
    +mcp_connector(stack, mcp_servers)
    +orchestrator_factory(model, subagents, servers, tools, unavailable)
    +response_guardrails_evaluator(text, subagents)
    +input_guardrails_evaluator(input, max_input_chars)
    +message_bus: MessageBus
    +memory: ConversationMemory
    +runner: AgentRunner
}
class RuntimeAuthContext {
    +subagent_tools: list
    +mcp_servers: list~McpServer~
    +unavailable_auth: list~str~
}
class RuntimeAuthDependencies {
    +subagent_tools_builder: SubagentToolsBuilder
}
class SubagentToolsBuilder {
    <<protocol>>
}
class ToolRegistry {
    +resolve(subagent) ToolAdapter?
}
class AppToolAdapter {
    +build(subagent, app_client, obo_client, deps) Callable
}

class GovernedAgentService {
    +stream(request) AsyncIterator~ExecutionStreamEvent~
    +_prepare(request) PreparedExecution
    +_connect(stack, prepared) ConnectedExecution
    +_stream_with_retry(connected, request) StreamExecutedStage
    +_finalize_stream(executed, connected) StreamFinalizedStage
}

class StreamHelpers {
    +_text_from_stream_event(event) str
    +_candidate_tool_names(data) list~str~
    +_resolve_subagent(candidate, subagents) SubagentConfig?
    +_governed_source_suffix(used_subagents) str
}

GovernedAgentServiceDependencies ..> GovernedAgentService : configures
GovernedAgentService ..> PreparedExecution : prepare
GovernedAgentService ..> ConnectedExecution : connect
GovernedAgentService ..> StreamExecutedStage : execute
GovernedAgentService ..> StreamFinalizedStage : finalize
GovernedAgentService --> ResponsesAgentStreamEvent : adapter translates events
GovernedAgentService ..> StreamHelpers : track + attribute
PreparedExecution --> RuntimeAuthContext
RuntimeAuthDependencies ..> SubagentToolsBuilder
SubagentToolsBuilder ..> ToolRegistry : builder implementation resolves direct tools
ToolRegistry --> AppToolAdapter : direct app/endpoint adapter
GovernedAgentService ..> AsyncExitStack : MCP lifecycle
```

## Notes

- Shared stages (`_prepare`, `_connect`) enforce a common pipeline contract for invoke and stream.
- Stream path buffers all events in one pass, tracks `used_subagents` and `has_tool_activity`, then applies guardrails post-execution.
- Buffered events become user-visible answer text only after finalization; the UI renders `response.output_text.delta` and keeps other events as metadata.
- Guardrail block behavior diverges by mode:
  - invoke: raises `GovernedExecutionError`, translated to the delivery framework's user error
  - stream: emits `response.output_text.delta` with block message and terminates
- Source attribution (`_governed_source_suffix`) appends Genie space freshness SLA citations for governed subagents.
