"""API routes for cross-team review metrics."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams, build_repository_filter, build_time_filter
from backend.utils.response_formatters import format_pagination_metadata

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.cross_team")

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/cross-team-reviews", operation_id="get_metrics_cross_team_reviews")
async def get_metrics_cross_team_reviews(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    repositories: Annotated[list[str] | None, Query(description="Filter by repositories (org/repo format)")] = None,
    reviewer_team: str | None = Query(default=None, description="Filter by reviewer's team (e.g., sig-storage)"),
    pr_team: str | None = Query(default=None, description="Filter by PR's sig label (e.g., sig-network)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=25, ge=1, description="Items per page"),
) -> dict[str, Any]:
    """Get cross-team review metrics.

    Analyzes webhook payloads to extract cross-team review activity where reviewers
    from one sig/team review PRs from a different sig/team. Essential for understanding
    cross-team collaboration and knowledge sharing patterns.

    **Primary Use Cases:**
    - Track cross-team collaboration and knowledge sharing
    - Identify teams that frequently review each other's work
    - Monitor review distribution across organizational boundaries
    - Measure cross-functional team engagement
    - Analyze reviewer expertise spread across teams

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `repositories` (list[str], optional): Filter by repositories (org/repo format)
    - `reviewer_team` (str, optional): Filter by reviewer's team (e.g., sig-storage)
    - `pr_team` (str, optional): Filter by PR's sig label (e.g., sig-network)
    - `page` (int, default=1): Page number (1-indexed)
    - `page_size` (int, default=25): Items per page

    **Return Structure:**
    ```json
    {
      "data": [
        {
          "pr_number": 123,
          "repository": "org/repo",
          "reviewer": "user1",
          "reviewer_team": "sig-storage",
          "pr_sig_label": "sig-network",
          "review_type": "approved",
          "created_at": "2024-01-15T10:00:00Z"
        }
      ],
      "summary": {
        "total_cross_team_reviews": 45,
        "by_reviewer_team": {"sig-storage": 20, "sig-network": 15},
        "by_pr_team": {"sig-network": 25, "sig-storage": 20}
      },
      "pagination": {
        "total": 45,
        "page": 1,
        "page_size": 25,
        "total_pages": 2
      }
    }
    ```

    **Notes:**
    - Only includes reviews where `is_cross_team = TRUE`
    - Review type is the action field (approved, changes_requested, commented)
    - Teams are identified by sig labels (e.g., sig-storage, sig-network)

    **Errors:**
    - 500: Database connection error or metrics server disabled
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build base filter parameters (time + repository filters)
    params = QueryParams()
    time_filter = build_time_filter(params, start_datetime, end_datetime)
    repository_filter = build_repository_filter(params, repositories)

    # Build reviewer_team filter
    reviewer_team_filter = ""
    if reviewer_team:
        reviewer_team_param = params.add(reviewer_team)
        reviewer_team_filter = " AND reviewer_team = " + reviewer_team_param

    # Build pr_team filter
    pr_team_filter = ""
    if pr_team:
        pr_team_param = params.add(pr_team)
        pr_team_filter = " AND pr_sig_label = " + pr_team_param

    # Mark pagination start before adding pagination parameters
    params.mark_pagination_start()
    # Add pagination parameters and use placeholders directly
    page_size_placeholder = params.add(page_size)
    offset_placeholder = params.add((page - 1) * page_size)

    # Count query for total cross-team reviews
    count_query = (
        """
        SELECT COUNT(*) as total
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND is_cross_team = TRUE
          """
        + time_filter
        + repository_filter
        + reviewer_team_filter
        + pr_team_filter
    )

    # Query for cross-team review data
    data_query = (
        """
        SELECT
            pr_number,
            repository,
            sender as reviewer,
            reviewer_team,
            pr_sig_label,
            action as review_type,
            created_at
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND is_cross_team = TRUE
          """
        + time_filter
        + repository_filter
        + reviewer_team_filter
        + pr_team_filter
        + f"""
        ORDER BY created_at DESC
        LIMIT {page_size_placeholder} OFFSET {offset_placeholder}
        """
    )

    # Summary query - group by reviewer_team
    summary_by_reviewer_team_query = (
        """
        SELECT
            reviewer_team,
            COUNT(*) as count
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND is_cross_team = TRUE
          """
        + time_filter
        + repository_filter
        + reviewer_team_filter
        + pr_team_filter
        + """
        GROUP BY reviewer_team
        ORDER BY count DESC
        """
    )

    # Summary query - group by pr_sig_label
    summary_by_pr_team_query = (
        """
        SELECT
            pr_sig_label,
            COUNT(*) as count
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND is_cross_team = TRUE
          """
        + time_filter
        + repository_filter
        + reviewer_team_filter
        + pr_team_filter
        + """
        GROUP BY pr_sig_label
        ORDER BY count DESC
        """
    )

    try:
        # Get params for count and summary queries (without LIMIT/OFFSET)
        params_without_pagination = params.get_params_excluding_pagination()
        # Get all params for data query
        all_params = params.get_params()

        # Execute all queries in parallel
        (
            total_count,
            data_rows,
            summary_by_reviewer_team_rows,
            summary_by_pr_team_rows,
        ) = await asyncio.gather(
            db_manager.fetchval(count_query, *params_without_pagination),
            db_manager.fetch(data_query, *all_params),
            db_manager.fetch(summary_by_reviewer_team_query, *params_without_pagination),
            db_manager.fetch(summary_by_pr_team_query, *params_without_pagination),
        )

        # Convert potentially None total to integer
        total_count = int(total_count or 0)

        # Format data
        data = [
            {
                "pr_number": row["pr_number"],
                "repository": row["repository"],
                "reviewer": row["reviewer"],
                "reviewer_team": row["reviewer_team"],
                "pr_sig_label": row["pr_sig_label"],
                "review_type": row["review_type"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in data_rows
        ]

        # Format summary - by reviewer team
        by_reviewer_team = {row["reviewer_team"]: row["count"] for row in summary_by_reviewer_team_rows}

        # Format summary - by PR team
        by_pr_team = {row["pr_sig_label"]: row["count"] for row in summary_by_pr_team_rows}

        # Calculate pagination metadata using shared formatter
        return {
            "data": data,
            "summary": {
                "total_cross_team_reviews": total_count,
                "by_reviewer_team": by_reviewer_team,
                "by_pr_team": by_pr_team,
            },
            "pagination": format_pagination_metadata(total_count, page, page_size),
        }
    except asyncio.CancelledError:
        LOGGER.debug("Cross-team reviews request was cancelled")
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch cross-team review metrics from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch cross-team review metrics",
        ) from ex
