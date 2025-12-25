"""API routes for comment resolution time metrics."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams, build_repository_filter, build_time_filter

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.comment_resolution")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


def _build_can_be_merged_cte(time_filter: str, repository_filter: str) -> str:
    """Build CTE for finding first successful can-be-merged check run per PR.

    Args:
        time_filter: SQL WHERE clause for time filtering
        repository_filter: SQL WHERE clause for repository filtering

    Returns:
        SQL CTE string for can_be_merged query
    """
    return (
        """
    can_be_merged AS (
        SELECT
            w.repository,
            (w.payload->'check_run'->>'pull_requests')::jsonb->0->>'number' as pr_number_text,
            MIN(w.created_at) as can_be_merged_at
        FROM webhooks w
        WHERE w.event_type = 'check_run'
          AND w.payload->'check_run'->>'name' = 'can-be-merged'
          AND w.payload->'check_run'->>'conclusion' = 'success'
          """
        + time_filter
        + repository_filter
        + """
        GROUP BY w.repository, (w.payload->'check_run'->>'pull_requests')::jsonb->0->>'number'
    )"""
    )


@router.get("/comment-resolution-time", operation_id="get_comment_resolution_time")
async def get_comment_resolution_time(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    repositories: Annotated[list[str] | None, Query(description="Filter by repositories (org/repo format)")] = None,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=25, ge=1, description="Items per page for threads list"),
) -> dict[str, Any]:
    """Get per-thread comment resolution metrics.

    Analyzes individual comment threads from pull_request_review_thread events
    to provide granular metrics including time to first response, time to resolution,
    participant lists, and correlation with can-be-merged check runs.

    **Primary Use Cases:**
    - Track per-thread resolution efficiency
    - Identify slow-to-respond threads
    - Monitor time from can-be-merged to resolution
    - Analyze participant engagement per thread
    - Calculate resolution rates

    **Prerequisites:**
    - GitHub webhook must be configured to send `pull_request_review_thread` events
    - (Optional) Repository uses a "can-be-merged" check run for correlation

    **Enabling pull_request_review_thread webhooks:**
    1. Go to your GitHub repository → Settings → Webhooks
    2. Click on your webhook (or create one)
    3. Under "Which events would you like to trigger this webhook?", select "Let me select individual events"
    4. Check "Pull request review threads" in the list
    5. Save the webhook

    **Return Structure:**
    ```json
    {
      "summary": {
        "avg_resolution_time_hours": 2.5,
        "median_resolution_time_hours": 1.5,
        "avg_time_to_first_response_hours": 0.8,
        "avg_comments_per_thread": 3.2,
        "total_threads_analyzed": 150,
        "resolution_rate": 85.5
      },
      "by_repository": [
        {
          "repository": "org/repo1",
          "avg_resolution_time_hours": 2.0,
          "total_threads": 75,
          "resolved_threads": 65
        }
      ],
      "threads": [
        {
          "thread_node_id": "PRRT_abc123",
          "repository": "org/repo1",
          "pr_number": 123,
          "first_comment_at": "2024-01-15T10:00:00Z",
          "resolved_at": "2024-01-15T12:30:00Z",
          "resolution_time_hours": 2.5,
          "time_to_first_response_hours": 0.5,
          "comment_count": 4,
          "resolver": "user1",
          "participants": ["user1", "user2", "user3"],
          "file_path": "src/main.py",
          "can_be_merged_at": "2024-01-15T11:00:00Z",
          "time_from_can_be_merged_hours": 1.5
        }
      ],
      "pagination": {
        "total": 150,
        "page": 1,
        "page_size": 25,
        "total_pages": 6,
        "has_next": true,
        "has_prev": false
      }
    }
    ```

    **Metrics Explained:**
    - `avg_resolution_time_hours`: Average time from first comment to resolution
    - `median_resolution_time_hours`: Median resolution time (less affected by outliers)
    - `avg_time_to_first_response_hours`: Average time from first to second comment
    - `avg_comments_per_thread`: Average number of comments per thread
    - `total_threads_analyzed`: Total threads in dataset
    - `resolution_rate`: Percentage of threads that have been resolved
    - `time_to_first_response_hours`: Time from first to second comment (null if only 1 comment)
    - `time_from_can_be_merged_hours`: Time from can-be-merged success to resolution (null if no can-be-merged)

    **Errors:**
    - 400: Invalid datetime format in parameters
    - 500: Database connection error
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build base parameters
    base_params = QueryParams()
    time_filter = build_time_filter(base_params, start_datetime, end_datetime)
    repository_filter = build_repository_filter(base_params, repositories)

    # Calculate offset for pagination
    offset = (page - 1) * page_size

    # Query 1: Get all thread events with extracted metadata
    threads_query = (
        """
        WITH """
        + _build_can_be_merged_cte(time_filter, repository_filter)
        + """,
        thread_events AS (
            -- Get all pull_request_review_thread events
            SELECT
                w.repository,
                w.pr_number,
                w.action,
                w.created_at,
                w.payload->'thread'->>'node_id' as thread_node_id,
                w.payload->'thread'->>'path' as file_path,
                w.payload->'thread'->'comments' as comments_array,
                jsonb_array_length(w.payload->'thread'->'comments') as comment_count,
                w.payload->'thread'->'comments'->0->>'created_at' as first_comment_at,
                w.payload->'thread'->'comments'->0->'user'->>'login' as first_commenter,
                w.payload->'thread'->'comments'->1->>'created_at' as second_comment_at,
                w.payload->'sender'->>'login' as resolver
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_thread'
              AND w.pr_number IS NOT NULL
              AND w.payload->'thread'->>'node_id' IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        resolved_threads AS (
            -- Get resolution events
            SELECT
                thread_node_id,
                repository,
                pr_number,
                created_at as resolved_at,
                resolver
            FROM thread_events
            WHERE action = 'resolved'
        ),
        thread_metadata AS (
            -- Get thread metadata from first event (resolved or unresolved)
            SELECT DISTINCT ON (thread_node_id)
                thread_node_id,
                repository,
                pr_number,
                file_path,
                comment_count,
                first_comment_at::timestamptz as first_comment_at,
                second_comment_at::timestamptz as second_comment_at,
                comments_array
            FROM thread_events
            ORDER BY thread_node_id, created_at
        ),
        thread_participants AS (
            -- Extract unique participants per thread
            SELECT
                tm.thread_node_id,
                jsonb_agg(DISTINCT comment->'user'->>'login') as participants
            FROM thread_metadata tm,
                 jsonb_array_elements(tm.comments_array) as comment
            WHERE comment->'user'->>'login' IS NOT NULL
            GROUP BY tm.thread_node_id
        ),
        threads_with_resolution AS (
            -- Combine all thread data
            SELECT
                tm.thread_node_id,
                tm.repository,
                tm.pr_number,
                tm.file_path,
                tm.first_comment_at,
                tm.second_comment_at,
                CASE
                    WHEN tm.second_comment_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (tm.second_comment_at - tm.first_comment_at)) / 3600
                    ELSE NULL
                END as time_to_first_response_hours,
                rt.resolved_at,
                rt.resolver,
                CASE
                    WHEN rt.resolved_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (rt.resolved_at - tm.first_comment_at)) / 3600
                    ELSE NULL
                END as resolution_time_hours,
                tm.comment_count,
                tp.participants,
                cm.can_be_merged_at,
                CASE
                    WHEN rt.resolved_at IS NOT NULL AND cm.can_be_merged_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (rt.resolved_at - cm.can_be_merged_at)) / 3600
                    ELSE NULL
                END as time_from_can_be_merged_hours
            FROM thread_metadata tm
            LEFT JOIN resolved_threads rt ON tm.thread_node_id = rt.thread_node_id
            LEFT JOIN thread_participants tp ON tm.thread_node_id = tp.thread_node_id
            LEFT JOIN can_be_merged cm ON tm.repository = cm.repository AND tm.pr_number::text = cm.pr_number_text
        ),
        counted_threads AS (
            SELECT COUNT(*) as total_count
            FROM threads_with_resolution
        )
        SELECT
            twr.*,
            ct.total_count
        FROM threads_with_resolution twr
        CROSS JOIN counted_threads ct
        ORDER BY twr.first_comment_at DESC
        LIMIT $"""
        + str(len(base_params.get_params()) + 1)
        + """ OFFSET $"""
        + str(len(base_params.get_params()) + 2)
    )

    # Query 2: Get repository-level statistics
    repo_stats_query = (
        """
        WITH thread_events AS (
            SELECT
                w.repository,
                w.action,
                w.payload->'thread'->>'node_id' as thread_node_id
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_thread'
              AND w.pr_number IS NOT NULL
              AND w.payload->'thread'->>'node_id' IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        thread_counts AS (
            SELECT
                repository,
                COUNT(DISTINCT thread_node_id) as total_threads,
                COUNT(DISTINCT CASE WHEN action = 'resolved' THEN thread_node_id END) as resolved_threads
            FROM thread_events
            GROUP BY repository
        ),
        resolved_times AS (
            SELECT
                w.repository,
                w.payload->'thread'->>'node_id' as thread_node_id,
                w.payload->'thread'->'comments'->0->>'created_at' as first_comment_at_text,
                w.created_at as resolved_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_thread'
              AND w.action = 'resolved'
              AND w.payload->'thread'->>'node_id' IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        resolution_times_calculated AS (
            SELECT
                repository,
                EXTRACT(EPOCH FROM (resolved_at - first_comment_at_text::timestamptz)) / 3600 as resolution_hours
            FROM resolved_times
            WHERE first_comment_at_text IS NOT NULL
        )
        SELECT
            tc.repository,
            tc.total_threads,
            tc.resolved_threads,
            COALESCE(AVG(rtc.resolution_hours), 0.0) as avg_resolution_time_hours
        FROM thread_counts tc
        LEFT JOIN resolution_times_calculated rtc ON tc.repository = rtc.repository
        GROUP BY tc.repository, tc.total_threads, tc.resolved_threads
        ORDER BY tc.total_threads DESC
    """
    )

    try:
        param_list = base_params.get_params()

        # Execute queries in parallel
        threads_rows, repo_stats_rows = await asyncio.gather(
            db_manager.fetch(threads_query, *param_list, page_size, offset),
            db_manager.fetch(repo_stats_query, *param_list),
        )

        # Extract total count from first row (or 0 if no rows)
        total_threads = threads_rows[0]["total_count"] if threads_rows else 0

        # Calculate summary statistics
        resolution_times: list[float] = []
        response_times: list[float] = []
        comment_counts: list[int] = []
        resolved_count = 0

        for row in threads_rows:
            if row["comment_count"]:
                comment_counts.append(row["comment_count"])

            if row["resolution_time_hours"] is not None:
                resolution_times.append(row["resolution_time_hours"])
                resolved_count += 1

            if row["time_to_first_response_hours"] is not None:
                response_times.append(row["time_to_first_response_hours"])

        # Calculate summary metrics
        avg_resolution = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0

        median_resolution = 0.0
        if resolution_times:
            sorted_times = sorted(resolution_times)
            mid = len(sorted_times) // 2
            median_resolution = round(
                sorted_times[mid] if len(sorted_times) % 2 == 1 else (sorted_times[mid - 1] + sorted_times[mid]) / 2,
                1,
            )

        avg_response = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
        avg_comments = round(sum(comment_counts) / len(comment_counts), 1) if comment_counts else 0.0

        resolution_rate = round((resolved_count / total_threads * 100), 1) if total_threads > 0 else 0.0

        # Format threads for response
        threads_list = [
            {
                "thread_node_id": row["thread_node_id"],
                "repository": row["repository"],
                "pr_number": row["pr_number"],
                "first_comment_at": row["first_comment_at"].isoformat() if row["first_comment_at"] else None,
                "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
                "resolution_time_hours": round(row["resolution_time_hours"], 1)
                if row["resolution_time_hours"] is not None
                else None,
                "time_to_first_response_hours": round(row["time_to_first_response_hours"], 1)
                if row["time_to_first_response_hours"] is not None
                else None,
                "comment_count": row["comment_count"],
                "resolver": row["resolver"],
                "participants": row["participants"] if row["participants"] else [],
                "file_path": row["file_path"],
                "can_be_merged_at": row["can_be_merged_at"].isoformat() if row["can_be_merged_at"] else None,
                "time_from_can_be_merged_hours": round(row["time_from_can_be_merged_hours"], 1)
                if row["time_from_can_be_merged_hours"] is not None
                else None,
            }
            for row in threads_rows
        ]

        # Format repository stats
        by_repository = [
            {
                "repository": row["repository"],
                "avg_resolution_time_hours": round(row["avg_resolution_time_hours"], 1),
                "total_threads": row["total_threads"],
                "resolved_threads": row["resolved_threads"],
            }
            for row in repo_stats_rows
        ]

        # Calculate pagination metadata
        total_pages = (total_threads + page_size - 1) // page_size if page_size > 0 else 0

    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch comment resolution time metrics")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch comment resolution time metrics",
        ) from ex
    else:
        return {
            "summary": {
                "avg_resolution_time_hours": avg_resolution,
                "median_resolution_time_hours": median_resolution,
                "avg_time_to_first_response_hours": avg_response,
                "avg_comments_per_thread": avg_comments,
                "total_threads_analyzed": total_threads,
                "resolution_rate": resolution_rate,
            },
            "by_repository": by_repository,
            "threads": threads_list,
            "pagination": {
                "total": total_threads,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
