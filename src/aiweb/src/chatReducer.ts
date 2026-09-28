import type {
  ChatMessage,
  GovernanceMetadata,
  HumanApprovalState,
} from "./types";

export type ChatAction =
  | { type: "append"; messages: ChatMessage[] }
  | { type: "stream-delta"; id: string; delta: string }
  | { type: "metadata"; id: string; metadata: GovernanceMetadata }
  | {
      type: "complete";
      id: string;
      content: string;
      metadata: GovernanceMetadata;
    }
  | { type: "error"; id: string; content: string }
  | { type: "approval"; id: string; approvalState: HumanApprovalState }
  | { type: "reset"; message: ChatMessage };

export function chatReducer(
  state: ChatMessage[],
  action: ChatAction,
): ChatMessage[] {
  switch (action.type) {
    case "append":
      return [...state, ...action.messages];
    case "stream-delta":
      return state.map((message) =>
        message.id === action.id
          ? { ...message, content: message.content + action.delta }
          : message,
      );
    case "metadata":
      return state.map((message) =>
        message.id === action.id
          ? {
              ...message,
              tools: action.metadata.tools,
              sourceCategories: action.metadata.sourceCategories,
              routePlan: action.metadata.routePlan,
              guardrailReasons: action.metadata.guardrailReasons,
              unavailableTools: action.metadata.unavailableTools,
              truncated: action.metadata.truncated,
              openaiRun: action.metadata.openaiRun,
              approvalState: action.metadata.approvalState,
            }
          : message,
      );
    case "complete":
      return state.map((message) =>
        message.id === action.id
          ? {
              ...message,
              content: action.content,
              status:
                action.metadata.status === "blocked"
                  ? "blocked"
                  : action.metadata.truncated
                    ? "truncated"
                    : "idle",
              tools: action.metadata.tools,
              sourceCategories: action.metadata.sourceCategories,
              routePlan: action.metadata.routePlan,
              guardrailReasons: action.metadata.guardrailReasons,
              unavailableTools: action.metadata.unavailableTools,
              truncated: action.metadata.truncated,
              openaiRun: action.metadata.openaiRun,
              approvalState: action.metadata.approvalState,
            }
          : message,
      );
    case "error":
      return state.map((message) =>
        message.id === action.id
          ? { ...message, content: action.content, status: "error" }
          : message,
      );
    case "approval":
      return state.map((message) =>
        message.id === action.id
          ? { ...message, approvalState: action.approvalState }
          : message,
      );
    case "reset":
      return [action.message];
  }
}
