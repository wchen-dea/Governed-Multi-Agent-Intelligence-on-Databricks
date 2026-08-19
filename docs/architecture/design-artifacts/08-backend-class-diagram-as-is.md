# Backend Class Diagrams

This class diagrams with several logic-isolated views.
Each view reflects current implementation naming and relationships in the backend.

## 1. Domain and Policy Model

```mermaid
classDiagram
direction LR

class SubagentConfig {
  +name: str
  +kind: SubagentKind
  +description: str
  +system_prompt: str?
  +endpoint: str?
  +space_id: str?
  +mcp_url: str?
  +project_id: str?
  +branch_id: str?
  +database: str?
  +pg_host: str?
  +pg_user: str?
  +endpoint_id: str?
  +auth_mode: SubagentAuthMode
  +data_classification: DataClassification
  +owner: str?
  +freshness_sla: str?
  +allowed_personas: tuple[str]
  +requires_evidence: bool
  +is_genie: bool
  +is_mcp: bool
  +is_lakebase: bool
  +is_obo: bool
  +tool_name: str
  +model_name: str
  +from_dict(value) SubagentConfig
}

class PolicyContext {
  +persona: str?
  +has_user_identity: bool
  +requested_tool: str?
  +request_confidence: float?
}

class PolicyDecision {
  +subagent_name: str
  +tool_name: str
  +allowed: bool
  +reason_code: str
  +reason: str
}

class GuardrailResult {
  +blocked: bool
  +reasons: tuple[str]
}

class RequestIdentityContext {
  +app_workspace_client: WorkspaceClient
  +user_workspace_client: WorkspaceClient?
  +forwarded_access_token: str?
  +has_user_identity: bool
}

class RuntimeAuthContext {
  +subagent_tools: list
  +mcp_servers: list[McpServer]
  +unavailable_auth: list[str]
  +policy_allowed_subagents: list[SubagentConfig]
}
RuntimeAuthContext --> SubagentConfig : policy_allowed_subagents

PolicyDecision --> SubagentConfig
PolicyContext --> RequestIdentityContext
PolicyDecision --> PolicyContext
GuardrailResult --> SubagentConfig : driven by used subagents
```

## 2. Dependency Composition and Ports

```mermaid
classDiagram
direction LR

class AppSettings {
  +orchestrator_model: str
  +message_bus_backend: str
  +message_bus_topic: str
  +message_bus_fail_open: bool
  +default_request_persona: str
}

class AppDependencyContainer {
  +orchestrator: OrchestratorDependencies
  +runtime_auth: RuntimeAuthDependencies
  +handlers: HandlerDependencies
}

class OrchestratorDependencies {
  +trace_metadata_updater
  +function_tool_wrapper
  +mcp_server_factory
  +message_bus
}

class RuntimeAuthDependencies {
  +identity_context_provider
  +session_id_provider
  +trace_metadata_updater
  +obo_client_factory
  +subagent_tools_builder
  +mcp_servers_builder
  +lakebase_tools_builder
  +policy_context_builder
  +subagent_policy_filter
  +message_bus
}

class HandlerDependencies {
  +runtime_auth_builder
  +mcp_connector
  +orchestrator_factory
  +guardrails_evaluator
  +message_bus
}

class RuntimeAuthContext {
  +subagent_tools: list
  +mcp_servers: list[McpServer]
  +unavailable_auth: list[str]
  +policy_allowed_subagents: list[SubagentConfig]
}

class GuardrailResult {
  +blocked: bool
  +reasons: tuple[str]
}

class MessageBus {
  <<protocol>>
  +publish(event_type, payload) None
}

class IdentityContextProvider {
  <<protocol>>
}
class SessionIdProvider {
  <<protocol>>
}
class TraceMetadataUpdater {
  <<protocol>>
}
class OboClientFactory {
  <<protocol>>
}
class SubagentToolsBuilder {
  <<protocol>>
}
class McpServersBuilder {
  <<protocol>>
}
class LakebaseToolsBuilder {
  <<protocol>>
}
class FunctionToolWrapper {
  <<protocol>>
}
class McpServerFactory {
  <<protocol>>
}

AppDependencyContainer o-- OrchestratorDependencies
AppDependencyContainer o-- RuntimeAuthDependencies
AppDependencyContainer o-- HandlerDependencies
AppDependencyContainer ..> AppSettings

OrchestratorDependencies ..> MessageBus
OrchestratorDependencies ..> FunctionToolWrapper
OrchestratorDependencies ..> McpServerFactory

RuntimeAuthDependencies ..> IdentityContextProvider
RuntimeAuthDependencies ..> SessionIdProvider
RuntimeAuthDependencies ..> TraceMetadataUpdater
RuntimeAuthDependencies ..> OboClientFactory
RuntimeAuthDependencies ..> SubagentToolsBuilder
RuntimeAuthDependencies ..> McpServersBuilder
RuntimeAuthDependencies ..> LakebaseToolsBuilder
RuntimeAuthDependencies ..> MessageBus

HandlerDependencies ..> RuntimeAuthContext
HandlerDependencies ..> GuardrailResult
HandlerDependencies ..> MessageBus
```

