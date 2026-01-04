"""API routes for review turnaround time metrics."""

import asyncio
from typing import Annotated, Any, cast

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams, build_repository_filter, build_time_filter

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.turnaround")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/turnaround", operation_id="get_review_turnaround")
async def get_review_turnaround(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    repositories: Annotated[list[str] | None, Query(description="Filter by repositories (org/repo format)")] = None,
    users: Annotated[list[str] | None, Query(description="Filter by reviewer usernames (include)")] = None,
    exclude_users: Annotated[list[str] | None, Query(description="Exclude reviewers from results")] = None,
) -> dict[str, Any]:
    """Get PR review turnaround time metrics.

    Calculates review turnaround times including time to first review, time to approval,
    and complete PR lifecycle duration. Essential for tracking review performance,
    identifying bottlenecks, and improving development velocity.

    **Primary Use Cases:**
    - Monitor review responsiveness and identify delays
    - Track reviewer performance and workload distribution
    - Identify repositories with slow review cycles
    - Measure team collaboration effectiveness
    - Generate SLA compliance reports for review times
    - Optimize development workflow based on turnaround data

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format
      Default: No time filter (all-time stats)
    - `end_time` (str, optional): End of time range in ISO 8601 format
      Default: No time filter (up to current time)
    - `repositories` (list[str], optional): Filter by repositories (org/repo format)
    - `users` (list[str], optional): Filter by reviewer usernames to include
      Note: The users filter only affects reviewer-centric metrics (time_to_first_review,
      by_repository breakdown, by_reviewer stats). Approval and lifecycle metrics remain
      global for the given time/repository filters since they track PR completion states.
    - `exclude_users` (list[str], optional): Exclude reviewers from results

    **Return Structure:**
    ```json
    {
      "summary": {
        "avg_time_to_first_review_hours": 2.5,
        "avg_time_to_approval_hours": 8.3,
        "avg_time_to_first_verified_hours": 10.2,
        "avg_time_to_first_changes_requested_hours": 4.7,
        "avg_pr_lifecycle_hours": 24.1,
        "total_prs_analyzed": 150
      },
      "by_repository": [
        {
          "repository": "org/repo1",
          "avg_time_to_first_review_hours": 1.2,
          "avg_time_to_approval_hours": 4.5,
          "avg_time_to_first_verified_hours": 6.8,
          "avg_time_to_first_changes_requested_hours": 3.5,
          "avg_pr_lifecycle_hours": 12.0,
          "total_prs": 50
        }
      ],
      "by_reviewer": [
        {
          "reviewer": "user1",
          "avg_response_time_hours": 1.5,
          "total_reviews": 30,
          "repositories_reviewed": ["org/repo1", "org/repo2"]
        }
      ]
    }
    ```

    **Metrics Explained:**
    - `avg_time_to_first_review_hours`: Average time from PR creation to first review submission
      (includes all PRs with at least one review, regardless of completion status)
    - `avg_time_to_approval_hours`: Average time from PR creation to first approval
      (includes all PRs with at least one approval, regardless of completion status)
    - `avg_time_to_first_verified_hours`: Average time from PR creation to first verified label
      (includes all PRs with at least one verified label, regardless of completion status)
    - `avg_time_to_first_changes_requested_hours`: Average time from PR creation to first changes_requested review
      (includes all PRs with at least one changes_requested review, regardless of completion status)
    - `avg_pr_lifecycle_hours`: Average time from PR creation to merge/close
      (ONLY includes completed PRs - merged or closed)
    - `avg_response_time_hours`: Average review response time per reviewer
    - `total_prs_analyzed`: Number of ALL PRs opened in time range (includes open, merged, and closed PRs)
    - `total_reviews`: Total number of reviews submitted by reviewer
    - `repositories_reviewed`: List of repositories reviewed by user

    **Calculation Details:**
    - Times are calculated from pull_requests and pr_reviews tables
    - Review metrics include ALL PRs with reviews (open, merged, or closed)
    - Lifecycle metrics ONLY include completed PRs (merged or closed)
    - Hours are rounded to 1 decimal place for readability
    - NULL values are handled gracefully (excluded from averages)

    **Errors:**
    - 400: Invalid datetime format in parameters
    - 500: Database connection error

    **Performance Notes:**
    - Queries use indexed columns (created_at, repository, reviewer)
    - Large date ranges may increase query time
    - Results are computed in real-time (not cached)
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build base parameters (time + repository filters)
    # These are used by ALL queries
    base_params = QueryParams()
    time_filter = build_time_filter(base_params, start_datetime, end_datetime)
    repository_filter = build_repository_filter(base_params, repositories)

    # Build reviewer parameters (base params + user filters)
    # These are used only by queries that filter by reviewer
    reviewer_params = base_params.clone()

    user_filter_reviewer = ""
    if users:
        user_filter_reviewer = f" AND w.sender = ANY({reviewer_params.add(users)})"

    exclude_user_filter_reviewer = ""
    if exclude_users:
        exclude_user_filter_reviewer = f" AND w.sender != ALL({reviewer_params.add(exclude_users)})"

    # Query 1: Time to first review per PR (for overall summary)
    # Find the first 'pull_request_review' event for each PR after it was opened
    time_to_first_review_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        first_review AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_review_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request_review'
              AND w.action = 'submitted'
              AND w.sender IS DISTINCT FROM w.pr_author
              """
        + user_filter_reviewer
        + exclude_user_filter_reviewer
        + """
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            EXTRACT(EPOCH FROM (fr.first_review_at - po.opened_at)) / 3600 as hours_to_first_review
        FROM pr_opened po
        INNER JOIN first_review fr ON po.repository = fr.repository AND po.pr_number = fr.pr_number
    """
    )

    # Query 2: Time to approval per PR (for overall summary)
    # Find the first approval label for each PR after it was opened
    time_to_approval_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        first_approval AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_approval_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'labeled'
              AND w.label_name LIKE 'approved-%'
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            EXTRACT(EPOCH FROM (fa.first_approval_at - po.opened_at)) / 3600 as hours_to_approval
        FROM pr_opened po
        INNER JOIN first_approval fa ON po.repository = fa.repository AND po.pr_number = fa.pr_number
    """
    )

    # Query 3: Time to first verified per PR (for overall summary)
    # Find the first verified label for each PR after it was opened
    time_to_verified_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        first_verified AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_verified_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'labeled'
              AND LOWER(w.label_name) LIKE '%verified%'
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            EXTRACT(EPOCH FROM (fv.first_verified_at - po.opened_at)) / 3600 as hours_to_verified
        FROM pr_opened po
        INNER JOIN first_verified fv ON po.repository = fv.repository AND po.pr_number = fv.pr_number
    """
    )

    # Query 4: Time to first changes_requested per PR (for overall summary)
    # Find the first changes_requested review for each PR after it was opened
    time_to_changes_requested_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        first_changes_requested AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_changes_requested_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request_review'
              AND w.action = 'submitted'
              AND w.payload->'review'->>'state' = 'changes_requested'
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            EXTRACT(EPOCH FROM (fcr.first_changes_requested_at - po.opened_at)) / 3600 as hours_to_changes_requested
        FROM pr_opened po
        INNER JOIN first_changes_requested fcr ON po.repository = fcr.repository AND po.pr_number = fcr.pr_number
    """
    )

    # Query 5: PR lifecycle duration (overall summary)
    # Calculate time from PR opened to PR merged/closed
    pr_lifecycle_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        pr_closed AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as closed_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'closed'
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            AVG(EXTRACT(EPOCH FROM (pc.closed_at - po.opened_at)) / 3600) as avg_hours,
            COUNT(*) as total_prs
        FROM pr_opened po
        INNER JOIN pr_closed pc ON po.repository = pc.repository AND po.pr_number = pc.pr_number
    """
    )

    # Query 6: Count all PRs opened in the time range
    # This is used for total_prs_analyzed (includes open, merged, and closed PRs)
    total_prs_query = (
        """
        SELECT COUNT(DISTINCT (repository, pr_number)) as total_prs
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'opened'
          AND pr_number IS NOT NULL
          """
        + time_filter
        + repository_filter
    )

    # Query 7: By repository
    by_repository_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        ),
        first_review AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_review_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request_review'
              AND w.action = 'submitted'
              AND w.sender IS DISTINCT FROM w.pr_author
              """
        + user_filter_reviewer
        + exclude_user_filter_reviewer
        + """
            GROUP BY w.repository, w.pr_number
        ),
        first_approval AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_approval_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'labeled'
              AND w.label_name LIKE 'approved-%'
            GROUP BY w.repository, w.pr_number
        ),
        first_verified AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_verified_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'labeled'
              AND LOWER(w.label_name) LIKE '%verified%'
            GROUP BY w.repository, w.pr_number
        ),
        first_changes_requested AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as first_changes_requested_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request_review'
              AND w.action = 'submitted'
              AND w.payload->'review'->>'state' = 'changes_requested'
            GROUP BY w.repository, w.pr_number
        ),
        pr_closed AS (
            SELECT
                w.repository,
                w.pr_number,
                MIN(w.created_at) as closed_at
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'closed'
            GROUP BY w.repository, w.pr_number
        )
        SELECT
            po.repository,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (fr.first_review_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_time_to_first_review_hours,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (fa.first_approval_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_time_to_approval_hours,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (fv.first_verified_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_time_to_first_verified_hours,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (fcr.first_changes_requested_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_time_to_first_changes_requested_hours,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (pc.closed_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_pr_lifecycle_hours,
            COUNT(DISTINCT po.pr_number) as total_prs
        FROM pr_opened po
        LEFT JOIN first_review fr ON po.repository = fr.repository AND po.pr_number = fr.pr_number
        LEFT JOIN first_approval fa ON po.repository = fa.repository AND po.pr_number = fa.pr_number
        LEFT JOIN first_verified fv ON po.repository = fv.repository AND po.pr_number = fv.pr_number
        LEFT JOIN first_changes_requested fcr ON po.repository = fcr.repository AND po.pr_number = fcr.pr_number
        LEFT JOIN pr_closed pc ON po.repository = pc.repository AND po.pr_number = pc.pr_number
        GROUP BY po.repository
        ORDER BY total_prs DESC
    """
    )

    # Query 8: By reviewer
    by_reviewer_query = (
        """
        WITH pr_opened AS (
            SELECT
                repository,
                pr_number,
                MIN(created_at) as opened_at
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'opened'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            GROUP BY repository, pr_number
        )
        SELECT
            w.sender as reviewer,
            ROUND(
                AVG(EXTRACT(EPOCH FROM (w.created_at - po.opened_at)) / 3600)::numeric, 1
            ) as avg_response_time_hours,
            COUNT(*) as total_reviews,
            ARRAY_AGG(DISTINCT w.repository ORDER BY w.repository) as repositories
        FROM webhooks w
        INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
        WHERE w.event_type = 'pull_request_review'
          AND w.action = 'submitted'
          AND w.sender IS DISTINCT FROM w.pr_author
          """
        + user_filter_reviewer
        + exclude_user_filter_reviewer
        + """
        GROUP BY w.sender
        ORDER BY total_reviews DESC
    """
    )

    try:
        # Get actual parameter lists
        base_param_list = base_params.get_params()
        reviewer_param_list = reviewer_params.get_params()

        # Execute all queries in parallel
        # Note: Some queries use reviewer_params (with user filter), others use base_params
        results = await asyncio.gather(
            db_manager.fetch(time_to_first_review_query, *reviewer_param_list),  # Uses user filter
            db_manager.fetch(time_to_approval_query, *base_param_list),  # No user filter
            db_manager.fetch(time_to_verified_query, *base_param_list),  # No user filter
            db_manager.fetch(time_to_changes_requested_query, *base_param_list),  # No user filter
            db_manager.fetchrow(pr_lifecycle_query, *base_param_list),  # No user filter
            db_manager.fetchrow(total_prs_query, *base_param_list),  # No user filter - count all PRs opened
            db_manager.fetch(by_repository_query, *reviewer_param_list),  # Uses user filter
            db_manager.fetch(by_reviewer_query, *reviewer_param_list),  # Uses user filter
        )

        # Explicit type casts to satisfy mypy (asyncio.gather returns mixed types)
        first_review_rows = cast(list[asyncpg.Record], results[0])
        approval_rows = cast(list[asyncpg.Record], results[1])
        verified_rows = cast(list[asyncpg.Record], results[2])
        changes_requested_rows = cast(list[asyncpg.Record], results[3])
        lifecycle_row = cast(asyncpg.Record | None, results[4])
        total_prs_row = cast(asyncpg.Record | None, results[5])
        by_repo_rows = cast(list[asyncpg.Record], results[6])
        by_reviewer_rows = cast(list[asyncpg.Record], results[7])

        # Calculate overall averages
        avg_first_review = 0.0
        if first_review_rows:
            review_times = [
                row["hours_to_first_review"] for row in first_review_rows if row["hours_to_first_review"] is not None
            ]
            if review_times:
                avg_first_review = float(round(sum(review_times) / len(review_times), 1))

        avg_approval = 0.0
        if approval_rows:
            approval_times = [row["hours_to_approval"] for row in approval_rows if row["hours_to_approval"] is not None]
            if approval_times:
                avg_approval = float(round(sum(approval_times) / len(approval_times), 1))

        avg_verified = 0.0
        if verified_rows:
            verified_times = [row["hours_to_verified"] for row in verified_rows if row["hours_to_verified"] is not None]
            if verified_times:
                avg_verified = float(round(sum(verified_times) / len(verified_times), 1))

        avg_changes_requested = 0.0
        if changes_requested_rows:
            changes_requested_times = [
                row["hours_to_changes_requested"]
                for row in changes_requested_rows
                if row["hours_to_changes_requested"] is not None
            ]
            if changes_requested_times:
                avg_changes_requested = float(round(sum(changes_requested_times) / len(changes_requested_times), 1))

        avg_lifecycle = 0.0
        if lifecycle_row:
            avg_lifecycle = round(float(lifecycle_row["avg_hours"] or 0), 1)

        total_prs = 0
        if total_prs_row:
            total_prs = total_prs_row["total_prs"] or 0

        summary = {
            "avg_time_to_first_review_hours": avg_first_review,
            "avg_time_to_approval_hours": avg_approval,
            "avg_time_to_first_verified_hours": avg_verified,
            "avg_time_to_first_changes_requested_hours": avg_changes_requested,
            "avg_pr_lifecycle_hours": avg_lifecycle,
            "total_prs_analyzed": total_prs,
        }

        # Format by_repository results
        by_repository = [
            {
                "repository": row["repository"],
                "avg_time_to_first_review_hours": float(row["avg_time_to_first_review_hours"] or 0),
                "avg_time_to_approval_hours": float(row["avg_time_to_approval_hours"] or 0),
                "avg_time_to_first_verified_hours": float(row["avg_time_to_first_verified_hours"] or 0),
                "avg_time_to_first_changes_requested_hours": float(
                    row["avg_time_to_first_changes_requested_hours"] or 0
                ),
                "avg_pr_lifecycle_hours": float(row["avg_pr_lifecycle_hours"] or 0),
                "total_prs": row["total_prs"],
            }
            for row in by_repo_rows
        ]

        # Format by_reviewer results
        by_reviewer = [
            {
                "reviewer": row["reviewer"],
                "avg_response_time_hours": float(row["avg_response_time_hours"] or 0),
                "total_reviews": row["total_reviews"],
                "repositories_reviewed": row["repositories"],
            }
            for row in by_reviewer_rows
        ]

    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch review turnaround metrics")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch review turnaround metrics",
        ) from ex
    else:
        return {
            "summary": summary,
            "by_repository": by_repository,
            "by_reviewer": by_reviewer,
        }
