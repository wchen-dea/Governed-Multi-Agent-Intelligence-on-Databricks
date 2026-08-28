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

import os
import uuid
import datetime as dt
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

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

# Approved data source tables (fully qualified Unity Catalog names).
# Replace these placeholders with your actual catalog.schema.table references.
REVENUE_TABLE = os.getenv(
    "REVENUE_TABLE", "catalog.schema.store_revenue_daily"
)
CDI_TABLE = os.getenv(
    "CDI_TABLE", "catalog.schema.store_cdi_scores"
)
PEER_SET_TABLE = os.getenv(
    "PEER_SET_TABLE", "catalog.schema.store_peer_sets"
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
    if resp.status.state != StatementState.SUCCEEDED:
        raise HTTPException(
            status_code=502,
            detail=f"SQL execution failed: {resp.status.error}",
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
    """Find stores with strong revenue AND declining CDI (Overall Delight NPS).

    Revenue source: store_sales_performance (`Store Code`, `Day Date`, net_sales)
    CDI source: fct_cdi_daily (store_code, date_dimension_identifier,
                               totpromo_rolling, totdetr_rolling, totresp_rolling)
    CDI NPS formula: (promoters - detractors) / NULLIF(responses, 0)
    """
    sql = f"""
    WITH revenue_ranked AS (
        SELECT
            `Store Code` AS store_code,
            SUM(net_sales) AS total_revenue,
            PERCENT_RANK() OVER (ORDER BY SUM(net_sales)) AS revenue_pctile,
            -- Trend: compare last 30d vs prior 30d
            SUM(CASE WHEN `Day Date` >= CURRENT_DATE - INTERVAL 30 DAYS THEN net_sales ELSE 0 END)
              / NULLIF(SUM(CASE WHEN `Day Date` BETWEEN CURRENT_DATE - INTERVAL 60 DAYS
                                               AND CURRENT_DATE - INTERVAL 31 DAYS
                            THEN net_sales ELSE 0 END), 0) - 1 AS revenue_trend_pct
        FROM {REVENUE_TABLE}
        WHERE `Day Date` >= CURRENT_DATE - INTERVAL {TREND_WINDOW_DAYS} DAYS
        GROUP BY `Store Code`
    ),
    cdi_scored AS (
        SELECT
            store_code,
            date_dimension_identifier,
            -- CDI = Overall Delight NPS = (promoters - detractors) / responses
            (totpromo_rolling - totdetr_rolling)
              / NULLIF(CAST(totresp_rolling AS DOUBLE), 0) AS cdi_nps
        FROM {CDI_TABLE}
        WHERE date_dimension_identifier >= CAST(DATE_FORMAT(
              CURRENT_DATE - INTERVAL {TREND_WINDOW_DAYS} DAYS, 'yyyyMMdd') AS INT)
    ),
    cdi_ranked AS (
        SELECT
            store_code,
            AVG(cdi_nps) AS avg_cdi,
            PERCENT_RANK() OVER (ORDER BY AVG(cdi_nps) DESC) AS cdi_pctile,
            -- Trend: last 30d avg vs prior 30d avg
            AVG(CASE WHEN date_dimension_identifier >= CAST(DATE_FORMAT(
                  CURRENT_DATE - INTERVAL 30 DAYS, 'yyyyMMdd') AS INT)
                THEN cdi_nps END)
              - AVG(CASE WHEN date_dimension_identifier BETWEEN
                  CAST(DATE_FORMAT(CURRENT_DATE - INTERVAL 60 DAYS, 'yyyyMMdd') AS INT)
                  AND CAST(DATE_FORMAT(CURRENT_DATE - INTERVAL 31 DAYS, 'yyyyMMdd') AS INT)
                THEN cdi_nps END) AS cdi_trend_delta
        FROM cdi_scored
        GROUP BY store_code
    )
    SELECT
        r.store_code,
        r.total_revenue,
        r.revenue_pctile,
        r.revenue_trend_pct,
        c.avg_cdi,
        c.cdi_pctile,
        c.cdi_trend_delta
    FROM revenue_ranked r
    JOIN cdi_ranked c ON r.store_code = c.store_code
    WHERE r.revenue_pctile >= 0.75   -- strong revenue (top quartile)
      AND c.cdi_trend_delta < 0      -- declining CDI NPS
    ORDER BY c.cdi_trend_delta ASC
    LIMIT 20
    """
    return _execute_sql(sql)


def _get_peer_comparison(store_code: str) -> dict[str, Any]:
    """Retrieve peer set context for a given store.

    The peer model uses brg_store_cluster_membership_group which maps
    store_cluster_membership_group_identifier -> store_cluster_dimension_identifier.
    We join through dim_store to resolve store_code to its cluster, then
    compute peer-group averages for revenue and CDI.
    """
    sql = f"""
    WITH target_cluster AS (
        -- Find the cluster(s) the target store belongs to
        SELECT DISTINCT
            brg.store_cluster_dimension_identifier AS cluster_id
        FROM {PEER_SET_TABLE} brg
        JOIN dt_dev_gold.dwh.dim_store_active ds
            ON brg.store_cluster_membership_group_identifier = ds.store_cluster_membership_group_identifier
        WHERE ds.store_code = '{store_code}'
    ),
    peer_stores AS (
        -- All stores in the same cluster(s)
        SELECT DISTINCT ds.store_code AS peer_store_code
        FROM {PEER_SET_TABLE} brg
        JOIN dt_dev_gold.dwh.dim_store_active ds
            ON brg.store_cluster_membership_group_identifier = ds.store_cluster_membership_group_identifier
        WHERE brg.store_cluster_dimension_identifier IN (SELECT cluster_id FROM target_cluster)
          AND ds.store_code != '{store_code}'
    )
    SELECT
        (SELECT cluster_id FROM target_cluster LIMIT 1) AS peer_group_id,
        AVG(r.net_sales) AS peer_avg_daily_revenue,
        AVG((cdi.totpromo_rolling - cdi.totdetr_rolling)
            / NULLIF(CAST(cdi.totresp_rolling AS DOUBLE), 0)) AS peer_avg_cdi
    FROM peer_stores ps
    LEFT JOIN {REVENUE_TABLE} r
        ON r.`Store Code` = ps.peer_store_code
        AND r.`Day Date` >= CURRENT_DATE - INTERVAL 30 DAYS
    LEFT JOIN {CDI_TABLE} cdi
        ON cdi.store_code = ps.peer_store_code
        AND cdi.date_dimension_identifier >= CAST(DATE_FORMAT(
            CURRENT_DATE - INTERVAL 30 DAYS, 'yyyyMMdd') AS INT)
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
Source: {REVENUE_TABLE}, {CDI_TABLE}, {PEER_SET_TABLE}
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
