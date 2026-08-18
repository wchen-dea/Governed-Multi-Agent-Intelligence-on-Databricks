import type { FrontendSettings } from "./types";

function parseAllowedPersonas(raw: string | undefined): string[] {
  if (!raw) {
    return ["manager", "analyst", "operator", "engineer", "executive"];
  }
  const values = raw
    .split(",")
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
  return [...new Set(values.length ? values : ["manager", "analyst", "operator", "engineer", "executive"])];
}

export const settings: FrontendSettings = {
  backendUrl: import.meta.env.VITE_API_PROXY ?? "/invocations",
  chatGreeting: import.meta.env.VITE_CHAT_GREETING ?? "What would you like to know?",
  timeoutSeconds: Number(import.meta.env.VITE_CHAT_PROXY_TIMEOUT_SECONDS ?? "300"),
  companyName: import.meta.env.VITE_CHAT_COMPANY_NAME ?? "Discount Tire",
  companyTagline: import.meta.env.VITE_CHAT_COMPANY_TAGLINE ?? "Enterprise AI Assistant",
  forwardedAccessTokenHeader:
    import.meta.env.VITE_FORWARDED_ACCESS_TOKEN_HEADER ?? "x-forwarded-access-token",
  setTokenCommand: "/token",
  clearTokenCommand: "/clear-token",
  setPersonaCommand: "/persona",
  clearPersonaCommand: "/clear-persona",
  allowedPersonas: parseAllowedPersonas(import.meta.env.VITE_CHAT_ALLOWED_PERSONAS),
};