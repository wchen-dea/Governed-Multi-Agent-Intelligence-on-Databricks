"""store-intervention-agent

A Databricks App specialist that exposes a Responses API-compatible endpoint.
It discovers stores with strong revenue and declining CDI, compares each
candidate against an explicit peer set, and returns an evidence-backed packet.

Contract guarantees:
- Every response includes citation / Source: lines with freshness.
- Intervention language is proposals only.
- Stops at pending manager review; never performs operational dispatch.
- Does NOT accept model-text approval; authorization is external only.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = FastAPI(
    title="store-intervention-agent",
    description="Responses API-compatible specialist for store intervention discovery",
    version="0.1.0",
)

# The Databricks SDK auto-discovers DATABRICKS_HOST / DATABRICKS_TOKEN from
# the app environment (injected at runtime by the Apps platform).
w = WorkspaceClient()

# ---------------------------------------------------------------------------
# Configuration — data sources and warehouse
# ---------------------------------------------------------------------------

# The SQL warehouse ID used to execute analytical queries.
# Set via app environment or default to the first available serverless warehouse.
SQL_WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID", "")
APP_ENV = os.getenv("HITL_ENV", os.getenv("APP_ENV", "dev")).strip().lower() or "dev"


def _default_source_table(layer: str, schema: str, table: str) -> str:
    """Build the conventional environment-scoped UC source table name."""
    return f"dt_{APP_ENV}_{layer}.{schema}.{table}"

# The scheduled snapshot job owns access to the source tables. The App only
# needs SELECT on this single, curated Delta table.
SNAPSHOT_TABLE = os.getenv(
    "SNAPSHOT_TABLE",
    "quickstart_catalog.multi_agent_schema.hitl_source_snapshot",
)

# Rolling window for trend analysis (days)
TREND_WINDOW_DAYS = int(os.getenv("TREND_WINDOW_DAYS", "90"))

# ---------------------------------------------------------------------------
# Request / Response models (Responses API contract)
# ---------------------------------------------------------------------------


class ResponsesRequest(BaseModel):
    """Responses API-compatible input."""
    input: str | list[dict[str, Any]] = Field(..., description="User question or message list")
    model: str | None = Field(default=None, description="Ignored; specialist is fixed")
    instructions: str | None = Field(default=None)


class OutputItem(BaseModel):
    type: str = "message"
    role: str = "assistant"
    content: list[dict[str, Any]]


class ResponsesResponse(BaseModel):
    """Responses API-compatible output."""
    id: str
    object: str = "response"
    created_at: int
    output: list[OutputItem]
    # Convenience accessor used by orchestrator
    output_text: str = ""


# ---------------------------------------------------------------------------
# SQL execution helper
# ---------------------------------------------------------------------------


def _execute_sql(sql: str) -> list[dict[str, Any]]:
    """Execute a SQL statement via the Statement Execution API and return rows."""
    warehouse_id = SQL_WAREHOUSE_ID
    if not warehouse_id:
        warehouses = w.warehouses.list()
        for wh in warehouses:
            if wh.enable_serverless_compute:
                warehouse_id = wh.id
                break
        if not warehouse_id:
            raise HTTPException(
                status_code=503,
                detail="No SQL warehouse available. Set SQL_WAREHOUSE_ID.",
            )

    resp = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
    )
    if resp.status is None:
        raise HTTPException(
            status_code=502,
            detail="SQL execution did not return statement status.",
        )
    if resp.status.state != StatementState.SUCCEEDED:
        raise HTTPException(
            status_code=502,
            detail=f"SQL execution failed: {resp.status.error}",
        )

    if resp.manifest is None or resp.manifest.schema is None or resp.manifest.schema.columns is None:
        raise HTTPException(
            status_code=502,
            detail="SQL execution did not return result schema.",
        )

    columns = [col.name for col in resp.manifest.schema.columns]
    rows = []
    if resp.result and resp.result.data_array:
        for row in resp.result.data_array:
            rows.append(dict(zip(columns, row)))
    return rows


# ---------------------------------------------------------------------------
# Core logic — discovery, peer comparison, evidence packet
# ---------------------------------------------------------------------------


def _discover_candidates() -> list[dict[str, Any]]:
    """Find high-revenue stores with declining CDI from the curated snapshot."""
    sql = f"""
    SELECT store_code, total_revenue, revenue_pctile, revenue_trend_pct,
           avg_cdi, cdi_pctile, cdi_trend_delta
    FROM {SNAPSHOT_TABLE}
    WHERE revenue_pctile >= 0.75
      AND cdi_trend_delta < 0
    ORDER BY cdi_trend_delta ASC
    LIMIT 20
    """
    return _execute_sql(sql)


def _get_peer_comparison(store_code: str) -> dict[str, Any]:
    """Retrieve peer context from the curated snapshot."""
    sql = f"""
    SELECT
        peer_group_id, peer_avg_daily_revenue, peer_avg_cdi
    FROM {SNAPSHOT_TABLE}
    WHERE store_code = '{store_code}'
    """
    rows = _execute_sql(sql)
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Evidence packet formatter
# ---------------------------------------------------------------------------

APPROVAL_STATE = "Pending manager review — no dispatch performed."
NO_AUTH_NOTICE = (
    "This output does NOT constitute authorization. Approval is established "
    "only by the orchestrator's approval API and persisted approval record."
)


def _format_candidate_packet(
    candidate: dict[str, Any],
    peer: dict[str, Any],
    query_ts: str,
) -> str:
    """Format a single candidate store into the required evidence packet."""
    store_code = candidate["store_code"]
    revenue = candidate["total_revenue"]
    rev_pctile = candidate["revenue_pctile"]
    rev_trend = candidate.get("revenue_trend_pct") or 0
    cdi = candidate["avg_cdi"]
    cdi_pctile = candidate["cdi_pctile"]
    cdi_trend = candidate.get("cdi_trend_delta") or 0
    peer_group = peer.get("peer_group_id", "N/A")
    peer_avg_rev = peer.get("peer_avg_daily_revenue", "N/A")
    peer_avg_cdi = peer.get("peer_avg_cdi", "N/A")

    packet = f"""---
