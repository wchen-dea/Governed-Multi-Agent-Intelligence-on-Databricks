# Backend Class Diagrams

Multi-view UML class diagrams reflecting current implementation naming and relationships.

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
    +allowed_personas: tuple~str~
    +requires_evidence: bool
    +is_genie: bool
    +is_mcp: bool
    +is_lakebase: bool
    +is_obo: bool
    +tool_name: str
    +model_name: str
    +from_dict(value) SubagentConfig
}

class SubagentKind {
    <<enumeration>>
    genie
    serving_endpoint
    app
    mcp
    lakebase
}

class SubagentAuthMode {
    <<enumeration>>
    app
    obo
}

class DataClassification {
    <<enumeration>>
    public
    internal
    confidential
    restricted
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
    +reasons: tuple~str~
}

class RequestIdentityContext {
    +app_workspace_client: WorkspaceClient
    +user_workspace_client: WorkspaceClient?
    +forwarded_access_token: str?
    +has_user_identity: bool
}

class RuntimeAuthContext {
    +subagent_tools: list
    +mcp_servers: list~McpServer~
    +unavailable_auth: list~str~
    +policy_allowed_subagents: list~SubagentConfig~
}

SubagentConfig --> SubagentKind
SubagentConfig --> SubagentAuthMode
SubagentConfig --> DataClassification
RuntimeAuthContext --> SubagentConfig : policy_allowed_subagents
PolicyDecision --> SubagentConfig
PolicyDecision --> PolicyContext
GuardrailResult --> SubagentConfig : driven by used subagents
```

## 2. Dependency Composition and Ports

```mermaid
classDiagram
direction LR

class AppSettings {
    +orchestrator_model: str
    +model_routing_enabled: bool
    +model_routing_default_model: str
    +model_routing_reasoning_model: str
    +model_routing_quality_model: str
    +openai_base_url: str
    +openai_timeout_seconds: float
    +message_bus_backend: str
    +message_bus_topic: str
    +message_bus_fail_open: bool
    +default_request_persona: str
    +message_bus_uc_warehouse_id: str
    +message_bus_uc_catalog: str
    +message_bus_uc_schema: str
    +message_bus_uc_table: str
}

class AppDependencyContainer {
    +orchestrator: OrchestratorDependencies
    +runtime_auth: RuntimeAuthDependencies
    +handlers: HandlerDependencies
    +delegation_task_bus: AgentTaskBus
}

class OrchestratorDependencies {
    +trace_metadata_updater: TraceMetadataUpdater
    +lakebase_connection_factory: LakebaseConnectionFactory
    +function_tool_wrapper: FunctionToolWrapper
    +mcp_server_factory: McpServerFactory
    +message_bus: MessageBus
}

class RuntimeAuthDependencies {
    +identity_context_provider: IdentityContextProvider
    +session_id_provider: SessionIdProvider
    +trace_metadata_updater: TraceMetadataUpdater
    +obo_client_factory: OboClientFactory
    +subagent_tools_builder: SubagentToolsBuilder
    +mcp_servers_builder: McpServersBuilder
    +lakebase_tools_builder: LakebaseToolsBuilder
    +lakebase_delegation_executors_builder: LakebaseDelegationExecutorsBuilder
    +policy_context_builder
    +subagent_policy_filter
    +message_bus: MessageBus
    +delegation_task_bus: AgentTaskBus?
}

class HandlerDependencies {
    +runtime_auth_builder
    +mcp_connector
    +orchestrator_factory
    +guardrails_evaluator
    +input_guardrails_evaluator
    +message_bus: MessageBus
    +memory: ConversationMemory
}

class MessageBus {
    <<protocol>>
    +publish(event_type, payload) None
}

