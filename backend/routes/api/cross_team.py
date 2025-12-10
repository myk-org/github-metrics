"""API routes for cross-team review metrics."""

import asyncio
from datetime import datetime
from typing import Annotated, TypedDict

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.sig_teams import SigTeamsConfig
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams, build_repository_filter, build_time_filter
from backend.utils.response_formatters import format_pagination_metadata

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.cross_team")


class _CrossTeamRowInternal(TypedDict):
    """Internal structure for cross-team review processing.

    Note: pr_sig_label is always str (not None) because rows without sig labels
    are filtered out during processing. reviewer_team can be None if the reviewer
    is not in the SIG teams configuration.
    """

    pr_number: int
    repository: str
    reviewer: str
    reviewer_team: str | None
    pr_sig_label: str
    review_type: str
    created_at: datetime


class CrossTeamReviewRow(TypedDict):
    """Individual cross-team review record."""

    pr_number: int
    repository: str
    reviewer: str
    reviewer_team: str | None
    pr_sig_label: str
    review_type: str
    created_at: str


class CrossTeamSummary(TypedDict):
    """Summary statistics for cross-team reviews."""

    total_cross_team_reviews: int
    by_reviewer_team: dict[str, int]
    by_pr_team: dict[str, int]


class PaginationInfo(TypedDict):
    """Pagination metadata."""

    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CrossTeamResponse(TypedDict):
    """Response structure for cross-team reviews endpoint."""

    data: list[CrossTeamReviewRow]
    summary: CrossTeamSummary
    pagination: PaginationInfo


router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None
sig_teams_config: SigTeamsConfig | None = None


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
) -> CrossTeamResponse:
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
    - Cross-team status computed at query time using SIG teams configuration
    - Review type extracted from payload review state (approved, changes_requested, commented)
    - Special case: "lgtm" shown when review body contains "lgtm" (case-insensitive)
    - Teams are identified by sig labels (e.g., sig-storage, sig-network)

    **Errors:**
    - 500: Database connection error or metrics server disabled
    - 503: SIG teams configuration not loaded
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    if sig_teams_config is None or not sig_teams_config.is_loaded:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SIG teams configuration not loaded - cross-team tracking unavailable",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build base filter parameters (time + repository filters)
    params = QueryParams()
    time_filter = build_time_filter(params, start_datetime, end_datetime)
    repository_filter = build_repository_filter(params, repositories)

    # Query for pull_request_review events with sig labels
    # Note: We fetch ALL pull_request_review events and filter cross-team in Python
    # This allows historical data to work even though is_cross_team wasn't populated before
    data_query = (
        """
        SELECT
            pr_number,
            repository,
            sender as reviewer,
            CASE
                WHEN payload->'review'->>'body' LIKE '%/approve%' THEN 'approved'
                WHEN payload->'review'->>'body' LIKE '%/lgtm%' THEN 'lgtm'
                WHEN payload->'review'->>'state' = 'approved' THEN 'lgtm'
                ELSE COALESCE(payload->'review'->>'state', action)
            END as review_type,
            created_at,
            (SELECT label_elem->>'name'
             FROM jsonb_array_elements(payload->'pull_request'->'labels') AS label_elem
             WHERE label_elem->>'name' LIKE 'sig-%'
             LIMIT 1) AS extracted_pr_sig_label
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND action != 'dismissed'
          AND sender != payload->'pull_request'->'user'->>'login'
          """
        + time_filter
        + repository_filter
        + """
        ORDER BY created_at DESC
        """
    )

    try:
        # Get params (no pagination at SQL level - we filter in Python)
        query_params = params.get_params()

        # Fetch all matching rows
        all_rows = await db_manager.fetch(data_query, *query_params)

        # Post-processing in Python: compute cross-team status and apply filters
        cross_team_rows: list[_CrossTeamRowInternal] = []

        for row in all_rows:
            repository = str(row["repository"])
            reviewer = str(row["reviewer"])
            pr_sig_label_raw = row["extracted_pr_sig_label"]

            # Skip rows without sig labels (can't determine cross-team status)
            if pr_sig_label_raw is None:
                continue

            pr_sig_label = str(pr_sig_label_raw)

            # Get reviewer's team from sig_teams_config
            reviewer_team_result = sig_teams_config.get_user_team(repository, reviewer)

            # Determine if this is a cross-team review
            is_cross_team = sig_teams_config.is_cross_team_review(repository, reviewer, pr_sig_label)

            # Skip if not cross-team (includes None - reviewer not in config)
            if is_cross_team is not True:
                continue

            # Apply reviewer_team filter (post-SQL filtering)
            if reviewer_team and reviewer_team_result != reviewer_team:
                continue

            # Apply pr_team filter (post-SQL filtering)
            if pr_team and pr_sig_label != pr_team:
                continue

            # Add to cross-team results
            cross_team_rows.append(
                _CrossTeamRowInternal(
                    pr_number=int(row["pr_number"]),
                    repository=repository,
                    reviewer=reviewer,
                    reviewer_team=reviewer_team_result,
                    pr_sig_label=pr_sig_label,
                    review_type=str(row["review_type"]),
                    created_at=row["created_at"],
                )
            )

        # Calculate total count after filtering
        total_count = len(cross_team_rows)

        # Apply pagination in Python
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_rows = cross_team_rows[start_idx:end_idx]

        # Format data
        data: list[CrossTeamReviewRow] = [
            CrossTeamReviewRow(
                pr_number=row["pr_number"],
                repository=row["repository"],
                reviewer=row["reviewer"],
                reviewer_team=row["reviewer_team"],
                pr_sig_label=row["pr_sig_label"],
                review_type=row["review_type"],
                created_at=row["created_at"].isoformat(),
            )
            for row in paginated_rows
        ]

        # Compute summaries from ALL filtered cross-team rows (global stats, not page-specific)
        by_reviewer_team: dict[str, int] = {}
        by_pr_team: dict[str, int] = {}

        for row in cross_team_rows:
            # Count by reviewer team
            reviewer_team_key = row["reviewer_team"] or "unknown"
            by_reviewer_team[reviewer_team_key] = by_reviewer_team.get(reviewer_team_key, 0) + 1

            # Count by PR team
            pr_team_key = row["pr_sig_label"]
            by_pr_team[pr_team_key] = by_pr_team.get(pr_team_key, 0) + 1

        # Calculate pagination metadata
        pagination_metadata = format_pagination_metadata(total_count, page, page_size)
        pagination: PaginationInfo = PaginationInfo(
            total=pagination_metadata["total"],
            page=pagination_metadata["page"],
            page_size=pagination_metadata["page_size"],
            total_pages=pagination_metadata["total_pages"],
            has_next=pagination_metadata["has_next"],
            has_prev=pagination_metadata["has_prev"],
        )

        # Build response
        return CrossTeamResponse(
            data=data,
            summary=CrossTeamSummary(
                total_cross_team_reviews=total_count,
                by_reviewer_team=by_reviewer_team,
                by_pr_team=by_pr_team,
            ),
            pagination=pagination,
        )
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
