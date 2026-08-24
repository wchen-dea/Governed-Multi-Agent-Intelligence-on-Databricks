#!/usr/bin/env python3
"""Create a materialized view from vw_cdi_metrics and set up a Genie Agent space for CDI analytics.

Usage:
    uv run assistant-setup-cdi [--profile PROFILE]
"""

import argparse
import importlib
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=True)

SOURCE_VIEW = "quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view"
CATALOG = "quickstart_catalog"
SCHEMA = "multi_agent_schema"
MV_NAME = "quickstart_catalog.multi_agent_schema.fct_cdi_trusted_expert_score_metric_view"


def _get_warehouse_id(w: WorkspaceClient) -> str:
    warehouses = list(w.warehouses.list())
    if not warehouses:
        print("ERROR: No SQL warehouse found.", file=sys.stderr)
        sys.exit(1)
    return warehouses[0].id


def _execute_sql(w: WorkspaceClient, wh_id: str, stmt: str) -> None:
    """Execute a SQL statement, polling until completion."""
    result = w.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=stmt.strip(),
        wait_timeout="0s",
    )
    stmt_id = result.statement_id
    state = result.status.state.value if result.status and result.status.state else "PENDING"

    for _ in range(60):
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            break
        time.sleep(5)
        r = w.statement_execution.get_statement(stmt_id)
        state = r.status.state.value if r.status and r.status.state else "PENDING"

    if state == "FAILED":
        r = w.statement_execution.get_statement(stmt_id)
        print(f"  SQL failed: {r.status.error}", file=sys.stderr)
        sys.exit(1)
    elif state != "SUCCEEDED":
        print(f"  SQL did not complete (state={state})", file=sys.stderr)
        sys.exit(1)


def _ensure_materialized_view(w: WorkspaceClient, wh_id: str) -> None:
    print(f"\n→ Creating materialized view {MV_NAME} from {SOURCE_VIEW} …")


def _ensure_materialized_view(w: WorkspaceClient, wh_id: str) -> None:
    """Verify the materialized view exists."""
    print(f"\n→ Verifying materialized view {MV_NAME} exists …")
    try:
        w.tables.get(MV_NAME)
        print(f"  Materialized view {MV_NAME} confirmed.")
    except Exception as exc:
        print(f"  ERROR: {MV_NAME} not found: {exc}", file=sys.stderr)
        sys.exit(1)


def _refresh_materialized_view(w: WorkspaceClient, wh_id: str) -> None:
    print(f"\n→ Refreshing materialized view {MV_NAME} …")
    _execute_sql(w, wh_id, f"REFRESH MATERIALIZED VIEW {MV_NAME}")
    print(f"  Materialized view {MV_NAME} refreshed.")


def _create_genie_space(w: WorkspaceClient, wh_id: str) -> str | None:
    """Attempt to create a Genie Agent space over the MV."""
    try:
        importlib.import_module("databricks.sdk.service.dashboards")
    except ImportError:
        return None

    try:
        space = w.genie.create_space(
            title="CDI Metrics Agent",
            description="Customer Delight Indicator metrics — promoter, detractor, and response counts across rolling and non-rolling periods.",
            warehouse_id=wh_id,
            table_identifiers=[MV_NAME],
        )
        return space.space_id
    except Exception as exc:
        print(f"  Could not auto-create Genie space: {exc}", file=sys.stderr)
        print(
            "  Create one manually in the Databricks UI and update the subagent config.",
            file=sys.stderr,
        )
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up CDI Agent (materialized view + Genie)")
    parser.add_argument("--profile", default=None, help="Databricks CLI profile")
    args = parser.parse_args()

    kwargs = {}
    if args.profile:
        kwargs["profile"] = args.profile
    w = WorkspaceClient(**kwargs)
    wh_id = _get_warehouse_id(w)

    print("Setting up CDI Agent …")
    _ensure_materialized_view(w, wh_id)

    space_id = _create_genie_space(w, wh_id)

    print("\n--- Setup complete ---")
    print(f"  Materialized view: {MV_NAME}")
    if space_id:
        print(f"  Genie space ID: {space_id}")
        print(f"  Update subagents.<target>.json with space_id: {space_id}")
    else:
        print("  Next step: Create a Genie Agent space in the Databricks UI using")
        print(
            f"    table {MV_NAME}, then update the cdi_agent space_id in subagents.<target>.json."
        )


if __name__ == "__main__":
    main()