class IdentityContextProvider {
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
class ToolAdapter {
    <<protocol>>
    +supports(subagent) bool
    +build(subagent, app_client, obo_client, deps) Any
}
class McpToolAdapter {
    +supports(subagent) bool
    +build(subagent, app_client, obo_client, deps) Any
}
class LakebaseToolAdapter {
    -_execute_query
    -_failure_result
    +supports(subagent) bool
    +build(subagent, app_client, obo_client, deps) Any
}
class AppToolAdapter {
    +supports(subagent) bool
    +build(subagent, app_client, obo_client, deps) Any
    -_select_client(subagent, app_client, obo_client) AsyncDatabricksOpenAI
}
class DelegationToolAdapter {
    +supports(subagent) bool
    +build(subagent, app_client, obo_client, deps) Any
}
class ToolRegistry {
    <<protocol>>
    +resolve(subagent) ToolAdapter?
}
class DefaultToolRegistry {
    -_adapters: tuple~ToolAdapter~
    +register(adapter) DefaultToolRegistry
    +resolve(subagent) ToolAdapter?
}

AppDependencyContainer o-- OrchestratorDependencies
AppDependencyContainer o-- RuntimeAuthDependencies
AppDependencyContainer o-- HandlerDependencies
AppDependencyContainer ..> AppSettings

OrchestratorDependencies ..> MessageBus
OrchestratorDependencies ..> FunctionToolWrapper
OrchestratorDependencies ..> McpServerFactory

McpToolAdapter ..|> ToolAdapter
LakebaseToolAdapter ..|> ToolAdapter
AppToolAdapter ..|> ToolAdapter
DelegationToolAdapter ..|> ToolAdapter
DefaultToolRegistry ..|> ToolRegistry
DefaultToolRegistry o-- ToolAdapter : ordered adapters
SubagentToolsBuilder ..> ToolRegistry : resolves direct tools

RuntimeAuthDependencies ..> IdentityContextProvider
RuntimeAuthDependencies ..> OboClientFactory
RuntimeAuthDependencies ..> SubagentToolsBuilder
RuntimeAuthDependencies ..> McpServersBuilder
RuntimeAuthDependencies ..> LakebaseToolsBuilder
RuntimeAuthDependencies ..> MessageBus

HandlerDependencies ..> MessageBus
```

## 3. Handler Runtime Pipeline Stages

```mermaid
classDiagram
direction LR

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

class ResponsesAgentRequest
class ResponsesAgentResponse
class ResponsesAgentStreamEvent

RequestStage --> ResponsesAgentRequest
RequestStage --> RuntimeAuthContext

ConnectedStage --> InvokeFinalizedStage : invoke path
ConnectedStage --> StreamExecutedStage : stream path
StreamExecutedStage --> StreamFinalizedStage : finalize

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

class NoOpMessageBus {
    +publish(event_type, payload) None
}
class StructuredLoggingMessageBus {
    +publish(event_type, payload) None
}
class AsyncMessageBus {
    -_inner: MessageBus
    -_queue: queue.Queue
    +publish(event_type, payload) None
}
class KafkaMessageBus {
    -_producer: confluent_kafka.Producer
    -_topic: str
    +publish(event_type, payload) None
}
class RabbitMQMessageBus {
    -_conn: pika.BlockingConnection
    -_exchange: str
    +publish(event_type, payload) None
}
class UcAuditTableMessageBus {
    -_warehouse_id: str
    -_table_fqn: str
    +publish(event_type, payload) None
}

class MessageBusFactory {
    +default_message_bus(settings) MessageBus
}

class AppSettings {
    +message_bus_backend: str
    +message_bus_topic: str
    +message_bus_fail_open: bool
}

MessageBus <|.. NoOpMessageBus
MessageBus <|.. StructuredLoggingMessageBus
MessageBus <|.. AsyncMessageBus
MessageBus <|.. KafkaMessageBus
MessageBus <|.. RabbitMQMessageBus
MessageBus <|.. UcAuditTableMessageBus

AsyncMessageBus o-- MessageBus : wraps inner

MessageBusFactory ..> AppSettings
MessageBusFactory ..> MessageBus : returns strategy
```

## 5. Model Routing and Delegation Control Plane

```mermaid
classDiagram
class ModelSelection {
    +model: str
    +task_type: str
    +reason: str
}
class ModelRoutingModule {
    <<module>>
    +select_model(question, settings) ModelSelection
}
class AgentTaskBus {
    <<protocol>>
    +submit(task) DelegationTaskRecord
    +claim_task(task_id, worker_id) DelegationTaskRecord?
    +claim(worker_id) list~DelegationTaskRecord~
    +complete(result, worker_id) DelegationTaskRecord
    +fail(task_id, worker_id, error_code) DelegationTaskRecord
    +get(task_id) DelegationTaskRecord
}
class UcAgentTaskBus {
    +agent_delegation_tasks
    +agent_delegation_events
}
class AgentTaskWorker {
    +run_once() int
    +run_forever(stop_event) None
}
class DelegationHandoffModule {
    <<module>>
    +build_delegation_tool()
    +execute_delegation()
}
ModelRoutingModule --> ModelSelection
AgentTaskBus <|.. UcAgentTaskBus
AgentTaskWorker --> AgentTaskBus
DelegationHandoffModule --> AgentTaskBus
```

## 6. Subagent Registry

```mermaid
classDiagram
direction TB

class SubagentRegistry {
    +SUBAGENTS: list~SubagentConfig~
    +load_subagents() list~SubagentConfig~
}

class GenieAgents {
    sales_insights_agent
    cdi_agent
}

class SearchAgents {
    product_index_assistant
    flink_support_agent
}

class AppAgents {
    store-intervention-agent
}

class LakebaseAgents {
    lakebase_ods_agent
}

SubagentRegistry --> GenieAgents
SubagentRegistry --> SearchAgents
SubagentRegistry --> AppAgents
SubagentRegistry --> LakebaseAgents
```

The concrete per-environment registry lives in `src/aiserver/contracts/subagents.<target>.json`. Dev currently defines six logical subagents: two Genie MCP routes, two AI Search MCP routes, one Databricks App HITL specialist, and one Lakebase PostgreSQL route. Environment-specific identifiers such as Genie space IDs, Databricks App endpoints, and Lakebase connection fields are maintained in the target registry files rather than this diagram.

## Notes

- All diagrams mirror current implementation naming in `src/aiserver/`.
- Views are logic-isolated: domain/policy, composition/ports, runtime stages, message bus strategy, subagent registry.
- Use with `07-request-execution-flow-class-diagram.md` for invoke-vs-stream pipeline emphasis.
- The durable delegation and model-routing classes above are the control planes that keep agent expansion bounded, observable, and policy-aware.
