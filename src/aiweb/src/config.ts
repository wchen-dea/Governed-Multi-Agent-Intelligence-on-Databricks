import type { FrontendSettings } from "./types";

const DEFINED_AGENT_PERSONAS = ["store-manager", "executive", "de-support"];

const LEGACY_PERSONA_MAP: Record<string, string> = {
  manager: "store-manager",
  analyst: "store-manager",
  operator: "de-support",
  engineer: "de-support",
};

function parseAllowedPersonas(raw: string | undefined): string[] {
  if (!raw) {
    return DEFINED_AGENT_PERSONAS;
  }
  const mapped = raw
    .split(",")
    .map((v) => {
      const cleaned = v.trim().toLowerCase();
      return LEGACY_PERSONA_MAP[cleaned] ?? cleaned;
    })
    .filter((v) => DEFINED_AGENT_PERSONAS.includes(v));

  const result = [...new Set(mapped)];
  return result.length ? result : DEFINED_AGENT_PERSONAS;
}

export const settings: FrontendSettings = {
  backendUrl: import.meta.env.VITE_API_PROXY ?? "/invocations",
  chatGreeting:
    import.meta.env.VITE_CHAT_GREETING ?? "What would you like to know?",
  timeoutSeconds: Number(
    import.meta.env.VITE_CHAT_PROXY_TIMEOUT_SECONDS ?? "300",
  ),
  companyName: import.meta.env.VITE_CHAT_COMPANY_NAME ?? "Discount Tire",
  companyTagline:
    import.meta.env.VITE_CHAT_COMPANY_TAGLINE ?? "Enterprise AI Assistant",
  forwardedAccessTokenHeader:
    import.meta.env.VITE_FORWARDED_ACCESS_TOKEN_HEADER ??
    "x-forwarded-access-token",
  setTokenCommand: "/token",
  clearTokenCommand: "/clear-token",
  allowedPersonas: parseAllowedPersonas(
    import.meta.env.VITE_CHAT_ALLOWED_PERSONAS,
  ),
};
