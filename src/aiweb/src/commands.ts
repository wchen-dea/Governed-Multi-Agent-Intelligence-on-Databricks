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

export function maskToken(token: string): string {
  const cleaned = token.trim();
  if (cleaned.length <= 10) {
    return "*".repeat(cleaned.length);
  }
  return `${cleaned.slice(0, 6)}...${cleaned.slice(-4)}`;
}
