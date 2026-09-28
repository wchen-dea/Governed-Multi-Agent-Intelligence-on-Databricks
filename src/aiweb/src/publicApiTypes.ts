/** Types for the application-facing API.  Runtime/MLflow details stay out of this module. */

export type PublicMessageRole = "user" | "assistant";

export interface PublicMessage {
  role: PublicMessageRole;
  content: string;
}

export interface ChatRequest {
  messages: PublicMessage[];
  conversation_id: string;
  persona: string | null;
  stream: boolean;
}

export type ApprovalDecision = "approved" | "rejected" | "more_info_requested";

export interface ApprovalDecisionRequest {
  request_id: string;
  agent_name: string;
  store_id?: string | null;
  approver?: string | null;
  decision: ApprovalDecision;
  reason?: string | null;
  notes?: string | null;
}

export interface DelegationResponse {
  task_id: string;
  correlation_id?: string | null;
  source_agent: string;
  target_agent: string;
  intent: string;
  status: string;
  attempt?: number | null;
  max_attempts?: number | null;
  failure_code?: string | null;
  completed: boolean;
}

export interface ApprovalResponse {
  request_id: string;
  agent_name: string;
  store_id?: string | null;
  approver?: string | null;
  decision: string;
  reason?: string | null;
  notes?: string | null;
  status: string;
}

export interface ApprovalDecisionResponse {
  status: "ok";
  approval: ApprovalResponse;
  delegation: DelegationResponse | null;
}

export interface PublicError {
  code: string;
  message: string;
  request_id?: string | null;
}

export type ChatStreamEvent =
  | { type: "text_delta"; delta: string }
  | { type: "metadata"; metadata: Record<string, unknown> }
  | { type: "completed" }
  | { type: "error"; error: PublicError };
