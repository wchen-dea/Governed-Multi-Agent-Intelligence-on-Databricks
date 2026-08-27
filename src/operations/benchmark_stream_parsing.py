#!/usr/bin/env python3
"""Micro-benchmark for frontend stream event parsing paths."""

from __future__ import annotations

from time import perf_counter

from frontend.app.stream_events import update_stream_hints


def _legacy_parse(event: dict[str, object]) -> tuple[str, set[str], set[str]]:
    """Reference parser matching prior temporary-set behavior."""
    categories: set[str] = set()
    tools: set[str] = set()

    event_type_raw = event.get("type")
    event_type = event_type_raw if isinstance(event_type_raw, str) else ""

    delta = ""
    if event_type == "response.output_text.delta":
        delta_raw = event.get("delta")
        if isinstance(delta_raw, str):
            delta = delta_raw
        elif delta_raw:
            delta = str(delta_raw)

    item_raw = event.get("item")
    item = item_raw if isinstance(item_raw, dict) else None
    item_type_raw = item.get("type") if item else ""
    item_type = item_type_raw if isinstance(item_type_raw, str) else ""

    if "mcp" in event_type or "mcp" in item_type:
        categories.add("Genie MCP")

    if event_type.startswith("response.output_item") and item_type == "tool_call_output_item":
        categories.add("Tool Execution")

    candidates = (
        event.get("name"),
        item.get("name") if item else None,
        item.get("tool_name") if item else None,
    )
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        tool_name = candidate.strip()
        if not tool_name:
            continue
        tools.add(tool_name)
        if tool_name.startswith("query_"):
            categories.add("Serving Endpoint Tool")
        else:
            categories.add("Function Tool")

    return delta, categories, tools


def _build_events(n: int) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for i in range(n):
        mod = i % 3
        if mod == 0:
            events.append(
                {
                    "type": "response.output_text.delta",
                    "delta": "token",
                    "item": {"type": "message"},
                }
            )
        elif mod == 1:
            events.append(
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "tool_call_output_item",
                        "name": "query_sales_agent",
                    },
                }
            )
        else:
            events.append(
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "mcp_result",
                        "tool_name": "genie_sales",
                    },
                }
            )
    return events


def _benchmark_legacy(events: list[dict[str, object]], loops: int) -> float:
    start = perf_counter()
    total = 0
    for _ in range(loops):
        all_categories: set[str] = set()
        all_tools: set[str] = set()
        for event in events:
            delta, categories, tools = _legacy_parse(event)
            if delta:
                total += len(delta)
            all_categories.update(categories)
            all_tools.update(tools)
        total += len(all_categories) + len(all_tools)
    elapsed = perf_counter() - start
    if total < 0:
        print(total)
    return elapsed


def _benchmark_optimized(events: list[dict[str, object]], loops: int) -> float:
    start = perf_counter()
    total = 0
    for _ in range(loops):
        all_categories: set[str] = set()
        all_tools: set[str] = set()
        for event in events:
            delta = update_stream_hints(event, all_categories, all_tools)
            if delta:
                total += len(delta)
        total += len(all_categories) + len(all_tools)
    elapsed = perf_counter() - start
    if total < 0:
        print(total)
    return elapsed


def main() -> None:
    events = _build_events(3000)
    loops = 200

    legacy_s = _benchmark_legacy(events, loops)
    optimized_s = _benchmark_optimized(events, loops)

    speedup = legacy_s / optimized_s if optimized_s else 0.0
    improvement = (1.0 - (optimized_s / legacy_s)) * 100.0 if legacy_s else 0.0

    print(f"events_per_run={len(events)} loops={loops}")
    print(f"legacy_seconds={legacy_s:.4f}")
    print(f"optimized_seconds={optimized_s:.4f}")
    print(f"speedup_x={speedup:.2f}")
    print(f"time_reduction_percent={improvement:.2f}")


if __name__ == "__main__":
    main()
