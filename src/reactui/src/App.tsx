import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { sendChat, sessionStatusLine } from "./api";
import { maskToken, parsePersonaCommand, parseTokenCommand } from "./commands";
import { settings } from "./config";
import type { ChatMessage, GovernanceMetadata } from "./types";

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
  const personaLine = persona
    ? `Persona for this chat: \`${persona}\`.`
    : "Persona for this chat: not set.";
  return `${tokenLine}\n${personaLine}`;
}

const THEME_STORAGE_KEY = "chat-ui-theme";

const THEMES = [
  { value: "deep-ocean", label: "Deep ocean" },
  { value: "sky-blue", label: "Sky blue" },
  { value: "deep-sky-blue", label: "Deep sky blue" },
] as const;

type ThemeValue = (typeof THEMES)[number]["value"];

function isThemeValue(value: string | null): value is ThemeValue {
  return THEMES.some((theme) => theme.value === value);
}

const STARTERS = [
  "/persona manager",
  "/persona analyst",
  "/persona operator",
  "/persona engineer",
  "What is the monthly aggregated total tax amount from sales receipts?",
  "How do delight scores compare for appointments vs walk-ins?",
  "What is the distribution of sales receipt document type to understand the different document types in sales receipts?",
  "Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?",
  "List latest day's open appointments and their current order status.",
  "Look up product details for brand code 'MICH' and list matching article types.",
];

