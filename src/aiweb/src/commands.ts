export function parseTokenCommand(
  text: string,
  setTokenCommand: string,
  clearTokenCommand: string,
): { kind: "set" | "clear" | null; token: string | null } {
  const stripped = text.trim();
  if (stripped === clearTokenCommand) {
    return { kind: "clear", token: null };
  }
  if (!stripped.startsWith(`${setTokenCommand} `)) {
    return { kind: null, token: null };
  }
  const token = stripped.slice(setTokenCommand.length).trim();
  return { kind: "set", token };
}

export function parsePersonaCommand(
  text: string,
  setPersonaCommand: string,
  clearPersonaCommand: string,
): { kind: "set" | "clear" | null; persona: string | null } {
  const stripped = text.trim();
  if (stripped === clearPersonaCommand) {
    return { kind: "clear", persona: null };
  }
  if (!stripped.startsWith(`${setPersonaCommand} `)) {
    return { kind: null, persona: null };
  }
  const persona = stripped.slice(setPersonaCommand.length).trim();
  return { kind: "set", persona };
}

export function maskToken(token: string): string {
  const cleaned = token.trim();
  if (cleaned.length <= 10) {
    return "*".repeat(cleaned.length);
  }
  return `${cleaned.slice(0, 6)}...${cleaned.slice(-4)}`;
}
