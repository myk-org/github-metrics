"""API routes for metrics trends over time."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string
from github_metrics.utils.query_builders import QueryParams, build_time_filter

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.trends")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/trends", operation_id="get_metrics_trends")
async def get_metrics_trends(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    bucket: str = Query(default="hour", pattern="^(hour|day)$", description="Time bucket ('hour', 'day')"),
) -> dict[str, Any]:
    """Get aggregated event trends over time.

    Returns aggregated event counts (total, success, error) grouped by time bucket.
    Essential for visualizing event volume and success rates over time on charts.

    **Parameters:**
    - `start_time`: Start of time range in ISO format.
    - `end_time`: End of time range in ISO format.
    - `bucket`: Time aggregation bucket ('hour' or 'day').

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "...",
        "end_time": "..."
      },
      "trends": [
        {
          "bucket": "2024-01-15T14:00:00Z",
          "total_events": 120,
          "successful_events": 115,
          "failed_events": 5
        },
        ...
      ]
    }
    ```
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    params = QueryParams()
    where_clause = "WHERE 1=1"
    where_clause += build_time_filter(params, start_datetime, end_datetime)

    # Add bucket parameter
    bucket_placeholder = params.add(bucket)

    query = (
        f"""
        SELECT
            date_trunc({bucket_placeholder}, created_at) as bucket,
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY bucket
        ORDER BY bucket
    """
    )

    try:
        rows = await db_manager.fetch(query, *params.get_params())

        trends = [
            {
                "bucket": row["bucket"].isoformat() if row["bucket"] else None,
                "total_events": row["total_events"],
                "successful_events": row["successful_events"],
                "failed_events": row["failed_events"],
            }
            for row in rows
        ]

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "trends": trends,
        }
    except asyncio.CancelledError as ex:
        LOGGER.debug("Metrics trends request was cancelled")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Request was cancelled",
        ) from ex
    except Exception as ex:
        LOGGER.exception("Failed to fetch metrics trends from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics trends",
        ) from ex