function renderMarkdown(text: string): JSX.Element {
  const blocks = text.split(/\n\s*\n/);
  return (
    <div className="rich-text">
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        if (
          lines.every((line) => line.includes("|") || /^[-| ]+$/.test(line))
        ) {
          const rows = lines.filter((line) => !/^\s*\|?\s*-+/.test(line));
          return (
            <table key={index}>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row
                      .split("|")
                      .filter(Boolean)
                      .map((cell, cellIndex) => (
                        <td key={cellIndex}>{cell.trim()}</td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        const content = lines.join("\n");
        const heading = content.match(/^(#{1,3})\s+(.+)$/);
        if (heading) {
          const Heading = `h${heading[1].length}` as "h1" | "h2" | "h3";
          return <Heading key={index}>{heading[2]}</Heading>;
        }
        const safeParts = content.split(/(\[[0-9]+\])/g);
        return (
          <p key={index}>
            {safeParts.map((part, partIndex) =>
              part.match(/^\[[0-9]+\]$/) ? (
                <a
                  href={`#citation-${part.slice(1, -1)}`}
                  key={partIndex}
                  className="citation"
                >
                  {part}
                </a>
              ) : (
                part
              ),
            )}
          </p>
        );
      })}
    </div>
  );
}

function GovernancePanel({
  message,
}: {
  message: ChatMessage;
}): JSX.Element | null {
  if (
    message.role !== "assistant" ||
    (!message.tools?.length &&
      !message.sourceCategories?.length &&
      !message.guardrailReasons?.length &&
      !message.truncated)
  )
    return null;
  return (
    <details className="governance-panel">
      <summary>Run context</summary>
      <div className="governance-grid">
        <span>Status</span>
        <strong>{message.status ?? "complete"}</strong>
        {message.tools?.length ? (
          <>
            <span>Tools</span>
            <strong>{message.tools.join(", ")}</strong>
          </>
        ) : null}
        {message.sourceCategories?.length ? (
          <>
            <span>Sources</span>
            <strong>{message.sourceCategories.join(", ")}</strong>
          </>
        ) : null}
        {message.guardrailReasons?.length ? (
          <>
            <span>Guardrails</span>
            <strong>{message.guardrailReasons.join(", ")}</strong>
          </>
        ) : null}
        {message.truncated ? (
          <>
            <span>Budget</span>
            <strong>Response shortened</strong>
          </>
        ) : null}
      </div>
    </details>
  );
}

export default function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: newId(),
      role: "assistant",
      content:
        `## ${settings.companyName} AI Workspace\n${settings.companyTagline}\n\n${settings.chatGreeting}\n\n` +
        "### Available Agents\n" +
        "|      Agent     |    Type   |    Description                                                |\n" +
        "| -------------- | --------- | ------------------------------------------------------------- |\n" +
        "| Sales Insights | Genie     | Revenue trends, store performance, seasonal comparisons       |\n" +
        "| CDI    Metrics | Genie     | Customer Delight Index scores, promoter/detractor analysis    |\n" +
        "| Product  Index | AI Search | Product catalog lookups by code, brand, or description        |\n" +
        "| Flink  Support | AI Search | Flink troubleshooting, configuration guidance, best practices |\n" +
        "| Lakebase   ODS | Lakebase  | Operational data — appointments, orders, invoices, etc.       |\n\n" +
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
  const [starterGroup, setStarterGroup] = useState("Business");
  const [theme, setTheme] = useState<ThemeValue>(() => {
    if (typeof window === "undefined") return "deep-ocean";
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeValue(stored) ? stored : "deep-ocean";
  });
  const chatLogRef = useRef<HTMLElement>(null);
  const conversationId = useMemo(() => newId(), []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  async function submitMessage(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || isSending) {
      return;
    }

    const tokenCommand = parseTokenCommand(
      text,
      settings.setTokenCommand,
      settings.clearTokenCommand,
    );
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

    const userMessage: ChatMessage = {
      id: newId(),
      role: "user",
      content: text,
    };
    const placeholderId = newId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: placeholderId,
        role: "assistant",
        content: "",
        status: "streaming",
      },
    ]);
    setInput("");
    setIsSending(true);

    const history = messages.filter(
      (m) => m.role === "user" || m.role === "assistant",
    );

    try {
      const update = (metadata: GovernanceMetadata) =>
        setMessages((prev) =>
          prev.map((message) =>
            message.id === placeholderId
              ? {
                  ...message,
                  tools: metadata.tools,
                  sourceCategories: metadata.sourceCategories,
                  routePlan: metadata.routePlan,
                  guardrailReasons: metadata.guardrailReasons,
                  truncated: metadata.truncated,
                }
              : message,
          ),
        );
      const result = await sendChat(
        {
          history,
          userMessage: text,
          conversationId,
          persona,
          token,
        },
        {
          onTextDelta: (delta) =>
            setMessages((prev) =>
              prev.map((message) =>
                message.id === placeholderId
                  ? { ...message, content: message.content + delta }
                  : message,
              ),
            ),
          onMetadata: update,
        },
      );

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === placeholderId
            ? {
                ...msg,
                content:
                  result.content || sessionStatusLine(persona, Boolean(token)),
                status:
                  result.metadata.status === "blocked"
                    ? "blocked"
                    : result.metadata.truncated
                      ? "truncated"
                      : "idle",
                tools: result.metadata.tools,
                sourceCategories: result.metadata.sourceCategories,
                routePlan: result.metadata.routePlan,
                guardrailReasons: result.metadata.guardrailReasons,
                truncated: result.metadata.truncated,
              }
            : msg,
        ),
      );
    } catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : "An unexpected error occurred.";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === placeholderId
            ? {
                ...msg,
                content: `${detail}${sessionStatusLine(persona, Boolean(token))}`,
                status: "error",
              }
            : msg,
        ),
      );
    } finally {
      setIsSending(false);
    }
  }

  useEffect(() => {
    const log = chatLogRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages]);

  function clearConversation(): void {
    setMessages([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await submitMessage(input);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <a
            className="brand-logo"
            href="https://www.discounttire.com/"
            target="_blank"
            rel="noreferrer"
          >
            <img
              src="https://www.discounttire.com/favicon.ico"
              alt="Discount Tire"
            />
          </a>
          <div>
            <span className="eyebrow">DISCOUNT TIRE | OPERATIONS</span>
            <h1>{settings.companyName} AI Workspace</h1>
            <p>{settings.companyTagline}</p>
          </div>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={clearConversation}
          title="Clear conversation"
          aria-label="Clear conversation"
        >
          ↺
        </button>
      </header>

      <nav className="utility-nav" aria-label="Workspace navigation">
        <span className="utility-active">AI workspace</span>
        <span>Products</span>
        <span>Store operations</span>
        <span>Support</span>
      </nav>

      <section className="trust-strip" aria-label="Workspace service status">
        <span>
          <strong>Expert context</strong> Governed business sources
        </span>
        <span>
          <strong>Fast answers</strong> Streaming agent responses
        </span>
        <span>
          <strong>Protected</strong> Policy-aware access
        </span>
      </section>

      <section className="context-bar" aria-label="Session context">
        <label>
          Persona
          <select
            value={persona ?? ""}
            onChange={(event) => {
              setPersona(event.target.value || null);
            }}
          >
            <option value="">Default</option>
            {settings.allowedPersonas.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Background
          <select
            value={theme}
            onChange={(event) => {
              const next = event.target.value;
              if (isThemeValue(next)) setTheme(next);
            }}
          >
            {THEMES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <span className={`status-pill ${token ? "is-secure" : ""}`}>
          <span className="status-dot" />
          {token ? "Hybrid OBO" : "App identity"}
        </span>
        {token ? (
          <button
            type="button"
            className="text-button"
            onClick={() => setToken(null)}
          >
            Clear identity
          </button>
        ) : (
          <span className="context-note">Session-scoped authorization</span>
        )}
      </section>

      <section className="starter-area">
        <div className="starter-tabs">
          {["Business", "Operations", "Commands"].map((group) => (
            <button
              key={group}
              type="button"
              className={starterGroup === group ? "active" : ""}
              onClick={() => setStarterGroup(group)}
            >
              {group}
            </button>
          ))}
        </div>
        <div className="starters">
          {STARTERS.filter((starter) =>
            starterGroup === "Commands"
              ? starter.startsWith("/")
              : starterGroup === "Operations"
                ? starter.toLowerCase().includes("flink") ||
                  starter.toLowerCase().includes("appointments")
                : !starter.startsWith("/") &&
                  !starter.toLowerCase().includes("flink") &&
                  !starter.toLowerCase().includes("appointments"),
          ).map((starter, index) => (
            <button
              key={`${starterGroup}-${index}-${starter}`}
              type="button"
              onClick={() => {
                void submitMessage(starter);
              }}
              disabled={isSending}
            >
              {starter}
            </button>
          ))}
        </div>
      </section>

      <main
        className="chat-log"
        ref={chatLogRef}
        aria-live="polite"
        aria-busy={isSending}
      >
        {messages.map((message) => (
          <article
            key={message.id}
            className={`bubble bubble-${message.role} status-${message.status ?? "idle"}`}
          >
            {message.role === "assistant" &&
            message.status === "streaming" &&
            !message.content ? (
              <div className="thinking">
                <span /> <span /> <span /> Retrieving context
              </div>
            ) : (
              renderMarkdown(message.content)
            )}
            <GovernancePanel message={message} />
          </article>
        ))}
      </main>

      <form className="chat-input" onSubmit={onSubmit}>
        <textarea
          aria-label="Message"
          autoFocus
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={3}
          placeholder="Ask a question or run /persona, /token commands"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          title="Send message"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}
