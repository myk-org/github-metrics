"""API routes for contributor statistics."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.contributors")

# Maximum pagination offset to prevent expensive deep queries
MAX_OFFSET = 10000

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/contributors", operation_id="get_metrics_contributors")
async def get_metrics_contributors(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    user: str | None = Query(default=None, description="Filter by username"),
    repository: str | None = Query(default=None, description="Filter by repository (org/repo format)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
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
    - `user` (str, optional): Filter by username
    - `repository` (str, optional): Filter by repository (org/repo format)
    - `page` (int, default=1): Page number (1-indexed)
    - `page_size` (int, default=10): Items per page (1-100)

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

    # Build filter clause with time, user, and repository filters
    time_filter = ""
    params: list[Any] = []
    param_count = 0

    if start_datetime:
        param_count += 1
        time_filter += " AND created_at >= $" + str(param_count)
        params.append(start_datetime)

    if end_datetime:
        param_count += 1
        time_filter += " AND created_at <= $" + str(param_count)
        params.append(end_datetime)

    # Add repository filter if provided
    repository_filter = ""
    if repository:
        param_count += 1
        repository_filter = " AND repository = $" + str(param_count)
        params.append(repository)

    # Build category-specific user filters to align with per-category "user" semantics
    # PR Creators: user = pr_author (extracted at insert-time from payload)
    # PR Reviewers: user = sender (reviewer who submitted the review)
    # PR Approvers: user = SUBSTRING(label_name FROM 10) where label_name LIKE 'approved-%'
    # PR LGTM: user = SUBSTRING(label_name FROM 6) where label_name LIKE 'lgtm-%'
    # Note: pr_author column is used for PR creators, reviewers use sender column
    user_filter_reviewers = ""
    user_filter_approvers = ""
    user_filter_lgtm = ""

    if user:
        param_count += 1
        user_param_idx = param_count
        params.append(user)

        # PR Reviewers: filter on sender (correct as-is)
        user_filter_reviewers = " AND sender = $" + str(user_param_idx)
        # PR Approvers: filter using label_name with prefix (index-friendly)
        user_filter_approvers = " AND label_name = 'approved-' || $" + str(user_param_idx)
        # PR LGTM: filter using label_name with prefix (index-friendly)
        user_filter_lgtm = " AND label_name = 'lgtm-' || $" + str(user_param_idx)

    # Calculate offset for pagination
    offset = (page - 1) * page_size
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )

    # Add page_size and offset to params
    param_count += 1
    page_size_param = param_count
    param_count += 1
    offset_param = param_count
    params.extend([page_size, offset])

    # Count query for PR Creators
    pr_creators_count_query = (
        """
        WITH pr_creators AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                CASE event_type
                    WHEN 'pull_request' THEN pr_author
                    WHEN 'pull_request_review' THEN pr_author
                    WHEN 'pull_request_review_comment' THEN pr_author
                    WHEN 'issue_comment' THEN COALESCE(
                        pr_author,
                        payload->'issue'->'user'->>'login'
                    )
                END as pr_creator
            FROM webhooks
            WHERE pr_number IS NOT NULL
              AND event_type IN (
                  'pull_request',
                  'pull_request_review',
                  'pull_request_review_comment',
                  'issue_comment'
              )
              """
        + time_filter
        + repository_filter
        + """
            ORDER BY repository, pr_number, created_at ASC
        )
        SELECT COUNT(DISTINCT pr_creator) as total
        FROM pr_creators
        WHERE pr_creator IS NOT NULL"""
        + (" AND pr_creator = $" + str(user_param_idx) if user else "")
    )

    # Query PR Creators (from any event with pr_number)
    pr_creators_query = (
        """
        WITH pr_creators AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                CASE event_type
                    WHEN 'pull_request' THEN pr_author
                    WHEN 'pull_request_review' THEN pr_author
                    WHEN 'pull_request_review_comment' THEN pr_author
                    WHEN 'issue_comment' THEN COALESCE(
                        pr_author,
                        payload->'issue'->'user'->>'login'
                    )
                END as pr_creator
            FROM webhooks
            WHERE pr_number IS NOT NULL
              AND event_type IN (
                  'pull_request',
                  'pull_request_review',
                  'pull_request_review_comment',
                  'issue_comment'
              )
              """
        + time_filter
        + repository_filter
        + """
            ORDER BY repository, pr_number, created_at ASC
        ),
        user_prs AS (
            SELECT
                pc.pr_creator,
                w.pr_number,
                COALESCE(w.pr_commits_count, 0) as commits,
                COALESCE(w.pr_merged, false) as is_merged,
                (w.pr_state = 'closed' AND COALESCE(w.pr_merged, false) = false) as is_closed
            FROM webhooks w
            INNER JOIN pr_creators pc ON w.repository = pc.repository AND w.pr_number = pc.pr_number
            WHERE w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        )
        SELECT
            pr_creator as user,
            COUNT(DISTINCT pr_number) as total_prs,
            COUNT(DISTINCT pr_number) FILTER (WHERE is_merged) as merged_prs,
            COUNT(DISTINCT pr_number) FILTER (WHERE is_closed) as closed_prs,
            ROUND(AVG(max_commits), 1) as avg_commits
        FROM (
            SELECT
                pr_creator,
                pr_number,
                MAX(commits) as max_commits,
                BOOL_OR(is_merged) as is_merged,
                BOOL_OR(is_closed) as is_closed
            FROM user_prs
            WHERE pr_creator IS NOT NULL
            GROUP BY pr_creator, pr_number
        ) pr_stats
        WHERE 1=1"""
        + (" AND pr_creator = $" + str(user_param_idx) if user else "")
        + """
        GROUP BY pr_creator
        ORDER BY total_prs DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
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
        + repository_filter
        + """
        GROUP BY sender
        ORDER BY total_reviews DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
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
        + repository_filter
        + """
        GROUP BY SUBSTRING(label_name FROM 10)
        ORDER BY total_approvals DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
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
        + repository_filter
        + """
        GROUP BY SUBSTRING(label_name FROM 6)
        ORDER BY total_lgtm DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
    )

    try:
        # Execute all count queries in parallel (params without LIMIT/OFFSET)
        params_without_pagination = params[:-2]
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
            db_manager.fetch(pr_creators_query, *params),
            db_manager.fetch(pr_reviewers_query, *params),
            db_manager.fetch(pr_approvers_query, *params),
            db_manager.fetch(pr_lgtm_query, *params),
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

        # Calculate pagination metadata for each category
        total_pages_creators = math.ceil(pr_creators_total / page_size) if pr_creators_total > 0 else 0
        total_pages_reviewers = math.ceil(pr_reviewers_total / page_size) if pr_reviewers_total > 0 else 0
        total_pages_approvers = math.ceil(pr_approvers_total / page_size) if pr_approvers_total > 0 else 0
        total_pages_lgtm = math.ceil(pr_lgtm_total / page_size) if pr_lgtm_total > 0 else 0

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "pr_creators": {
                "data": pr_creators,
                "pagination": {
                    "total": pr_creators_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_creators,
                    "has_next": page < total_pages_creators,
                    "has_prev": page > 1,
                },
            },
            "pr_reviewers": {
                "data": pr_reviewers,
                "pagination": {
                    "total": pr_reviewers_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_reviewers,
                    "has_next": page < total_pages_reviewers,
                    "has_prev": page > 1,
                },
            },
            "pr_approvers": {
                "data": pr_approvers,
                "pagination": {
                    "total": pr_approvers_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_approvers,
                    "has_next": page < total_pages_approvers,
                    "has_prev": page > 1,
                },
            },
            "pr_lgtm": {
                "data": pr_lgtm,
                "pagination": {
                    "total": pr_lgtm_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_lgtm,
                    "has_next": page < total_pages_lgtm,
                    "has_prev": page > 1,
                },
            },
        }
    except asyncio.CancelledError as ex:
        LOGGER.debug("Contributors metrics request was cancelled")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Request was cancelled",
        ) from ex
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch contributor metrics from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contributor metrics",
        ) from ex
