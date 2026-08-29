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
  approvalState?: HumanApprovalState;
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
  setPersonaCommand: string;
  clearPersonaCommand: string;
  allowedPersonas: string[];
}
