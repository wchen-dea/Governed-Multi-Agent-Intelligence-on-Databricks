import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { sendChat, sessionStatusLine } from "./api";
import { maskToken, parseTokenCommand } from "./commands";
import { settings } from "./config";
import { chatReducer } from "./chatReducer";
import type { ChatMessage, GovernanceMetadata } from "./types";

export const MAX_HISTORY_MESSAGES = 20;

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto)
    return crypto.randomUUID();
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function statusLines(token: string | null, persona: string | null): string {
  const tokenLine = token
    ? "Auth mode for this chat: Hybrid (app + forwarded user OBO token)."
    : "Auth mode for this chat: App identity only.";
  const personaLine = persona
    ? `Persona for this chat: \`${persona}\`.`
    : "Persona for this chat: not set.";
  return `${tokenLine}\n${personaLine}`;
}

export function createWelcomeMessage(
  token: string | null,
  persona: string | null,
): ChatMessage {
  return {
    id: newId(),
    role: "assistant",
    content:
      "### Available Agents\n\n" +
      "| Agent | Type | Description | Persona |\n| --- | --- | --- | --- |\n" +
      "| Sales Insights | Genie | Revenue trends, store performance, seasonal comparisons | executive |\n" +
      "| CDI Metrics | Genie | Customer Delight Index scores, promoter/detractor analysis | executive |\n" +
      "| Store Intervention | Databricks App | Human-in-the-loop store risk review and intervention planning | executive |\n" +
      "| Product Index | AI Search | Product catalog lookups by code, brand, or description | store-manager |\n" +
      "| Lakebase ODS | Lakebase | Operational data — appointments, orders, invoices, etc. | store-manager |\n" +
      "| Flink Support | AI Search | Flink troubleshooting, configuration guidance, best practices | de-support |\n\n" +
      "### Persona Selection\n\nSelect a persona from the dropdown above the chat.\n\n" +
      "### Session Commands\n\n/token <databricks_access_token>\n/clear-token\n\n" +
      statusLines(token, persona),
  };
}

function requestHistory(messages: ChatMessage[]): ChatMessage[] {
  return messages
    .filter(
      (message) => message.role === "user" || message.role === "assistant",
    )
    .slice(-MAX_HISTORY_MESSAGES)
    .map(({ id: _id, status: _status, ...message }) => message as ChatMessage);
}

export function useChatSession(persona: string | null) {
  const [messages, dispatch] = useReducer(chatReducer, undefined, () => [
    createWelcomeMessage(null, null),
  ]);
  const [token, setToken] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const conversationIdRef = useRef(newId());
  const activeRequestRef = useRef<AbortController | null>(null);
  const initialMessageIdRef = useRef(messages[0].id);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  const submitMessage = useCallback(
    async (raw: string): Promise<void> => {
      const text = raw.trim();
      if (!text || isSending) return;
      const command = parseTokenCommand(
        text,
        settings.setTokenCommand,
        settings.clearTokenCommand,
      );
      if (command.kind === "clear") {
        setToken(null);
        dispatch({
          type: "append",
          messages: [
            {
              id: newId(),
              role: "assistant",
              content: `Forwarded user token removed for this chat session.\n${statusLines(null, persona)}`,
            },
          ],
        });
        return;
      }
      if (command.kind === "set") {
        if (!command.token) {
          dispatch({
            type: "append",
            messages: [
              {
                id: newId(),
                role: "assistant",
                content: `Token command format: ${settings.setTokenCommand} <databricks_access_token>`,
              },
            ],
          });
        } else {
          setToken(command.token);
          dispatch({
            type: "append",
            messages: [
              {
                id: newId(),
                role: "assistant",
                content: `Forwarded user token saved for this chat session.\nToken: \`${maskToken(command.token)}\`\nSubsequent requests will include ${settings.forwardedAccessTokenHeader}.\n${statusLines(command.token, persona)}`,
              },
            ],
          });
        }
        return;
      }

      const userMessage: ChatMessage = {
        id: newId(),
        role: "user",
        content: text,
      };
      const placeholderId = newId();
      const history = requestHistory(messages);
      dispatch({
        type: "append",
        messages: [
          { ...userMessage },
          {
            id: placeholderId,
            role: "assistant",
            content: "",
            status: "streaming",
          },
        ],
      });
      setIsSending(true);
      try {
        const result = await sendChat(
          {
            history,
            userMessage: text,
            conversationId: conversationIdRef.current,
            persona,
            token,
          },
          {
            onTextDelta: (delta) =>
              dispatch({ type: "stream-delta", id: placeholderId, delta }),
            onMetadata: (metadata: GovernanceMetadata) =>
              dispatch({ type: "metadata", id: placeholderId, metadata }),
            onRequestController: (controller) => {
              activeRequestRef.current = controller;
            },
          },
        );
        dispatch({
          type: "complete",
          id: placeholderId,
          content: result.content || sessionStatusLine(persona, Boolean(token)),
          metadata: result.metadata,
        });
      } catch (error) {
        const cancelled =
          error instanceof DOMException && error.name === "AbortError";
        const detail = cancelled
          ? "Query canceled."
          : error instanceof Error
            ? error.message
            : "An unexpected error occurred.";
        dispatch({
          type: "error",
          id: placeholderId,
          content: `${detail}${sessionStatusLine(persona, Boolean(token))}`,
        });
      } finally {
        activeRequestRef.current = null;
        setIsSending(false);
      }
    },
    [isSending, messages, persona, token],
  );

  const cancelCurrentQuery = useCallback(
    () => activeRequestRef.current?.abort(),
    [],
  );
  const clearConversation = useCallback(() => {
    activeRequestRef.current?.abort();
    const welcome = createWelcomeMessage(token, persona);
    initialMessageIdRef.current = welcome.id;
    conversationIdRef.current = newId();
    dispatch({ type: "reset", message: welcome });
    setIsSending(false);
  }, [persona, token]);

  const updateApproval = useCallback(
    (
      messageId: string,
      approvalState: NonNullable<ChatMessage["approvalState"]>,
    ) => dispatch({ type: "approval", id: messageId, approvalState }),
    [],
  );

  return {
    messages,
    token,
    setToken,
    isSending,
    submitMessage,
    cancelCurrentQuery,
    clearConversation,
    updateApproval,
    initialMessageId: initialMessageIdRef.current,
  };
}
