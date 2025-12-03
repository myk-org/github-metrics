"""API routes for metrics summary with trends."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.summary")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/summary", operation_id="get_metrics_summary")
async def get_metrics_summary(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
) -> dict[str, Any]:
    """Get overall metrics summary for webhook processing.

    Provides high-level overview of webhook processing metrics including total events,
    performance statistics, success rates, and top repositories. Essential for operational
    dashboards, executive reporting, and system health monitoring.

    **Primary Use Cases:**
    - Generate executive dashboards and summary reports
    - Monitor overall system health and performance
    - Track webhook processing trends over time
    - Identify system-wide performance issues
    - Analyze API usage patterns across all repositories
    - Quick health check for webhook processing system

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format.
      Example: "2024-01-01T00:00:00Z"
      Default: No time filter (all-time stats)
    - `end_time` (str, optional): End of time range in ISO 8601 format.
      Example: "2024-01-31T23:59:59Z"
      Default: No time filter (up to current time)

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-31T23:59:59Z"
      },
      "summary": {
        "total_events": 8745,
        "successful_events": 8423,
        "failed_events": 322,
        "success_rate": 96.32,
        "avg_processing_time_ms": 5834,
        "median_processing_time_ms": 4521,
        "p95_processing_time_ms": 14234,
        "max_processing_time_ms": 52134,
        "total_api_calls": 104940,
        "avg_api_calls_per_event": 12.0,
        "total_token_spend": 104940,
        "total_events_trend": 15.3,
        "success_rate_trend": 2.1,
        "failed_events_trend": -8.5,
        "avg_duration_trend": -12.4
      },
      "top_repositories": [
        {
          "repository": "myakove/high-traffic-repo",
          "total_events": 3456,
          "success_rate": 98.5
        },
        {
          "repository": "myakove/medium-traffic-repo",
          "total_events": 2134,
          "success_rate": 95.2
        },
        {
          "repository": "myakove/low-traffic-repo",
          "total_events": 856,
          "success_rate": 97.8
        }
      ],
      "event_type_distribution": {
        "pull_request": 4523,
        "issue_comment": 2134,
        "check_run": 1234,
        "push": 854
      },
      "hourly_event_rate": 12.3,
      "daily_event_rate": 295.4
    }
    ```

    **Metrics Explained:**
    - `total_events`: Total webhook events processed in time range
    - `successful_events`: Events that completed successfully
    - `failed_events`: Events that failed or partially failed
    - `success_rate`: Overall success percentage (0-100)
    - `avg_processing_time_ms`: Average processing duration across all events
    - `median_processing_time_ms`: Median processing duration (50th percentile)
    - `p95_processing_time_ms`: 95th percentile processing time (SLA metric)
    - `max_processing_time_ms`: Maximum processing time (worst case scenario)
    - `total_api_calls`: Total GitHub API calls made across all events
    - `avg_api_calls_per_event`: Average API calls per webhook event
    - `total_token_spend`: Total rate limit tokens consumed
    - `total_events_trend`: Percentage change in total events vs previous period (e.g., 15.3 = 15.3% increase)
    - `success_rate_trend`: Percentage change in success rate vs previous period
    - `failed_events_trend`: Percentage change in failed events vs previous period (negative = improvement)
    - `avg_duration_trend`: Percentage change in avg processing time vs previous period (negative = faster)
    - `top_repositories`: Top 10 repositories by event volume
    - `event_type_distribution`: Event count breakdown by type
    - `hourly_event_rate`: Average events per hour in time range
    - `daily_event_rate`: Average events per day in time range

    **Trend Calculation:**
    - Trends compare current period to previous period of equal duration
    - Example: If querying last 24 hours, trends compare to 24 hours before that
    - Trend = ((current - previous) / previous) * 100
    - Returns 0.0 if no previous data or both periods have no events
    - Returns 100.0 if previous period had 0 but current period has data
    - Negative trends for duration metrics indicate performance improvement

    **Common Analysis Scenarios:**
    - Daily summary: `start_time=<today>&end_time=<now>`
    - Weekly trends: `start_time=<week_start>&end_time=<week_end>`
    - Monthly reporting: `start_time=2024-01-01&end_time=2024-01-31`
    - System health check: No time filters (all-time stats)

    **Error Conditions:**
    - 400: Invalid datetime format in start_time/end_time parameters
    - 500: Database connection errors or query failures

    **AI Agent Usage Examples:**
    - "Show overall metrics summary for last month for executive report"
    - "Get webhook processing health metrics to check system status"
    - "Analyze event type distribution to understand webhook traffic patterns"
    - "Review top repositories by event volume to identify high-traffic sources"

    **Performance Notes:**
    - Summary computed in real-time from webhooks table
    - Optimized queries using indexed columns (created_at, repository, event_type)
    - Large date ranges may increase query time
    - Consider caching for frequently accessed time ranges
    """

    # Helper function to calculate percentage change trends
    def calculate_trend(current: float, previous: float) -> float:
        """Calculate percentage change from previous to current.

        Args:
            current: Current period value
            previous: Previous period value

        Returns:
            Percentage change rounded to 1 decimal place
            - Returns 0.0 if both values are 0
            - Returns 100.0 if previous is 0 but current is not
        """
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / previous) * 100, 1)

    # Validate database manager is available
    if db_manager is None:
        LOGGER.error("Database manager not initialized - metrics server may not be properly configured")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    # Parse datetime strings
    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Calculate previous period for trend comparison
    prev_start_datetime = None
    prev_end_datetime = None
    if start_datetime and end_datetime:
        # Previous period has same duration as current period
        period_duration = end_datetime - start_datetime
        prev_start_datetime = start_datetime - period_duration
        prev_end_datetime = end_datetime - period_duration

    # Build query with time filters for current period
    where_clause = "WHERE 1=1"
    params: list[Any] = []
    param_idx = 1

    if start_datetime:
        where_clause += " AND created_at >= $" + str(param_idx)
        params.append(start_datetime)
        param_idx += 1

    if end_datetime:
        where_clause += " AND created_at <= $" + str(param_idx)
        params.append(end_datetime)
        param_idx += 1

    # Build query with time filters for previous period
    prev_where_clause = "WHERE 1=1"
    prev_params: list[Any] = []
    prev_param_idx = 1

    if prev_start_datetime:
        prev_where_clause += " AND created_at >= $" + str(prev_param_idx)
        prev_params.append(prev_start_datetime)
        prev_param_idx += 1

    if prev_end_datetime:
        prev_where_clause += " AND created_at <= $" + str(prev_param_idx)
        prev_params.append(prev_end_datetime)
        prev_param_idx += 1

    # Main summary query
    summary_query = (
        """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / NULLIF(COUNT(*), 0)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(AVG(duration_ms)) as avg_processing_time_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as median_processing_time_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_processing_time_ms,
            MAX(duration_ms) as max_processing_time_ms,
            SUM(api_calls_count) as total_api_calls,
            ROUND(AVG(api_calls_count), 2) as avg_api_calls_per_event,
            SUM(token_spend) as total_token_spend
        FROM webhooks
        """
        + where_clause
    )

    # Top repositories query
    top_repos_query = (
        """
        WITH total AS (
            SELECT COUNT(*) as total_count
            FROM webhooks
            """
        + where_clause
        + """
        )
        SELECT
            repository,
            COUNT(*) as total_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / COUNT(*)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(
                (COUNT(*)::numeric / (SELECT total_count FROM total) * 100)::numeric,
                2
            ) as percentage
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY repository
        ORDER BY total_events DESC
        LIMIT 10
    """
    )

    # Event type distribution query
    event_type_query = (
        """
        SELECT
            event_type,
            COUNT(*) as event_count
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY event_type
        ORDER BY event_count DESC
    """
    )

    # Time range for rate calculations
    time_range_query = (
        """
        SELECT
            MIN(created_at) as first_event_time,
            MAX(created_at) as last_event_time
        FROM webhooks
        """
        + where_clause
    )

    # Previous period summary query for trend calculation
    prev_summary_query = (
        """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / NULLIF(COUNT(*), 0)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(AVG(duration_ms)) as avg_processing_time_ms
        FROM webhooks
        """
        + prev_where_clause
    )

    try:
        # Execute independent queries in parallel for better performance
        summary_row, top_repos_rows, event_type_rows, time_range_row = await asyncio.gather(
            db_manager.fetchrow(summary_query, *params),
            db_manager.fetch(top_repos_query, *params),
            db_manager.fetch(event_type_query, *params),
            db_manager.fetchrow(time_range_query, *params),
        )

        # Execute previous period query if time range is specified
        prev_summary_row = None
        if prev_start_datetime and prev_end_datetime:
            prev_summary_row = await db_manager.fetchrow(prev_summary_query, *prev_params)

        # Ensure summary_row is not None before processing
        if summary_row is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Summary query returned no results",
            )

        # Process summary metrics
        total_events = summary_row["total_events"] or 0
        current_success_rate = float(summary_row["success_rate"]) if summary_row["success_rate"] is not None else 0.0
        current_failed_events = summary_row["failed_events"] or 0
        current_avg_duration = (
            int(summary_row["avg_processing_time_ms"]) if summary_row["avg_processing_time_ms"] is not None else 0
        )

        summary = {
            "total_events": total_events,
            "successful_events": summary_row["successful_events"] or 0,
            "failed_events": current_failed_events,
            "success_rate": current_success_rate,
            "avg_processing_time_ms": current_avg_duration,
            "median_processing_time_ms": int(summary_row["median_processing_time_ms"])
            if summary_row["median_processing_time_ms"] is not None
            else 0,
            "p95_processing_time_ms": int(summary_row["p95_processing_time_ms"])
            if summary_row["p95_processing_time_ms"] is not None
            else 0,
            "max_processing_time_ms": summary_row["max_processing_time_ms"] or 0,
            "total_api_calls": summary_row["total_api_calls"] or 0,
            "avg_api_calls_per_event": float(summary_row["avg_api_calls_per_event"])
            if summary_row["avg_api_calls_per_event"] is not None
            else 0.0,
            "total_token_spend": summary_row["total_token_spend"] or 0,
        }

        # Calculate and add trend fields if previous period data is available
        if prev_summary_row is not None:
            prev_total_events = prev_summary_row["total_events"] or 0
            prev_success_rate = (
                float(prev_summary_row["success_rate"]) if prev_summary_row["success_rate"] is not None else 0.0
            )
            prev_failed_events = prev_summary_row["failed_events"] or 0
            prev_avg_duration = (
                int(prev_summary_row["avg_processing_time_ms"])
                if prev_summary_row["avg_processing_time_ms"] is not None
                else 0
            )

            summary["total_events_trend"] = calculate_trend(float(total_events), float(prev_total_events))
            summary["success_rate_trend"] = calculate_trend(current_success_rate, prev_success_rate)
            summary["failed_events_trend"] = calculate_trend(float(current_failed_events), float(prev_failed_events))
            summary["avg_duration_trend"] = calculate_trend(float(current_avg_duration), float(prev_avg_duration))
        else:
            # No previous period data - set trends to 0.0
            summary["total_events_trend"] = 0.0
            summary["success_rate_trend"] = 0.0
            summary["failed_events_trend"] = 0.0
            summary["avg_duration_trend"] = 0.0

        # Process top repositories
        top_repositories = [
            {
                "repository": row["repository"],
                "total_events": row["total_events"],
                "percentage": float(row["percentage"]) if row["percentage"] is not None else 0.0,
                "success_rate": float(row["success_rate"]) if row["success_rate"] is not None else 0.0,
            }
            for row in top_repos_rows
        ]

        # Process event type distribution
        event_type_distribution = {row["event_type"]: row["event_count"] for row in event_type_rows}

        # Calculate event rates
        hourly_event_rate = 0.0
        daily_event_rate = 0.0
        if time_range_row and time_range_row["first_event_time"] and time_range_row["last_event_time"]:
            time_diff = time_range_row["last_event_time"] - time_range_row["first_event_time"]
            total_hours = max(time_diff.total_seconds() / 3600, 1)  # Avoid division by zero
            total_days = max(time_diff.total_seconds() / 86400, 1)  # Avoid division by zero
            hourly_event_rate = round(total_events / total_hours, 2)
            daily_event_rate = round(total_events / total_days, 2)

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "summary": summary,
            "top_repositories": top_repositories,
            "event_type_distribution": event_type_distribution,
            "hourly_event_rate": hourly_event_rate,
            "daily_event_rate": daily_event_rate,
        }
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch metrics summary from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics summary",
        ) from ex
