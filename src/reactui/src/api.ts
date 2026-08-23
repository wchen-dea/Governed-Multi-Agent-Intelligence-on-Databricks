import { settings } from "./config";
import { governanceFromHints, sourceBadgeLine, updateStreamHints } from "./stream";
import type { ChatMessage } from "./types";
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
}

function metadataFromEvent(event: Record<string, unknown>, fallback: GovernanceMetadata): GovernanceMetadata {
  const envelope = (event.response_envelope ?? event.governance) as Record<string, unknown> | undefined;
  if (!envelope || typeof envelope !== "object") return fallback;
  return {
    ...fallback,
    guardrailReasons: Array.isArray(envelope.guardrail_reasons) ? envelope.guardrail_reasons.filter((item): item is string => typeof item === "string") : fallback.guardrailReasons,
    truncated: envelope.truncated === true,
    status: typeof envelope.status === "string" ? envelope.status : fallback.status,
  };
}

export function sessionStatusLine(persona: string | null, hasToken: boolean): string {
  const personaLabel = persona ?? "not set";
  const authMode = hasToken ? "hybrid (app + OBO token)" : "app-only";
  return `\n\n---\nSession: persona=\`${personaLabel}\` | auth=\`${authMode}\``;
}

export async function sendChat(options: SendChatOptions, callbacks: StreamCallbacks = {}): Promise<SendChatResult> {
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
  const timeout = setTimeout(() => controller.abort(), settings.timeoutSeconds * 1000);

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
      throw new Error(`Backend returned HTTP ${response.status}.${suffix}`);
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

        const delta = updateStreamHints(event, { categories, tools });
        if (delta) {
          streamedText = true;
          fullText += delta;
          callbacks.onTextDelta?.(delta);
        }
        callbacks.onMetadata?.(metadataFromEvent(event, governanceFromHints({ categories, tools })));
      }
    }

    if (!streamedText) {
      return {
        streamedText: false,
        content:
          "The backend ended the stream without returning visible content. This often means the response was blocked before it could be shown, for example by an `evidence_required` guardrail." +
          sessionStatusLine(options.persona, Boolean(options.token)),
        metadata: { ...governanceFromHints({ categories, tools }), status: "blocked" },
      };
    }

    const badge = sourceBadgeLine(categories, tools);
    if (badge) {
      fullText += badge;
    }
    fullText += sessionStatusLine(options.persona, Boolean(options.token));

    return { content: fullText, streamedText: true, metadata: governanceFromHints({ categories, tools }) };
  } finally {
    clearTimeout(timeout);
  }
}