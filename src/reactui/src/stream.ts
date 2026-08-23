import type { GovernanceMetadata, StreamHints } from "./types";

export function formatToolLabel(toolName: string): string {
  if (toolName.startsWith("query_")) {
    return toolName.slice("query_".length).split("_").join(" ");
  }
  return toolName.split("_").join(" ");
}

export function updateStreamHints(event: Record<string, unknown>, hints: StreamHints): string {
  const eventType = typeof event.type === "string" ? event.type : "";

  let delta = "";
  if (eventType === "response.output_text.delta") {
    if (typeof event.delta === "string") {
      delta = event.delta;
    } else if (event.delta !== undefined && event.delta !== null) {
      delta = String(event.delta);
    }
  }

  const item = (event.item && typeof event.item === "object" ? event.item : null) as
    | Record<string, unknown>
    | null;
  const itemType = item && typeof item.type === "string" ? item.type : "";

  if (eventType.includes("mcp") || itemType.includes("mcp")) {
    hints.categories.add("Genie MCP");
  }

  if (eventType.startsWith("response.output_item") && itemType === "tool_call_output_item") {
    hints.categories.add("Tool Execution");
  }

  const candidates = [event.name, item?.name, item?.tool_name];
  for (const candidate of candidates) {
    if (typeof candidate !== "string") {
      continue;
    }
    const toolName = candidate.trim();
    if (!toolName) {
      continue;
    }
    hints.tools.add(toolName);
    if (toolName.startsWith("query_")) {
      hints.categories.add("Serving Endpoint Tool");
    } else {
      hints.categories.add("Function Tool");
    }
  }

  return delta;
}

export function sourceBadgeLine(categories: Set<string>, tools: Set<string>): string {
  if (categories.size === 0 && tools.size === 0) {
    return "";
  }

  const parts: string[] = [];
  if (categories.size > 0) {
    parts.push(`Sources used: ${Array.from(categories).sort().join(" | ")}`);
  }
  if (tools.size > 0) {
    const labels = Array.from(tools)
      .map((t) => formatToolLabel(t))
      .sort();
    parts.push(`Tools: ${labels.join(" | ")}`);
  }
  return `\n\n---\n${parts.join("\n")}`;
}

export function governanceFromHints(hints: StreamHints): GovernanceMetadata {
  return {
    tools: Array.from(hints.tools),
    sourceCategories: Array.from(hints.categories),
    guardrailReasons: [],
    unavailableTools: [],
    truncated: false,
  };
}