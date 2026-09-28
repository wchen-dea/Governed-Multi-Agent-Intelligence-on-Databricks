"""Refresh the governed HITL source snapshot as a single Delta table."""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revenue-table", required=True)
    parser.add_argument("--cdi-table", required=True)
    parser.add_argument("--peer-set-table", required=True)
    parser.add_argument("--store-dimension-table", required=True)
    parser.add_argument("--snapshot-table", required=True)
    parser.add_argument("--trend-window-days", type=int, default=90)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    days = args.trend_window_days
    snapshot_sql = f"""
    WITH revenue AS (
      SELECT `Store Code` AS store_code,
        SUM(net_sales) AS total_revenue,
        SUM(CASE WHEN `Day Date` >= CURRENT_DATE - INTERVAL 30 DAYS THEN net_sales ELSE 0 END)
          / NULLIF(SUM(CASE WHEN `Day Date` BETWEEN CURRENT_DATE - INTERVAL 60 DAYS
            AND CURRENT_DATE - INTERVAL 31 DAYS THEN net_sales ELSE 0 END), 0) - 1
          AS revenue_trend_pct
      FROM {args.revenue_table}
      WHERE `Day Date` >= CURRENT_DATE - INTERVAL {days} DAYS
      GROUP BY `Store Code`
    ),
    cdi AS (
      SELECT store_code,
        AVG((totpromo_rolling - totdetr_rolling) /
          NULLIF(CAST(totresp_rolling AS DOUBLE), 0)) AS avg_cdi,
        AVG(CASE WHEN date_dimension_identifier >= CAST(DATE_FORMAT(
          CURRENT_DATE - INTERVAL 30 DAYS, 'yyyyMMdd') AS INT)
          THEN (totpromo_rolling - totdetr_rolling) /
            NULLIF(CAST(totresp_rolling AS DOUBLE), 0) END)
        - AVG(CASE WHEN date_dimension_identifier BETWEEN CAST(DATE_FORMAT(
          CURRENT_DATE - INTERVAL 60 DAYS, 'yyyyMMdd') AS INT) AND CAST(DATE_FORMAT(
          CURRENT_DATE - INTERVAL 31 DAYS, 'yyyyMMdd') AS INT)
          THEN (totpromo_rolling - totdetr_rolling) /
            NULLIF(CAST(totresp_rolling AS DOUBLE), 0) END) AS cdi_trend_delta
      FROM {args.cdi_table}
      WHERE date_dimension_identifier >= CAST(DATE_FORMAT(
        CURRENT_DATE - INTERVAL {days} DAYS, 'yyyyMMdd') AS INT)
      GROUP BY store_code
    ),
    stores AS (
      SELECT DISTINCT store_code, store_cluster_membership_group_identifier
      FROM {args.store_dimension_table}
    ),
    membership AS (
      SELECT DISTINCT store_cluster_membership_group_identifier,
        store_cluster_dimension_identifier AS peer_group_id
      FROM {args.peer_set_table}
    ),
    metrics AS (
      SELECT s.store_code, m.peer_group_id, r.total_revenue, r.revenue_trend_pct,
        c.avg_cdi, c.cdi_trend_delta
      FROM stores s
      LEFT JOIN membership m USING (store_cluster_membership_group_identifier)
      LEFT JOIN revenue r USING (store_code)
      LEFT JOIN cdi c USING (store_code)
    ),
    ranked AS (
      SELECT *, PERCENT_RANK() OVER (ORDER BY total_revenue) AS revenue_pctile,
        PERCENT_RANK() OVER (ORDER BY avg_cdi DESC) AS cdi_pctile
      FROM metrics
    ),
    peer_metrics AS (
      SELECT peer_group_id, AVG(total_revenue) AS peer_avg_daily_revenue,
        AVG(avg_cdi) AS peer_avg_cdi
      FROM ranked GROUP BY peer_group_id
    )
    SELECT r.store_code, r.peer_group_id, r.total_revenue, r.revenue_pctile,
      r.revenue_trend_pct, r.avg_cdi, r.cdi_pctile, r.cdi_trend_delta,
      p.peer_avg_daily_revenue, p.peer_avg_cdi, CURRENT_DATE AS snapshot_date
    FROM ranked r LEFT JOIN peer_metrics p USING (peer_group_id)
    """
    spark.sql(f"CREATE OR REPLACE TABLE {args.snapshot_table} USING DELTA AS {snapshot_sql}")


if __name__ == "__main__":
    main()