## Store Identity
Store Code: {store_code}
Display Label: Store {store_code}

## Revenue Signal
- Metric: Net Sales (rolling {TREND_WINDOW_DAYS}d)
- Period: Last {TREND_WINDOW_DAYS} days ending {query_ts[:10]}
- Value: ${float(revenue):,.2f}
- Peer Position: {float(rev_pctile)*100:.1f}th percentile
- Trend (30d vs prior 30d): {float(rev_trend)*100:+.1f}%
- Peer Group Avg Daily Net Sales: {peer_avg_rev}

## CDI Signal
- Dimension: Overall Delight NPS (rolling)
- Period: Last {TREND_WINDOW_DAYS} days ending {query_ts[:10]}
- Value: {float(cdi):.3f}
- Peer Position: {float(cdi_pctile)*100:.1f}th percentile (lower = worse)
- Trend (30d delta): {float(cdi_trend):+.4f} (declining)
- Peer Group Avg CDI NPS: {peer_avg_cdi}

## Materiality
Store {store_code} is in the top quartile for net sales (peer cluster: {peer_group}) \
but Overall Delight NPS has declined by {abs(float(cdi_trend)):.4f} points over the \
last 30 days. This divergence indicates the store is generating strong sales while \
customer delight is worsening — a pattern that historically precedes revenue churn \
if unaddressed.

## Evidence
Source: {REVENUE_TABLE}, {CDI_TABLE}, {PEER_SET_TABLE}, {STORE_DIMENSION_TABLE}
Query timestamp: {query_ts}
Data freshness: Within 24h of query execution (governed by source pipeline SLA)

## Proposal (NON-EXECUTING — proposals only)
- Option A: Targeted CDI coaching visit — scope: 1 store, 2-day engagement
  - Risk: Minimal operational disruption; cost = travel + 2 FTE-days
  - Success measure: CDI trend reversal within 30d post-intervention
- Option B: Peer-benchmarking workshop — scope: peer group, virtual half-day
  - Risk: Low; requires peer availability coordination
  - Success measure: CDI delta narrows to peer mean within 45d
- Option C: Root-cause diagnostic (mystery shop + survey burst)
  - Risk: 5-7 day lead time; cost = vendor engagement
  - Success measure: Actionable root cause identified and remediation plan filed

## Approval State
{APPROVAL_STATE}
{NO_AUTH_NOTICE}
---"""
    return packet


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.post("/responses", response_model=ResponsesResponse)
@app.post("/v1/responses", response_model=ResponsesResponse, include_in_schema=False)
async def create_response(req: ResponsesRequest) -> ResponsesResponse:
    """Responses API-compatible endpoint.

    Accepts a user question and returns output_text with evidence packets.
    """
    query_ts = dt.datetime.utcnow().isoformat() + "Z"
    if isinstance(req.input, str):
        user_question = req.input.strip()
    else:
        user_question = "\n".join(
            str(item.get("content", ""))
            for item in req.input
            if item.get("role") == "user"
        ).strip()
    user_input = user_question.lower()

    # --- Guard: reject any claim of approval in the input text ---
    approval_keywords = ["approved", "authorize", "execute intervention"]
    if any(kw in user_input for kw in approval_keywords):
        denial_text = (
            "DENIED: This specialist does not accept approval or dispatch "
            "instructions via model text. Authorization is established only "
            "by the orchestrator's approval API and the persisted approval "
            "record. No action has been taken.\n\n"
            f"Source: store-intervention-agent policy | {query_ts}"
        )
        return _build_response(denial_text, query_ts)

    # --- Discovery query (default behavior) ---
    try:
        candidates = _discover_candidates()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery query failed: {e}")

    if not candidates:
        no_results = (
            "No stores currently match the discovery criteria "
            "(top-quartile revenue with declining CDI trend).\n\n"
            f"Source: {REVENUE_TABLE}, {CDI_TABLE} | Query: {query_ts}"
        )
        return _build_response(no_results, query_ts)

    # Build evidence packets for each candidate
    packets: list[str] = []
    for candidate in candidates:
        try:
            peer = _get_peer_comparison(str(candidate["store_code"]))
        except Exception:
            peer = {}
        packets.append(_format_candidate_packet(candidate, peer, query_ts))

    header = (
        f"# Store Intervention Discovery Report\n"
        f"Generated: {query_ts}\n"
        f"Candidates found: {len(candidates)}\n"
        f"Criteria: Revenue >= 75th percentile AND CDI trending negative (30d)\n\n"
    )
    footer = (
        f"\n---\n"
        f"## Governance Notice\n"
        f"{APPROVAL_STATE}\n"
        f"{NO_AUTH_NOTICE}\n"
        f"Source: store-intervention-agent v0.1.0 | {query_ts}\n"
    )
    output_text = header + "\n".join(packets) + footer

    return _build_response(output_text, query_ts)


def _build_response(text: str, ts: str) -> ResponsesResponse:
    """Construct a Responses API-shaped response object."""
    return ResponsesResponse(
        id=f"resp_{uuid.uuid4().hex[:24]}",
        created_at=int(dt.datetime.utcnow().timestamp()),
        output=[
            OutputItem(
                content=[{"type": "output_text", "text": text}]
            )
        ],
        output_text=text,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "store-intervention-agent"}


@app.get("/")
def root():
    return {"message": "store-intervention-agent is running. POST to /v1/responses."}
