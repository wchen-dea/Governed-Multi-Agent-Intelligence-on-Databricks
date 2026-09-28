import { FormEvent, memo, useEffect, useMemo, useRef, useState } from "react";
import { submitApprovalDecision } from "./api";
import { settings } from "./config";
import MessageMarkdown from "./MessageMarkdown";
import { useChatSession } from "./useChatSession";
import type { ChatMessage, HumanApprovalState } from "./types";

const THEMES = [
  { value: "deep-ocean", label: "Deep ocean" },
  { value: "sky-blue", label: "Sky blue" },
  { value: "deep-sky-blue", label: "Deep sky blue" },
] as const;
type ThemeValue = (typeof THEMES)[number]["value"];
type StarterGroup = "Operations" | "Insights" | "HITL" | "DE";
const STARTER_GROUPS: StarterGroup[] = ["Operations", "Insights", "HITL", "DE"];
const PERSONA_STARTER_GROUPS: Record<string, readonly StarterGroup[]> = {
  "store-manager": ["Operations"],
  executive: ["Insights", "HITL"],
  "de-support": ["DE"],
};
const STARTERS: { group: StarterGroup; text: string }[] = [
  {
    group: "Operations",
    text: "Using the latest available season, which stores had the highest total net_sales in the last 30 days? Include Store Code and total net sales.",
  },
  {
    group: "Operations",
    text: "Look up product_code '000000000000183662' and return product_description, brand_code, and article_type.",
  },
  {
    group: "Operations",
    text: "List the latest open appointments and include the current status of each linked order.",
  },
  {
    group: "DE",
    text: "Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?",
  },
  {
    group: "DE",
    text: "Using the ORE platform and pipeline support articles, what Flink configuration checks should DE support perform first when backpressure appears?",
  },
  {
    group: "Insights",
    text: "What are the top 5 stores by appointment count, and are they also in the top 20 stores by sales?",
  },
  {
    group: "Insights",
    text: "Compare the latest rolling CDI NPS with total net_sales by Store Code. Which high-revenue stores have below-average customer delight, and what are their promoter, detractor, and response counts?",
  },
  {
    group: "HITL",
    text: "Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.",
  },
];

function isTheme(value: string): value is ThemeValue {
  return THEMES.some((theme) => theme.value === value);
}

function GovernancePanel({ message }: { message: ChatMessage }) {
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
  onDecision: (id: string, state: HumanApprovalState) => void;
}) {
  const [inFlight, setInFlight] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const approval = message.approvalState;
  if (!approval) return null;
  if (approval.status !== "pending")
    return (
      <section
        className="approval-actions"
        aria-label="Manager approval status"
      >
        <div className="approval-status-summary">
          <strong>Manager decision recorded</strong>
          <span>
            Status: {approval.status}
            {approval.delegation
              ? ` | Follow-up task: ${approval.delegation.task_id} (${approval.delegation.status ?? "pending"})`
              : ""}
          </span>
        </div>
      </section>
    );
  async function decide(
    decision: "approved" | "rejected" | "more_info_requested",
  ) {
    setInFlight(decision);
    setError(null);
    try {
      const state = await submitApprovalDecision({
        requestId: message.openaiRun?.run_id || message.id,
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
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Approval decision could not be saved.",
      );
    } finally {
      setInFlight(null);
    }
  }
  return (
    <section className="approval-actions" aria-label="Manager approval actions">
      <div>
        <strong>Manager approval required</strong>
        <span>
          {approval.reason ?? "Review this packet before any action."}
        </span>
      </div>
      <div className="approval-buttons">
        <button
          type="button"
          disabled={inFlight !== null}
          onClick={() => void decide("approved")}
        >
          {inFlight === "approved" ? "Saving..." : "Approve planning"}
        </button>
        <button
          type="button"
          disabled={inFlight !== null}
          onClick={() => void decide("more_info_requested")}
        >
          {inFlight === "more_info_requested"
            ? "Saving..."
            : "Request more info"}
        </button>
        <button
          type="button"
          disabled={inFlight !== null}
          onClick={() => void decide("rejected")}
        >
          {inFlight === "rejected" ? "Saving..." : "Reject"}
        </button>
      </div>
      {error ? <span role="alert">{error}</span> : null}
    </section>
  );
}

const ChatMessage = memo(function ChatMessage({
  message,
  token,
  onDecision,
}: {
  message: ChatMessage;
  token: string | null;
  onDecision: (id: string, state: HumanApprovalState) => void;
}) {
  return (
    <article
      className={`bubble bubble-${message.role} status-${message.status ?? "idle"}`}
    >
      {message.role === "assistant" &&
      message.status === "streaming" &&
      !message.content ? (
        <div className="thinking">
          <span /> <span /> <span /> Retrieving context
        </div>
      ) : (
        <MessageMarkdown text={message.content} />
      )}
      <GovernancePanel message={message} />
      <ApprovalActions
        message={message}
        token={token}
        onDecision={onDecision}
      />
    </article>
  );
});

function useTranscription(
  input: string,
  isSending: boolean,
  setInput: (value: string) => void,
) {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<{ abort: () => void } | null>(null);
  const prefixRef = useRef("");
  useEffect(() => () => recognitionRef.current?.abort(), []);
  function startTranscription() {
    if (isSending || isTranscribing) return;
    const browser = window as typeof window & {
      SpeechRecognition?: new () => any;
      webkitSpeechRecognition?: new () => any;
    };
    const Constructor =
      browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
    if (!Constructor) {
      setError("Voice transcription is not supported by this browser.");
      return;
    }
    const recognition = new Constructor();
    recognitionRef.current = recognition;
    recognition.lang = navigator.language || "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0].transcript.trim())
        .filter(Boolean)
        .join(" ");
      if (transcript)
        setInput(
          prefixRef.current ? `${prefixRef.current} ${transcript}` : transcript,
        );
    };
    recognition.onerror = (event: { error: string }) =>
      setError(
        event.error === "not-allowed"
          ? "Microphone access was not allowed."
          : "Voice transcription failed. Please try again.",
      );
    recognition.onend = () => {
      recognitionRef.current = null;
      prefixRef.current = "";
      setIsTranscribing(false);
    };
    setError(null);
    prefixRef.current = input.trim();
    setIsTranscribing(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setIsTranscribing(false);
      setError("Voice transcription could not be started.");
    }
  }
  return { isTranscribing, error, startTranscription };
}

