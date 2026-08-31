import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { sendChat, sessionStatusLine, submitApprovalDecision } from "./api";
import { maskToken, parseTokenCommand } from "./commands";
import { settings } from "./config";
import type {
  ChatMessage,
  GovernanceMetadata,
  HumanApprovalState,
} from "./types";

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

const STARTER_GROUPS = ["Operations", "Insight", "HITL", "DE"] as const;

type StarterGroup = (typeof STARTER_GROUPS)[number];

const PERSONA_STARTER_GROUPS: Record<string, readonly StarterGroup[]> = {
  "store-manager": ["Operations"],
  executive: ["Insight", "HITL"],
  "de-support": ["DE"],
};

const STARTERS: { group: StarterGroup; text: string }[] = [
  {
    group: "Operations",
    text: "What are the top 5 stores by revenue for the current season?",
  },
  {
    group: "Operations",
    text: "Look up product details for brand code 'MICH' and list matching article types.",
  },
  {
    group: "Operations",
    text: "List today's open appointments and their current order status.",
  },
  {
    group: "DE",
    text: "Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?",
  },
  {
    group: "DE",
    text: "What Flink configuration tuning steps should DE support check first when backpressure appears?",
  },
  {
    group: "Insight",
    text: "How do CDI promoter and detractor counts compare across stores this month?",
  },
  {
    group: "Insight",
    text: "What are the top 5 stores by appointment count, and are they also in the top 20 stores by sales?",
  },
  {
    group: "Insight",
    text: "Which stores have strong sales performance but below-average CDI scores, where we might be winning on revenue but losing on customer experience?",
  },
  {
    group: "Insight",
    text: "Using the 2025-08-30 to 2026-04-30 time window, which stores are showing strong sales but below-average CDI scores—where we may be performing well on revenue but falling short on CDI?",
  },
  {
    group: "HITL",
    text: "Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.",
  },
];