## 3. Handler Runtime Pipeline Stages

```mermaid
classDiagram
direction LR

class RequestStage {
  +request: ResponsesAgentRequest
  +runtime_auth
  +messages: list
}

class ConnectedStage {
  +runtime_auth
  +unavailable: list[str]
  +agent
}

class InvokeFinalizedStage {
  +output_items: list[dict]
  +unavailable: list[str]
}

class StreamExecutedStage {
  +event_count: int
  +buffered_events: list
  +streamed_text_parts: list[str]
  +used_subagents: list[SubagentConfig]
  +has_tool_activity: bool
}

class StreamFinalizedStage {
  +event_count: int
  +buffered_events: list
  +source_suffix: str
  +unavailable: list[str]
  +guardrail_blocked: bool
  +guardrail_reasons: tuple[str]
}

class ResponsesAgentRequest
class ResponsesAgentResponse
class ResponsesAgentStreamEvent
class RuntimeAuthContext {
  +subagent_tools: list
  +mcp_servers: list[McpServer]
  +unavailable_auth: list[str]
  +policy_allowed_subagents: list[SubagentConfig]
}

RequestStage --> ResponsesAgentRequest
RequestStage --> RuntimeAuthContext
ConnectedStage --> RuntimeAuthContext

ConnectedStage --> InvokeFinalizedStage : invoke finalize
ConnectedStage --> StreamExecutedStage : stream execute
StreamExecutedStage --> StreamFinalizedStage : stream finalize

InvokeFinalizedStage --> ResponsesAgentResponse
StreamFinalizedStage --> ResponsesAgentStreamEvent
```

## 4. Message Bus Strategy and Implementations

```mermaid
classDiagram
direction LR

class MessageBus {
  <<protocol>>
  +publish(event_type, payload) None
}

class NoOpMessageBus
class StructuredLoggingMessageBus
class AsyncMessageBus
class KafkaMessageBus
class RabbitMQMessageBus
class UcAuditTableMessageBus

class AppSettings {
  +message_bus_backend: str
  +message_bus_topic: str
  +message_bus_fail_open: bool
}

class MessageBusFactory {
  +default_message_bus(settings) MessageBus
}

MessageBus <|.. NoOpMessageBus
MessageBus <|.. StructuredLoggingMessageBus
MessageBus <|.. AsyncMessageBus
MessageBus <|.. KafkaMessageBus
MessageBus <|.. RabbitMQMessageBus
MessageBus <|.. UcAuditTableMessageBus

MessageBusFactory ..> AppSettings
MessageBusFactory ..> MessageBus : returns strategy
```

## Notes

- These are as-is structural views and mirror current implementation naming.
- The logic-relative: domain/policy, composition/ports, runtime stages, and message bus strategy.
- Use this artifact with `07-request-execution-flow-class-diagram.md` for invoke-vs-stream execution emphasis.
