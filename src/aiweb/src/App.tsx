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
// One tab per governed agent, plus one cross-agent tab per persona whose
// questions span several of that persona's agents (backend `composite_match`
// routing via contract routing_keywords). Each tab is enabled only for the
// persona that owns it in src/aiserver/contracts/subagents.<target>.json.
type StarterGroup =
  | "Sales Insights"
  | "CDI Metrics"
  | "Store Intervention"
  | "Exec Cross-Agent"
  | "Product Index"
  | "Lakebase ODS"
  | "Store Cross-Agent"
  | "Flink Support";
const STARTER_GROUPS: { group: StarterGroup; persona: string }[] = [
  { group: "Sales Insights", persona: "executive" },
  { group: "CDI Metrics", persona: "executive" },
  { group: "Store Intervention", persona: "executive" },
  { group: "Exec Cross-Agent", persona: "executive" },
  { group: "Product Index", persona: "store-manager" },
  { group: "Lakebase ODS", persona: "store-manager" },
  { group: "Store Cross-Agent", persona: "store-manager" },
  { group: "Flink Support", persona: "de-support" },
];
const STARTERS: { group: StarterGroup; text: string }[] = [
  {
    group: "Sales Insights",
    text: "Which 10 stores had the highest total net sales over the last 30 days? Include Store Code, region, total net sales, and total units, and state the exact date range.",
  },
  {
    group: "Sales Insights",
    text: "Compare month-to-date total net sales and units by region against the same period last year using day-over-day logic. Which regions grew or declined the most?",
  },
  {
    group: "CDI Metrics",
    text: "For the most recent week, which 10 stores have the lowest rolling Overall Delight NPS? Include Store Code, promoter, detractor, and response counts.",
  },
  {
    group: "CDI Metrics",
    text: "For last month, which regions had the highest share of customers waiting more than 45 minutes, and how does that compare with their Time NPS?",
  },
  {
    group: "Store Intervention",
    text: "Find stores with strong revenue but declining CDI scores, compare each store with its peers and recent trend, prepare an evidence-backed customer-experience intervention packet, and pause for manager approval before any operational dispatch.",
  },
  {
    group: "Store Intervention",
    text: "Which top-quartile revenue stores show the steepest CDI decline over the last 90 days? Compare each with its peer group's average daily revenue and CDI.",
  },
  {
    group: "Exec Cross-Agent",
    text: "Which of the top 20 stores by total net sales over the last 30 days have a rolling Overall Delight NPS below the company average? Show Store Code, net sales, NPS, and promoter/detractor counts.",
  },
  {
    group: "Exec Cross-Agent",
    text: "For each region, compare the month-over-month change in net sales with the change in Time NPS and the share of customers waiting more than 45 minutes. Where is sales growth coming with worse wait times?",
  },
  {
    group: "Exec Cross-Agent",
    text: "Find stores with top-quartile revenue but declining CDI, confirm their last-30-day net sales and weekly NPS trend, and prepare an intervention packet for approval.",
  },
  {
    group: "Product Index",
    text: "Look up product_code '000000000000019887' and return product_description, brand_code, and article_type.",
  },
  {
    group: "Product Index",
    text: "Find Cooper CS5 Ultra Touring tires in size 225/60R18 and list their product codes and descriptions.",
  },
  {
    group: "Lakebase ODS",
    text: "List the next 20 Scheduled or Confirmed appointments with Store Code, site name, order type, and scheduled start time.",
  },
  {
    group: "Lakebase ODS",
    text: "What are the top 5 stores by appointment count in the most recent 30 days of appointment data? Include Store Code, site name, and the missed and canceled rate.",
  },
  {
    group: "Store Cross-Agent",
    text: "Find Cooper CS5 Ultra Touring tires in 225/60R18, then check each product code's lifecycle status in the operational article data. Which ones are discontinued or end-of-life?",
  },
  {
    group: "Store Cross-Agent",
    text: "Look up product_code '000000000000019887', then list active alternatives from the same brand in the operational article data.",
  },
  {
    group: "Store Cross-Agent",
    text: "Which stores have the most Scheduled or Confirmed appointments this week, and how many active Store Managers and Tire Technicians does each have?",
  },
  {
    group: "Flink Support",
    text: "Flink streaming job has increasing consumer lag. What are the common causes and how do we fix it?",
  },
  {
    group: "Flink Support",
    text: "Which Flink alarms and thresholds does ORE monitor for backpressure and checkpoint failures, and what does the Kafka/Flink operations runbook say to check first?",
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
  const [starterGroup, setStarterGroup] =
    useState<StarterGroup>("Sales Insights");
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
    () =>
      STARTER_GROUPS.filter((item) => item.persona === persona).map(
        (item) => item.group,
      ),
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
    if (enabledGroups.length && !enabledGroups.includes(starterGroup))
      setStarterGroup(enabledGroups[0]);
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
          {STARTER_GROUPS.map(({ group, persona: owner }) => (
            <button
              key={group}
              type="button"
              className={starterGroup === group ? "active" : ""}
              onClick={() => setStarterGroup(group)}
              disabled={!enabledGroups.includes(group)}
              title={`Persona: ${owner}`}
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