export default function App() {
  const [input, setInput] = useState("");
  const [persona, setPersona] = useState<string | null>(null);
  const [starterGroup, setStarterGroup] = useState<StarterGroup>("Operations");
  const [theme, setTheme] = useState<ThemeValue>(() => {
    const stored =
      typeof window === "undefined"
        ? null
        : window.localStorage.getItem("chat-ui-theme");
    return stored && isTheme(stored) ? stored : "deep-ocean";
  });
  const {
    messages,
    token,
    setToken,
    isSending,
    submitMessage,
    cancelCurrentQuery,
    clearConversation,
    updateApproval,
    initialMessageId,
  } = useChatSession(persona);
  const {
    isTranscribing,
    error: transcriptionError,
    startTranscription,
  } = useTranscription(input, isSending, setInput);
  const chatLogRef = useRef<HTMLElement>(null);
  const enabledGroups = useMemo(
    () => (persona ? (PERSONA_STARTER_GROUPS[persona] ?? []) : []),
    [persona],
  );
  const visibleStarters = useMemo(
    () => STARTERS.filter((starter) => starter.group === starterGroup),
    [starterGroup],
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("chat-ui-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!enabledGroups.includes(starterGroup))
      setStarterGroup(enabledGroups[0] ?? "Operations");
  }, [enabledGroups, starterGroup]);
  useEffect(() => {
    const log = chatLogRef.current;
    if (log)
      log.scrollTop =
        messages.length === 1 && messages[0].id === initialMessageId
          ? 0
          : log.scrollHeight;
  }, [messages, initialMessageId]);
  function sendInput() {
    const value = input;
    setInput("");
    void submitMessage(value);
  }
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendInput();
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
            aria-label="Persona"
            value={persona ?? ""}
            onChange={(event) => setPersona(event.target.value || null)}
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
            aria-label="Background"
            value={theme}
            onChange={(event) => {
              if (isTheme(event.target.value)) setTheme(event.target.value);
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
              disabled={!enabledGroups.includes(group)}
            >
              {group}
            </button>
          ))}
        </div>
        <div className="starters">
          {visibleStarters.map((starter) => (
            <button
              key={starter.text}
              type="button"
              onClick={() => void submitMessage(starter.text)}
              disabled={isSending || !enabledGroups.includes(starter.group)}
            >
              {starter.text}
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
          <ChatMessage
            key={message.id}
            message={message}
            token={token}
            onDecision={updateApproval}
          />
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
              if (!isSending && input.trim()) sendInput();
            }
          }}
          rows={2}
          placeholder="Ask a question or run /token commands"
        />
        <button
          className="transcribe-button"
          type="button"
          aria-label={
            isTranscribing
              ? "Listening for speaker input"
              : "Transcribe from microphone"
          }
          aria-pressed={isTranscribing}
          disabled={isSending || isTranscribing}
          onClick={startTranscription}
          title="Transcribe from microphone"
        >
          <span aria-hidden="true">🎤</span>
        </button>
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
        {transcriptionError ? (
          <span className="transcription-error" role="alert">
            {transcriptionError}
          </span>
        ) : null}
      </form>
    </div>
  );
}
