export type Role = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  status?: "idle" | "streaming" | "blocked" | "error" | "truncated";
  tools?: string[];
  sourceCategories?: string[];
  routePlan?: RoutePlan;
  guardrailReasons?: string[];
  unavailableTools?: string[];
  truncated?: boolean;
  openaiRun?: OpenAIAgentRunMetadata;
  approvalState?: HumanApprovalState;
}

export interface OpenAIAgentRunMetadata {
  run_id?: string;
  api?: string;
  model?: string;
  model_task_type?: string;
  model_reason?: string;
  candidate_subagents?: string[];
  selected_tool_names?: string[];
  unavailable_tool_details?: string[];
  ai_gateway_enabled?: boolean;
}

export interface HumanApprovalState {
  status:
    | "not_required"
    | "pending"
    | "approved"
    | "rejected"
    | "more_info_requested"
    | "expired";
  required: boolean;
  approver?: string | null;
  decision?: string | null;
  reason?: string | null;
  delegation?: DelegationStatus | null;
}

export interface DelegationStatus {
  task_id: string;
  correlation_id?: string;
  source_agent?: string;
  target_agent?: string;
  intent?: string;
  status?: string;
  attempt?: number;
  max_attempts?: number;
  failure_code?: string | null;
  completed?: boolean;
}

export interface RoutePlan {
  candidates: string[];
  reason: string;
  confidence: number;
  requires_evidence: boolean;
}

export interface GovernanceMetadata {
  routePlan?: RoutePlan;
  tools: string[];
  sourceCategories: string[];
  guardrailReasons: string[];
  unavailableTools: string[];
  truncated: boolean;
  status?: string;
  openaiRun?: OpenAIAgentRunMetadata;
  approvalState?: HumanApprovalState;
}

export interface StreamHints {
  categories: Set<string>;
  tools: Set<string>;
}

export interface FrontendSettings {
  backendUrl: string;
  chatGreeting: string;
  timeoutSeconds: number;
  companyName: string;
  companyTagline: string;
  forwardedAccessTokenHeader: string;
  setTokenCommand: string;
  clearTokenCommand: string;
  allowedPersonas: string[];
}