function renderMarkdown(text: string): JSX.Element {
  const lines = text.split("\n");
  const blocks: JSX.Element[] = [];
  let currentTableLines: string[] = [];
  let currentTextLines: string[] = [];

  function flushText() {
    if (currentTextLines.length > 0) {
      const content = currentTextLines.join("\n").trim();
      if (content) {
        const safeParts = content.split(/(\[[0-9]+\])/g);
        blocks.push(
          <p key={`p-${blocks.length}`}>
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
          </p>,
        );
      }
      currentTextLines = [];
    }
  }

  function flushTable() {
    if (currentTableLines.length > 0) {
      const rows = currentTableLines.filter(
        (line) => !/^\s*\|?\s*[-| ]+\s*$/.test(line),
      );
      if (rows.length > 0) {
        blocks.push(
          <table key={`table-${blocks.length}`}>
            <tbody>
              {rows.map((row, rowIndex) => {
                const cells = row.split("|").map((c) => c.trim());
                if (cells.length > 1 && cells[0] === "") cells.shift();
                if (cells.length > 1 && cells[cells.length - 1] === "")
                  cells.pop();

                return (
                  <tr key={rowIndex}>
                    {cells.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cell}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>,
        );
      }
      currentTableLines = [];
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      flushText();
      flushTable();
      continue;
    }

    if (trimmed.startsWith("#")) {
      const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
      if (headingMatch) {
        flushText();
        flushTable();
        const Heading = `h${headingMatch[1].length}` as "h1" | "h2" | "h3";
        blocks.push(
          <Heading key={`h-${blocks.length}`}>{headingMatch[2]}</Heading>,
        );
        continue;
      }
    }

    if (trimmed.includes("|")) {
      flushText();
      currentTableLines.push(line);
      continue;
    }

    flushTable();
    currentTextLines.push(line);
  }

  flushText();
  flushTable();

  return <div className="rich-text">{blocks}</div>;
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

function ApprovalActions({
  message,
  token,
  onDecision,
}: {
  message: ChatMessage;
  token: string | null;
  onDecision: (messageId: string, state: HumanApprovalState) => void;
}): JSX.Element | null {
  const [decisionInFlight, setDecisionInFlight] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  if (!message.approvalState) {
    return null;
  }

  if (message.approvalState.status !== "pending") {
    const delegation = message.approvalState.delegation;
    return (
      <section
        className="approval-actions"
        aria-label="Manager approval status"
      >
        <div className="approval-status-summary">
          <strong>Manager decision recorded</strong>
          <span>
            Status: {message.approvalState.status}
            {delegation
              ? ` | Follow-up task: ${delegation.task_id} (${delegation.status ?? "pending"})`
              : ""}
          </span>
        </div>
      </section>
    );
  }

  async function decide(
    decision: "approved" | "rejected" | "more_info_requested",
  ): Promise<void> {
    setDecisionInFlight(decision);
    setDecisionError(null);
    try {
      const requestId = message.openaiRun?.run_id || message.id;
      const state = await submitApprovalDecision({
        requestId,
        agentName: "store-intervention-agent",
        approver: "manager",
        decision,
        reason:
          decision === "approved"
            ? "Manager approved the proposed planning step."
            : decision === "rejected"
              ? "Manager rejected the proposed planning step."
              : "Manager requested additional evidence before deciding.",
        notes: "No operational dispatch is authorized by this UI action.",
        token,
      });
      onDecision(message.id, state);
    } catch (error) {
      setDecisionError(
        error instanceof Error
          ? error.message
          : "Approval decision could not be saved.",
      );
    } finally {
      setDecisionInFlight(null);
    }
  }

  return (
    <section className="approval-actions" aria-label="Manager approval actions">
      <div>
        <strong>Manager approval required</strong>
        <span>
          {message.approvalState.reason ??
            "Review this packet before any action."}
        </span>
      </div>
      <div className="approval-buttons">
        <button
          type="button"
          disabled={decisionInFlight !== null}
          onClick={() => void decide("approved")}
        >
          {decisionInFlight === "approved" ? "Saving..." : "Approve planning"}
        </button>
        <button
          type="button"
          disabled={decisionInFlight !== null}
          onClick={() => void decide("more_info_requested")}
        >
          {decisionInFlight === "more_info_requested"
            ? "Saving..."
            : "Request more info"}
        </button>
        <button
          type="button"
          disabled={decisionInFlight !== null}
          onClick={() => void decide("rejected")}
        >
          {decisionInFlight === "rejected" ? "Saving..." : "Reject"}
        </button>
      </div>
      {decisionError ? <span role="alert">{decisionError}</span> : null}
    </section>
  );
}

export default function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: newId(),
      role: "assistant",
      content:
        "### Available Agents\n\n" +
        "| Agent | Type | Description |\n" +
        "| --- | --- | --- |\n" +
        "| Sales Insights | Genie | Revenue trends, store performance, seasonal comparisons |\n" +
        "| CDI Metrics | Genie | Customer Delight Index scores, promoter/detractor analysis |\n" +
        "| Product Index | AI Search | Product catalog lookups by code, brand, or description |\n" +
        "| Flink Support | AI Search | Flink troubleshooting, configuration guidance, best practices |\n" +
        "| Store Intervention | Databricks App | Human-in-the-loop store risk review and intervention planning |\n" +
        "| Lakebase ODS | Lakebase | Operational data — appointments, orders, invoices, etc. |\n\n" +
        "### Persona Selection\n\n" +
        "Select a persona from the dropdown above the chat.\n\n" +
        "### Session Commands\n\n" +
        "/token <databricks_access_token>\n" +
        "/clear-token\n\n" +
        statusLines(null, null),
    },
  ]);
  const [token, setToken] = useState<string | null>(null);
  const [persona, setPersona] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [starterGroup, setStarterGroup] = useState<StarterGroup>("Operations");
  const [theme, setTheme] = useState<ThemeValue>(() => {
    if (typeof window === "undefined") return "deep-ocean";
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeValue(stored) ? stored : "deep-ocean";
  });
  const chatLogRef = useRef<HTMLElement>(null);
  const conversationId = useMemo(() => newId(), []);
  const activeRequestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const enabledStarterGroups = useMemo(
    () => (persona ? (PERSONA_STARTER_GROUPS[persona] ?? []) : []),
    [persona],
  );

  useEffect(() => {
    if (enabledStarterGroups.includes(starterGroup)) {
      return;
    }
    setStarterGroup(enabledStarterGroups[0] ?? "Operations");
  }, [enabledStarterGroups, starterGroup]);

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
                  openaiRun: metadata.openaiRun,
                  approvalState: metadata.approvalState,
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
          onRequestController: (controller) => {
            activeRequestRef.current = controller;
          },
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
                openaiRun: result.metadata.openaiRun,
                approvalState: result.metadata.approvalState,
              }
            : msg,
        ),
      );
    } catch (error) {
      const cancelled =
        error instanceof DOMException && error.name === "AbortError";
      const detail = cancelled
        ? "Query canceled."
        : error instanceof Error
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
      activeRequestRef.current = null;
      setIsSending(false);
    }
  }

  function cancelCurrentQuery(): void {
    activeRequestRef.current?.abort();
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
            <h1>SBS AI Systems</h1>
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

      <section className="context-bar" aria-label="Session context">
        <div className="auth-status-block">
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
        </div>
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
      </section>

      <section className="starter-area">
        <div className="starter-tabs">
          {STARTER_GROUPS.map((group) => (
            <button
              key={group}
              type="button"
              className={starterGroup === group ? "active" : ""}
              onClick={() => setStarterGroup(group)}
              disabled={!enabledStarterGroups.includes(group)}
            >
              {group}
            </button>
          ))}
        </div>
        <div className="starters">
          {STARTERS.filter((starter) => starter.group === starterGroup).map(
            (starter, index) => (
              <button
                key={`${starterGroup}-${index}-${starter.text}`}
                type="button"
                onClick={() => {
                  void submitMessage(starter.text);
                }}
                disabled={
                  isSending || !enabledStarterGroups.includes(starter.group)
                }
              >
                {starter.text}
              </button>
            ),
          )}
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
            <ApprovalActions
              message={message}
              token={token}
              onDecision={(messageId, state) =>
                setMessages((prev) =>
                  prev.map((item) =>
                    item.id === messageId
                      ? { ...item, approvalState: state }
                      : item,
                  ),
                )
              }
            />
          </article>
        ))}
      </main>

      <form className="chat-input" onSubmit={onSubmit}>
        <textarea
          aria-label="Message"
          autoFocus
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!isSending && input.trim()) {
                void submitMessage(input);
              }
            }
          }}
          rows={2}
          placeholder="Ask a question or run /token commands"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          title="Send message"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
        {isSending ? (
          <button
            className="cancel-query"
            type="button"
            onClick={cancelCurrentQuery}
            title="Cancel current query"
          >
            Cancel
          </button>
        ) : null}
      </form>
    </div>
  );
}
