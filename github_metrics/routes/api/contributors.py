"""API routes for contributor statistics."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.contributor_queries import get_pr_creators_count_query, get_pr_creators_data_query
from github_metrics.utils.datetime_utils import parse_datetime_string
from github_metrics.utils.query_builders import QueryParams, build_repository_filter, build_time_filter
from github_metrics.utils.response_formatters import format_pagination_metadata

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.contributors")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/contributors", operation_id="get_metrics_contributors")
async def get_metrics_contributors(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    users: Annotated[list[str] | None, Query(description="Filter by usernames (include)")] = None,
    exclude_users: Annotated[list[str] | None, Query(description="Exclude users from results")] = None,
    repositories: Annotated[list[str] | None, Query(description="Filter by repositories (org/repo format)")] = None,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, description="Items per page"),
) -> dict[str, Any]:
    """Get PR contributors statistics (creators, reviewers, approvers, LGTM).

    Analyzes webhook payloads to extract contributor activity including PR creation,
    code review, approval, and LGTM metrics. Essential for understanding team contributions
    and identifying active contributors.

    **Primary Use Cases:**
    - Track who is creating PRs and how many
    - Monitor code review participation
    - Identify approval patterns and bottlenecks
    - Track LGTM activity separate from approvals
    - Measure team collaboration and engagement
    - Generate contributor leaderboards

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `users` (list[str], optional): Filter by usernames to include
    - `exclude_users` (list[str], optional): Exclude users from results
    - `repositories` (list[str], optional): Filter by repositories (org/repo format)
    - `page` (int, default=1): Page number (1-indexed)
    - `page_size` (int, default=10): Items per page

    **Pagination:**
    - Each category (pr_creators, pr_reviewers, pr_approvers, pr_lgtm) includes pagination metadata
    - `total`: Total number of contributors in this category
    - `total_pages`: Total number of pages
    - `has_next`: Whether there's a next page
    - `has_prev`: Whether there's a previous page

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-31T23:59:59Z"
      },
      "pr_creators": {
        "data": [
          {
            "user": "john-doe",
            "total_prs": 45,
            "merged_prs": 42,
            "closed_prs": 3,
            "avg_commits_per_pr": 3.0
          }
        ],
        "pagination": {
          "total": 150,
          "page": 1,
          "page_size": 10,
          "total_pages": 15,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_reviewers": {
        "data": [
          {
            "user": "jane-smith",
            "total_reviews": 78,
            "prs_reviewed": 65,
            "avg_reviews_per_pr": 1.2
          }
        ],
        "pagination": {
          "total": 120,
          "page": 1,
          "page_size": 10,
          "total_pages": 12,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_approvers": {
        "data": [
          {
            "user": "bob-wilson",
            "total_approvals": 56,
            "prs_approved": 54
          }
        ],
        "pagination": {
          "total": 95,
          "page": 1,
          "page_size": 10,
          "total_pages": 10,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_lgtm": {
        "data": [
          {
            "user": "alice-jones",
            "total_lgtm": 42,
            "prs_lgtm": 40
          }
        ],
        "pagination": {
          "total": 78,
          "page": 1,
          "page_size": 10,
          "total_pages": 8,
          "has_next": true,
          "has_prev": false
        }
      }
    }
    ```

    **Notes:**
    - PR Approvers: Tracks /approve commands (approved-<username> labels)
    - PR LGTM: Tracks /lgtm commands (lgtm-<username> labels)
    - LGTM is separate from approvals in this workflow

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

    # Build category-specific user filters to align with per-category "user" semantics
    # NOTE: These role definitions are the SOURCE OF TRUTH and are mirrored in:
    #       github_metrics/utils/contributor_queries.py (ROLE_CONFIGS)
    # PR Creators: user = pr_author (extracted at insert-time from payload)
    # PR Reviewers: user = sender (reviewer who submitted the review)
    # PR Approvers: user = SUBSTRING(label_name FROM 10) where label_name LIKE 'approved-%'
    # PR LGTM: user = SUBSTRING(label_name FROM 6) where label_name LIKE 'lgtm-%'
    # Note: pr_author column is used for PR creators, reviewers use sender column
    user_filter_reviewers = ""
    user_filter_approvers = ""
    user_filter_lgtm = ""
    user_filter_creators = ""

    if users:
        users_param = params.add(users)

        # PR Creators: filter on pr_creator
        user_filter_creators = f" AND pr_creator = ANY({users_param})"
        # PR Reviewers: filter on sender
        user_filter_reviewers = f" AND sender = ANY({users_param})"
        # PR Approvers: filter using SUBSTRING result in array
        user_filter_approvers = f" AND SUBSTRING(label_name FROM 10) = ANY({users_param})"
        # PR LGTM: filter using SUBSTRING result in array
        user_filter_lgtm = f" AND SUBSTRING(label_name FROM 6) = ANY({users_param})"

    # Build exclude user filters
    exclude_user_filter_reviewers = ""
    exclude_user_filter_approvers = ""
    exclude_user_filter_lgtm = ""
    exclude_user_filter_creators = ""

    if exclude_users:
        exclude_users_param = params.add(exclude_users)

        # PR Creators: exclude pr_creator
        exclude_user_filter_creators = f" AND pr_creator != ALL({exclude_users_param})"
        # PR Reviewers: exclude sender
        exclude_user_filter_reviewers = f" AND sender != ALL({exclude_users_param})"
        # PR Approvers: exclude using SUBSTRING result
        exclude_user_filter_approvers = f" AND SUBSTRING(label_name FROM 10) != ALL({exclude_users_param})"
        # PR LGTM: exclude using SUBSTRING result
        exclude_user_filter_lgtm = f" AND SUBSTRING(label_name FROM 6) != ALL({exclude_users_param})"

    # Mark pagination start before adding pagination parameters
    params.mark_pagination_start()
    # Add pagination parameters and use placeholders directly
    page_size_placeholder = params.add(page_size)
    offset_placeholder = params.add((page - 1) * page_size)

    # Count query for PR Creators - use shared function
    pr_creators_count_query = get_pr_creators_count_query(
        time_filter, repository_filter, user_filter_creators + exclude_user_filter_creators
    )

    # Query PR Creators - use shared function
    pr_creators_query = get_pr_creators_data_query(
        time_filter,
        repository_filter,
        user_filter_creators + exclude_user_filter_creators,
        page_size_placeholder,
        offset_placeholder,
    )

    # Count query for PR Reviewers
    pr_reviewers_count_query = (
        """
        SELECT COUNT(DISTINCT sender) as total
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND action = 'submitted'
          AND sender IS DISTINCT FROM pr_author
          """
        + time_filter
        + user_filter_reviewers
        + exclude_user_filter_reviewers
        + repository_filter
    )

    # Query PR Reviewers (from pull_request_review events)
    pr_reviewers_query = (
        """
        SELECT
            sender as user,
            COUNT(*) as total_reviews,
            COUNT(DISTINCT pr_number) as prs_reviewed
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND action = 'submitted'
          AND sender IS DISTINCT FROM pr_author
          """
        + time_filter
        + user_filter_reviewers
        + exclude_user_filter_reviewers
        + repository_filter
        + f"""
        GROUP BY sender
        ORDER BY total_reviews DESC
        LIMIT {page_size_placeholder} OFFSET {offset_placeholder}
        """
    )

    # Count query for PR Approvers
    pr_approvers_count_query = (
        """
        SELECT COUNT(DISTINCT SUBSTRING(label_name FROM 10)) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND label_name LIKE 'approved-%'
          """
        + time_filter
        + user_filter_approvers
        + exclude_user_filter_approvers
        + repository_filter
    )

    # Query PR Approvers (from pull_request labeled events with 'approved-' prefix only)
    # Custom approval workflow: /approve comment triggers 'approved-<username>' label
    # Note: LGTM is separate from approval - tracked separately
    pr_approvers_query = (
        """
        SELECT
            SUBSTRING(label_name FROM 10) as user,
            COUNT(*) as total_approvals,
            COUNT(DISTINCT pr_number) as prs_approved
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND label_name LIKE 'approved-%'
          """
        + time_filter
        + user_filter_approvers
        + exclude_user_filter_approvers
        + repository_filter
        + f"""
        GROUP BY SUBSTRING(label_name FROM 10)
        ORDER BY total_approvals DESC
        LIMIT {page_size_placeholder} OFFSET {offset_placeholder}
        """
    )

    # Count query for LGTM
    pr_lgtm_count_query = (
        """
        SELECT COUNT(DISTINCT SUBSTRING(label_name FROM 6)) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND label_name LIKE 'lgtm-%'
          """
        + time_filter
        + user_filter_lgtm
        + exclude_user_filter_lgtm
        + repository_filter
    )

    # Query LGTM (from pull_request labeled events with 'lgtm-' prefix)
    # Custom LGTM workflow: /lgtm comment triggers 'lgtm-<username>' label
    pr_lgtm_query = (
        """
        SELECT
            SUBSTRING(label_name FROM 6) as user,
            COUNT(*) as total_lgtm,
            COUNT(DISTINCT pr_number) as prs_lgtm
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND label_name LIKE 'lgtm-%'
          """
        + time_filter
        + user_filter_lgtm
        + exclude_user_filter_lgtm
        + repository_filter
        + f"""
        GROUP BY SUBSTRING(label_name FROM 6)
        ORDER BY total_lgtm DESC
        LIMIT {page_size_placeholder} OFFSET {offset_placeholder}
        """
    )

    try:
        # Get params for count queries (without LIMIT/OFFSET)
        params_without_pagination = params.get_params_excluding_pagination()
        # Get all params for data queries
        all_params = params.get_params()

        # Execute all count queries in parallel (params without LIMIT/OFFSET)
        (
            pr_creators_total,
            pr_reviewers_total,
            pr_approvers_total,
            pr_lgtm_total,
        ) = await asyncio.gather(
            db_manager.fetchval(pr_creators_count_query, *params_without_pagination),
            db_manager.fetchval(pr_reviewers_count_query, *params_without_pagination),
            db_manager.fetchval(pr_approvers_count_query, *params_without_pagination),
            db_manager.fetchval(pr_lgtm_count_query, *params_without_pagination),
        )

        # Convert potentially None values to integers with safe defaults
        pr_creators_total = int(pr_creators_total or 0)
        pr_reviewers_total = int(pr_reviewers_total or 0)
        pr_approvers_total = int(pr_approvers_total or 0)
        pr_lgtm_total = int(pr_lgtm_total or 0)

        # Execute all data queries in parallel for better performance
        pr_creators_rows, pr_reviewers_rows, pr_approvers_rows, pr_lgtm_rows = await asyncio.gather(
            db_manager.fetch(pr_creators_query, *all_params),
            db_manager.fetch(pr_reviewers_query, *all_params),
            db_manager.fetch(pr_approvers_query, *all_params),
            db_manager.fetch(pr_lgtm_query, *all_params),
        )

        # Format PR creators
        pr_creators = [
            {
                "user": row["user"],
                "total_prs": row["total_prs"],
                "merged_prs": row["merged_prs"] or 0,
                "closed_prs": row["closed_prs"] or 0,
                "avg_commits_per_pr": round(row["avg_commits"] or 0, 1),
            }
            for row in pr_creators_rows
        ]

        # Format PR reviewers
        pr_reviewers = [
            {
                "user": row["user"],
                "total_reviews": row["total_reviews"],
                "prs_reviewed": row["prs_reviewed"],
                "avg_reviews_per_pr": round(row["total_reviews"] / max(row["prs_reviewed"], 1), 2),
            }
            for row in pr_reviewers_rows
        ]

        # Format PR approvers
        pr_approvers = [
            {
                "user": row["user"],
                "total_approvals": row["total_approvals"],
                "prs_approved": row["prs_approved"],
            }
            for row in pr_approvers_rows
        ]

        # Format LGTM
        pr_lgtm = [
            {
                "user": row["user"],
                "total_lgtm": row["total_lgtm"],
                "prs_lgtm": row["prs_lgtm"],
            }
            for row in pr_lgtm_rows
        ]

        # Calculate pagination metadata for each category using shared formatter
        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "pr_creators": {
                "data": pr_creators,
                "pagination": format_pagination_metadata(pr_creators_total, page, page_size),
            },
            "pr_reviewers": {
                "data": pr_reviewers,
                "pagination": format_pagination_metadata(pr_reviewers_total, page, page_size),
            },
            "pr_approvers": {
                "data": pr_approvers,
                "pagination": format_pagination_metadata(pr_approvers_total, page, page_size),
            },
            "pr_lgtm": {
                "data": pr_lgtm,
                "pagination": format_pagination_metadata(pr_lgtm_total, page, page_size),
            },
        }
    except asyncio.CancelledError:
        LOGGER.debug("Contributors metrics request was cancelled")
        raise  # Re-raise directly, let FastAPI handle
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch contributor metrics from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contributor metrics",
        ) from ex
