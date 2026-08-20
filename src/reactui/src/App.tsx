import { FormEvent, useMemo, useState } from "react";
import { sendChat, sessionStatusLine } from "./api";
import { maskToken, parsePersonaCommand, parseTokenCommand } from "./commands";
import { settings } from "./config";
import type { ChatMessage } from "./types";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function statusLines(token: string | null, persona: string | null): string {
  const tokenLine = token
    ? "Auth mode for this chat: Hybrid (app + forwarded user OBO token)."
    : "Auth mode for this chat: App identity only.";
  const personaLine = persona ? `Persona for this chat: \`${persona}\`.` : "Persona for this chat: not set.";
  return `${tokenLine}\n${personaLine}`;
}

const STARTERS = [
  "/persona manager",
  "/persona analyst",
  "/persona operator",
  "/persona engineer",
  "Any products matching 'all season 225/65R17 tire'",
  "How do delight scores compare for appointments vs walk-ins?",
  "What is the distribution of sales_receipt_document_type_code to understand the different document types in sales receipts?",
  "Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?",
  "List today's open appointments and their current order status.",
  "Look up product details for brand code 'MICH' and list matching article types.",
];

export default function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: newId(),
      role: "assistant",
      content:
        `## ${settings.companyName} AI Workspace\n${settings.companyTagline}\n\n${settings.chatGreeting}\n\n` +
        "### Available Agents\n" +
        "|      Agent     |    Type   |    Description                                                | Personas              |\n" +
        "| -------------- | --------- | ------------------------------------------------------------- | --------------------- |\n" +
        "| Sales Insights | Genie     | Revenue trends, store performance, seasonal comparisons       | manager               |\n" +
        "| CDI    Metrics | Genie     | Customer Delight Index scores, promoter/detractor analysis    | manager               |\n" +
        "| Product  Index | AI Search | Product catalog lookups by code, brand, or description        | analyst, manager, engineer |\n" +
        "| Flink  Support | AI Search | Flink troubleshooting, configuration guidance, best practices | operator, manager, engineer |\n" +
        "| Lakebase   ODS | Lakebase  | Operational data — appointments, orders, invoices, scheduling | analyst, manager, engineer |\n\n" +
        "### Persona Selection\n" +
        "Pick a persona from the starter chips, or run /persona <persona>.\n" +
        `Accepted personas: ${settings.allowedPersonas.join(", ")}\n\n` +
        "### Session Commands\n" +
        "/token <databricks_access_token>\n/clear-token\n/persona <persona>\n/clear-persona\n\n" +
        statusLines(null, null),
    },
  ]);
  const [token, setToken] = useState<string | null>(null);
  const [persona, setPersona] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const conversationId = useMemo(() => newId(), []);

  async function submitMessage(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || isSending) {
      return;
    }

    const tokenCommand = parseTokenCommand(text, settings.setTokenCommand, settings.clearTokenCommand);
    if (tokenCommand.kind === "clear") {
      setToken(null);
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: `Forwarded user token removed for this chat session.\n${statusLines(null, persona)}`,
        },
      ]);
      setInput("");
      return;
    }

    if (tokenCommand.kind === "set") {
      const tokenValue = tokenCommand.token;
      if (!tokenValue) {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: `Token command format: ${settings.setTokenCommand} <databricks_access_token>`,
          },
        ]);
        setInput("");
        return;
      }
      setToken(tokenValue);
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content:
            `Forwarded user token saved for this chat session.\nToken: \`${maskToken(tokenValue)}\`\n` +
            `Subsequent requests will include ${settings.forwardedAccessTokenHeader}.\n${statusLines(tokenValue, persona)}`,
        },
      ]);
      setInput("");
      return;
    }

    const personaCommand = parsePersonaCommand(
      text,
      settings.setPersonaCommand,
      settings.clearPersonaCommand,
    );

    if (personaCommand.kind === "clear") {
      setPersona(null);
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: `Persona cleared for this chat session.\n${statusLines(token, null)}`,
        },
      ]);
      setInput("");
      return;
    }

    if (personaCommand.kind === "set") {
      const normalized = personaCommand.persona?.toLowerCase() ?? "";
      if (!normalized) {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: `Persona command format: ${settings.setPersonaCommand} <persona>\nAccepted personas: ${settings.allowedPersonas.join(", ")}`,
          },
        ]);
        setInput("");
        return;
      }
      if (!settings.allowedPersonas.includes(normalized)) {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: "assistant",
            content: `Invalid persona: \`${personaCommand.persona}\`.\nAccepted personas: ${settings.allowedPersonas.join(", ")}`,
          },
        ]);
        setInput("");
        return;
      }
      setPersona(normalized);
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: "assistant",
          content: `Persona saved for this chat session.\n${statusLines(token, normalized)}`,
        },
      ]);
      setInput("");
      return;
    }

    const userMessage: ChatMessage = { id: newId(), role: "user", content: text };
    const placeholderId = newId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: placeholderId, role: "assistant", content: "Working on your request..." },
    ]);
    setInput("");
    setIsSending(true);

    const history = messages.filter((m) => m.role === "user" || m.role === "assistant");

    try {
      const result = await sendChat({
        history,
        userMessage: text,
        conversationId,
        persona,
        token,
      });

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === placeholderId
            ? { ...msg, content: result.content || sessionStatusLine(persona, Boolean(token)) }
            : msg,
        ),
      );
    } catch (error) {
      const detail = error instanceof Error ? error.message : "An unexpected error occurred.";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === placeholderId
            ? {
                ...msg,
                content: `${detail}${sessionStatusLine(persona, Boolean(token))}`,
              }
            : msg,
        ),
      );
    } finally {
      setIsSending(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await submitMessage(input);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>{settings.companyName} React UI</h1>
        <p>{settings.companyTagline}</p>
      </header>

      <section className="starters">
        {STARTERS.map((starter) => (
          <button
            key={starter}
            type="button"
            onClick={() => {
              void submitMessage(starter);
            }}
            disabled={isSending}
          >
            {starter}
          </button>
        ))}
      </section>

      <main className="chat-log">
        {messages.map((message) => (
          <article key={message.id} className={`bubble bubble-${message.role}`}>
            <pre>{message.content}</pre>
          </article>
        ))}
      </main>

      <form className="chat-input" onSubmit={onSubmit}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={3}
          placeholder="Ask a question or run /persona, /token commands"
        />
        <button type="submit" disabled={isSending || !input.trim()}>
          {isSending ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}