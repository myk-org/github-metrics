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
    pending_limit: int = Query(default=50, ge=1, description="Max pending PRs to return"),
) -> dict[str, Any]:
    """Get time from can-be-merged check success to last comment thread resolution.

    Calculates the time between when a PR's "can-be-merged" check run succeeds
    and when the last comment thread is resolved. This metric helps track
    how long it takes to address review comments after the PR is ready to merge.

    **Primary Use Cases:**
    - Monitor comment resolution efficiency
    - Identify PRs stuck waiting for comment resolution
    - Track team responsiveness to review feedback
    - Optimize code review workflow

    **Prerequisites:**
    - GitHub webhook must be configured to send `pull_request_review_thread` events
    - The repository must use a "can-be-merged" check run

    **Enabling pull_request_review_thread webhooks:**
    1. Go to your GitHub repository → Settings → Webhooks
    2. Click on your webhook (or create one)
    3. Under "Which events would you like to trigger this webhook?", select "Let me select individual events"
    4. Check "Pull request review threads" in the list
    5. Save the webhook

    For organization-level webhooks, configure this in Organization Settings → Webhooks.

    **Note:** If repositories don't have `pull_request_review_thread` events configured,
    this endpoint will return empty results for those repositories (no errors).

    **Return Structure:**
    ```json
    {
      "summary": {
        "avg_resolution_time_hours": 2.5,
        "median_resolution_time_hours": 1.5,
        "max_resolution_time_hours": 24.0,
        "total_prs_analyzed": 50
      },
      "by_repository": [
        {
          "repository": "org/repo1",
          "avg_resolution_time_hours": 2.0,
          "total_prs": 25
        }
      ],
      "prs_pending_resolution": [
        {
          "repository": "org/repo1",
          "pr_number": 123,
          "can_be_merged_at": "2024-01-15T10:00:00Z",
          "hours_waiting": 5.2
        }
      ]
    }
    ```

    **Notes:**
    - Only includes PRs that have both a successful can-be-merged check AND
      at least one pull_request_review_thread event
    - PRs without comment threads are excluded
    - `prs_pending_resolution` shows PRs that have can-be-merged success but
      still have unresolved comment threads

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

    # Query 1: Find PRs with can-be-merged success and their last thread resolution
    resolution_time_query = (
        """
        WITH """
        + _build_can_be_merged_cte(time_filter, repository_filter)
        + """,
        last_thread_resolved AS (
            -- Find the last thread resolution for each PR
            SELECT
                w.repository,
                w.pr_number,
                MAX(w.created_at) as last_resolved_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_thread'
              AND w.action = 'resolved'
              AND w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            cm.repository,
            cm.pr_number_text::int as pr_number,
            cm.can_be_merged_at,
            ltr.last_resolved_at,
            EXTRACT(EPOCH FROM (ltr.last_resolved_at - cm.can_be_merged_at)) / 3600 as resolution_hours
        FROM can_be_merged cm
        INNER JOIN last_thread_resolved ltr
            ON cm.repository = ltr.repository
            AND cm.pr_number_text::int = ltr.pr_number
        WHERE ltr.last_resolved_at > cm.can_be_merged_at
        ORDER BY resolution_hours DESC
    """
    )

    # Query 2: Find PRs pending resolution (have can-be-merged but unresolved threads)
    pending_resolution_query = (
        """
        WITH """
        + _build_can_be_merged_cte(time_filter, repository_filter)
        + """,
        thread_status AS (
            -- Get thread resolution status per PR
            SELECT
                w.repository,
                w.pr_number,
                SUM(CASE WHEN w.action = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
                SUM(CASE WHEN w.action = 'unresolved' THEN 1 ELSE 0 END) as unresolved_count
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_thread'
              AND w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY w.repository, w.pr_number
        ),
        prs_with_unresolved AS (
            -- PRs where unresolved > resolved (net unresolved threads)
            SELECT repository, pr_number
            FROM thread_status
            WHERE unresolved_count > resolved_count
        )
        SELECT
            cm.repository,
            cm.pr_number_text::int as pr_number,
            cm.can_be_merged_at,
            EXTRACT(EPOCH FROM (NOW() - cm.can_be_merged_at)) / 3600 as hours_waiting
        FROM can_be_merged cm
        INNER JOIN prs_with_unresolved pu
            ON cm.repository = pu.repository
            AND cm.pr_number_text::int = pu.pr_number
        ORDER BY hours_waiting DESC
        LIMIT $"""
        + str(len(base_params.get_params()) + 1)
        + """
    """
    )

    try:
        param_list = base_params.get_params()

        # Execute queries in parallel
        resolution_rows, pending_rows = await asyncio.gather(
            db_manager.fetch(resolution_time_query, *param_list),
            db_manager.fetch(pending_resolution_query, *param_list, pending_limit),
        )

        # Calculate summary statistics
        resolution_times = [
            row["resolution_hours"]
            for row in resolution_rows
            if row["resolution_hours"] is not None and row["resolution_hours"] > 0
        ]

        avg_resolution = 0.0
        median_resolution = 0.0
        max_resolution = 0.0
        total_prs = len(resolution_times)

        if resolution_times:
            avg_resolution = round(sum(resolution_times) / len(resolution_times), 1)
            sorted_times = sorted(resolution_times)
            mid = len(sorted_times) // 2
            median_resolution = round(
                sorted_times[mid] if len(sorted_times) % 2 == 1 else (sorted_times[mid - 1] + sorted_times[mid]) / 2,
                1,
            )
            max_resolution = round(max(resolution_times), 1)

        # Group by repository
        repo_stats: dict[str, dict[str, Any]] = {}
        for row in resolution_rows:
            repo = row["repository"]
            if repo not in repo_stats:
                repo_stats[repo] = {"times": [], "count": 0}
            if row["resolution_hours"] is not None and row["resolution_hours"] > 0:
                repo_stats[repo]["times"].append(row["resolution_hours"])
                repo_stats[repo]["count"] += 1

        by_repository = [
            {
                "repository": repo,
                "avg_resolution_time_hours": round(sum(stats["times"]) / len(stats["times"]), 1)
                if stats["times"]
                else 0.0,
                "total_prs": stats["count"],
            }
            for repo, stats in sorted(repo_stats.items(), key=lambda x: -x[1]["count"])
        ]

        # Format pending PRs
        prs_pending = [
            {
                "repository": row["repository"],
                "pr_number": row["pr_number"],
                "can_be_merged_at": row["can_be_merged_at"].isoformat() if row["can_be_merged_at"] else None,
                "hours_waiting": round(row["hours_waiting"], 1) if row["hours_waiting"] else 0.0,
            }
            for row in pending_rows
        ]

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
                "max_resolution_time_hours": max_resolution,
                "total_prs_analyzed": total_prs,
            },
            "by_repository": by_repository,
            "prs_pending_resolution": prs_pending,
        }
