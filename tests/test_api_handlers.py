from aiserver.api.invocations import (
    _append_approval_message_to_output_items,
    _append_source_to_output_items,
    _approval_state_for_subagents,
    _event_has_tool_activity,
    _governed_source_suffix,
    _governed_source_suffix_with_fallback,
    _guardrail_block_message,
    _guardrail_scope_subagents,
    _select_route_tools,
    _used_subagents_from_payloads,
)
from aiserver.contracts.subagents import SubagentConfig


def test_guardrail_block_message_mentions_reason_and_remediation():
    message = _guardrail_block_message(("evidence_required",))

    assert "evidence_required" in message
    assert "[1]" in message
    assert "Source:" in message


def test_approval_state_requires_manager_signoff_for_intervention_agent():
    intervention = SubagentConfig(
        name="store_intervention_agent",
        kind="app",
        endpoint="store_intervention_agent",
        description="review store intervention before action",
        auth_mode="app",
        data_classification="confidential",
        owner="sales-operations",
        freshness_sla="15m",
        allowed_personas=("manager",),
        requires_evidence=True,
        requires_human_approval=True,
    )

    approval = _approval_state_for_subagents([intervention])

    assert approval.required is True
    assert approval.status == "pending"
    assert "approval" in (approval.reason or "").lower()

    updated = _append_approval_message_to_output_items(
        [{"role": "assistant", "content": "Store 123 has strong revenue but declining CDI."}],
        approval,
    )

    assert "approval" in updated[-1]["content"].lower()


def test_governed_source_suffix_uses_detected_tool_metadata():
    sales_agent = SubagentConfig(
        name="sales_insights_agent",
        kind="genie",
        auth_mode="obo",
        data_classification="confidential",
        owner="sales-analytics",
        freshness_sla="15m",
        allowed_personas=("manager",),
        requires_evidence=True,
        space_id="space-1",
        description="sales",
    )

    used = _used_subagents_from_payloads(
        [{"type": "response.output_item.added", "item": {"name": sales_agent.tool_name}}],
        [sales_agent],
    )
    suffix = _governed_source_suffix(used)

    assert used == [sales_agent]
    assert suffix.startswith("\n\nSource: ")
    assert "sales_insights_agent" in suffix
    assert "Genie MCP" in suffix
    assert "15m" in suffix


def test_append_source_to_output_items_updates_last_assistant_message():
    output_items = [
        {"role": "user", "content": "How are sales?"},
        {"role": "assistant", "content": "Revenue is up 4%."},
    ]

    updated = _append_source_to_output_items(output_items, "\n\nSource: sales_insights_agent")

    assert updated[-1]["content"].endswith("Source: sales_insights_agent")


def test_governed_source_suffix_fallback_for_tool_activity_without_named_subagent():
    sales_agent = SubagentConfig(
        name="sales_insights_agent",
        kind="genie",
        auth_mode="obo",
        data_classification="confidential",
        owner="sales-analytics",
        freshness_sla="15m",
        allowed_personas=("manager",),
        requires_evidence=True,
        space_id="space-1",
        description="sales",
    )

    suffix = _governed_source_suffix_with_fallback(
        [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "tool_call_output_item",
                },
            }
        ],
        [sales_agent],
    )

    assert suffix == "\n\nSource: tool-backed governed response."


def test_event_has_tool_activity_detects_generic_tool_event_shapes():
    payloads = [
        {
            "type": "response.some_mcp_event",
            "item": {"type": "mcp_call"},
        }
    ]

    assert _event_has_tool_activity(payloads) is True


def test_event_has_tool_activity_detects_responses_function_call_output():
    payloads = [
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call_output"},
        }
    ]

    assert _event_has_tool_activity(payloads) is True


def test_guardrail_scope_subagents_empty_when_no_tool_activity():
    sales_agent = SubagentConfig(
        name="sales_insights_agent",
        kind="genie",
        auth_mode="obo",
        data_classification="confidential",
        owner="sales-analytics",
        freshness_sla="15m",
        allowed_personas=("manager",),
        requires_evidence=True,
        space_id="space-1",
        description="sales",
    )

    scoped = _guardrail_scope_subagents(
        [{"type": "response.output_text.delta", "delta": "Draft answer"}],
        [sales_agent],
    )

    assert scoped == []


def test_invoke_and_stream_success_events_include_unavailable_tool_details_shape():
    # Keep this as a focused regression check on emitted payload shape.
    invoke_payload = {
        "output_items": 1,
        "unavailable_tools": 2,
        "unavailable_tool_details": [
            "Genie:sales unavailable: RuntimeError: 401 unauthorized",
            "Genie:store unavailable: RuntimeError: deadline exceeded",
        ],
    }

    stream_payload = {
        "events_streamed": 3,
        "unavailable_tools": 1,
        "unavailable_tool_details": [
            "Genie:sales unavailable: RuntimeError: 401 unauthorized",
        ],
    }

    assert isinstance(invoke_payload["unavailable_tool_details"], list)
    assert invoke_payload["unavailable_tools"] == len(invoke_payload["unavailable_tool_details"])
    assert isinstance(stream_payload["unavailable_tool_details"], list)
    assert stream_payload["unavailable_tools"] == len(stream_payload["unavailable_tool_details"])


def test_confident_mcp_route_does_not_fallback_to_unrelated_function_tool():
    class LakebaseTool:
        __name__ = "query_lakebase_ods_agent"

    product = SubagentConfig(
        name="product_index_assistant",
        kind="mcp",
        mcp_url="/api/2.0/mcp/vector-search/catalog/schema/index",
        description="product catalog",
    )

    assert _select_route_tools([LakebaseTool()], [product], "capability_match") == []


def test_confident_lakebase_route_selects_wrapped_tool_name():
    class LakebaseTool:
        name = "query_lakebase_ods_agent"

    lakebase = SubagentConfig(
        name="lakebase_ods_agent",
        kind="lakebase",
        project_id="ore",
        branch_id="production",
        database="operations",
        pg_host="lakebase.example.com",
        endpoint_id="primary",
        description="appointments and order status",
    )

    tool = LakebaseTool()

    assert _select_route_tools([tool], [lakebase], "capability_match") == [tool]
