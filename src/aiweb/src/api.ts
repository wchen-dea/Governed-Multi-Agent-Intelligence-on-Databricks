import { settings } from "./config";
import {
  governanceFromHints,
  sourceBadgeLine,
  updateStreamHints,
} from "./stream";
import type {
  ChatMessage,
  HumanApprovalState,
  OpenAIAgentRunMetadata,
} from "./types";
import type { GovernanceMetadata } from "./types";

export interface SendChatOptions {
  history: ChatMessage[];
  userMessage: string;
  conversationId: string;
  persona: string | null;
  token: string | null;
}

export interface SendChatResult {
  content: string;
  streamedText: boolean;
  metadata: GovernanceMetadata;
}

export interface StreamCallbacks {
  onTextDelta?: (delta: string) => void;
  onMetadata?: (metadata: GovernanceMetadata) => void;
  onRequestController?: (controller: AbortController | null) => void;
}

function metadataFromEvent(
  event: Record<string, unknown>,
  fallback: GovernanceMetadata,
): GovernanceMetadata {
  const envelope = (event.response_envelope ?? event.governance) as
    Record<string, unknown> | undefined;
  if (!envelope || typeof envelope !== "object") return fallback;
  const openaiRun = envelope.openai_run;
  return {
    ...fallback,
    guardrailReasons: Array.isArray(envelope.guardrail_reasons)
      ? envelope.guardrail_reasons.filter(
          (item): item is string => typeof item === "string",
        )
      : fallback.guardrailReasons,
    truncated: envelope.truncated === true,
    status:
      typeof envelope.status === "string" ? envelope.status : fallback.status,
    approvalState:
      envelope.approval_state && typeof envelope.approval_state === "object"
        ? (envelope.approval_state as HumanApprovalState)
        : fallback.approvalState,
    openaiRun:
      openaiRun && typeof openaiRun === "object"
        ? (openaiRun as OpenAIAgentRunMetadata)
        : fallback.openaiRun,
  };
}

export async function submitApprovalDecision(options: {
  requestId: string;
  agentName: string;
  approver: string;
  decision: "approved" | "rejected" | "more_info_requested";
  reason: string;
  notes: string;
  token: string | null;
}): Promise<HumanApprovalState> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options.token)
    headers[settings.forwardedAccessTokenHeader] = options.token;
  const response = await fetch(
    `${settings.backendUrl.replace(/\/invocations\/?$/, "")}/approval-decisions`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        request_id: options.requestId,
        agent_name: options.agentName,
        approver: options.approver,
        decision: options.decision,
        reason: options.reason,
        notes: options.notes,
      }),
    },
  );
  if (!response.ok)
    throw new Error(`Approval decision failed (HTTP ${response.status}).`);
  const payload = (await response.json()) as {
    approval?: Record<string, unknown>;
    delegation?: Record<string, unknown> | null;
  };
  const approval = payload.approval;
  if (!approval)
    throw new Error("Approval response did not include a decision.");
  return {
    status: approval.status as HumanApprovalState["status"],
    required: false,
    approver: typeof approval.approver === "string" ? approval.approver : null,
    decision: typeof approval.decision === "string" ? approval.decision : null,
    reason: typeof approval.reason === "string" ? approval.reason : null,
    delegation:
      payload.delegation && typeof payload.delegation.task_id === "string"
        ? {
            task_id: payload.delegation.task_id,
            correlation_id:
              typeof payload.delegation.correlation_id === "string"
                ? payload.delegation.correlation_id
                : undefined,
            source_agent:
              typeof payload.delegation.source_agent === "string"
                ? payload.delegation.source_agent
                : undefined,
            target_agent:
              typeof payload.delegation.target_agent === "string"
                ? payload.delegation.target_agent
                : undefined,
            intent:
              typeof payload.delegation.intent === "string"
                ? payload.delegation.intent
                : undefined,
            status:
              typeof payload.delegation.status === "string"
                ? payload.delegation.status
                : undefined,
            failure_code:
              typeof payload.delegation.failure_code === "string"
                ? payload.delegation.failure_code
                : null,
            completed: payload.delegation.completed === true,
          }
        : null,
  };
}

export function sessionStatusLine(
  persona: string | null,
  hasToken: boolean,
): string {
  const personaLabel = persona ?? "not set";
  const authMode = hasToken ? "hybrid (app + OBO token)" : "app-only";
  return `\n\n---\nSession: persona=\`${personaLabel}\` | auth=\`${authMode}\``;
}

export async function sendChat(
  options: SendChatOptions,
  callbacks: StreamCallbacks = {},
): Promise<SendChatResult> {
  const payloadInput = [
    ...options.history.map((m) => ({ role: m.role, content: m.content })),
    { role: "user", content: options.userMessage },
  ];

  const payload: Record<string, unknown> = {
    input: payloadInput,
    stream: true,
    context: { conversation_id: options.conversationId },
  };
  if (options.persona) {
    payload.custom_inputs = { persona: options.persona };
  }

  const controller = new AbortController();
  callbacks.onRequestController?.(controller);
  const timeout = setTimeout(
    () => controller.abort(),
    settings.timeoutSeconds * 1000,
  );

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options.token) {
    headers[settings.forwardedAccessTokenHeader] = options.token;
  }

  try {
    const response = await fetch(settings.backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      const details = (await response.text()).trim();
      const suffix = details ? ` Details: ${details.slice(0, 300)}` : "";
      throw new Error(
        `The backend is unavailable (HTTP ${response.status}). Please retry in a moment.${suffix}`,
      );
    }

    if (!response.body) {
      throw new Error("Backend response has no stream body.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    let fullText = "";
    let streamedText = false;
    const categories = new Set<string>();
    const tools = new Set<string>();
    const seenEvents = new Set<string>();

    let latestMetadata = governanceFromHints({ categories, tools });
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line.startsWith("data: ")) {
          continue;
        }

        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          break;
        }

        let event: Record<string, unknown>;
        try {
          event = JSON.parse(data) as Record<string, unknown>;
        } catch {
          continue;
        }

        const eventKey = JSON.stringify(event);
        if (seenEvents.has(eventKey)) {
          continue;
        }
        seenEvents.add(eventKey);

        const delta = updateStreamHints(event, { categories, tools });
        if (delta) {
          if (fullText.endsWith(delta)) {
            continue;
          }
          streamedText = true;
          fullText += delta;
          callbacks.onTextDelta?.(delta);
        }
        latestMetadata = metadataFromEvent(
          event,
          governanceFromHints({ categories, tools }),
        );
        callbacks.onMetadata?.(latestMetadata);
      }
    }

    if (!streamedText) {
      return {
        streamedText: false,
        content:
          "The backend ended the stream without returning visible content. This often means the response was blocked before it could be shown, for example by an `evidence_required` guardrail." +
          sessionStatusLine(options.persona, Boolean(options.token)),
        metadata: {
          ...latestMetadata,
          status: latestMetadata.status ?? "blocked",
        },
      };
    }

    const badge = sourceBadgeLine(categories, tools);
    if (badge) {
      fullText += badge;
    }
    fullText += sessionStatusLine(options.persona, Boolean(options.token));

    return { content: fullText, streamedText: true, metadata: latestMetadata };
  } finally {
    clearTimeout(timeout);
    callbacks.onRequestController?.(null);
  }
}
