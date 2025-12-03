"""API routes for user pull requests."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.user_prs")

# Maximum pagination offset to prevent expensive deep queries
MAX_OFFSET = 10000

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/user-prs", operation_id="get_user_pull_requests")
async def get_user_pull_requests(
    user: str | None = Query(None, description="GitHub username (optional - shows all PRs if not specified)"),
    repository: str | None = Query(None, description="Filter by repository (org/repo)"),
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """Get pull requests with optional user filtering and commit details.

    Retrieves pull requests with pagination. Can show all PRs or filter by user.
    Includes detailed commit information for each PR. Supports filtering by repository
    and time range.

    **Primary Use Cases:**
    - View all PRs across repositories with pagination
    - Filter PRs by specific user to track contributions
    - Analyze commit patterns per PR
    - Monitor PR lifecycle (created, merged, closed)
    - Filter PR activity by repository or time period

    **Parameters:**
    - `user` (str, optional): GitHub username to filter by (shows all PRs if not specified)
    - `repository` (str, optional): Filter by specific repository (format: org/repo)
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `page` (int, optional): Page number for pagination (default: 1)
    - `page_size` (int, optional): Items per page, 1-100 (default: 10)

    **Return Structure:**
    ```json
    {
      "data": [
        {
          "number": 123,
          "title": "Add feature X",
          "owner": "username",
          "repository": "org/repo1",
          "state": "closed",
          "merged": true,
          "url": "https://github.com/org/repo1/pull/123",
          "created_at": "2024-11-20T10:00:00Z",
          "updated_at": "2024-11-21T15:30:00Z",
          "commits_count": 5,
          "head_sha": "abc123def456"  # pragma: allowlist secret
        }
      ],
      "pagination": {
        "total": 45,
        "page": 1,
        "page_size": 10,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false
      }
    }
    ```

    **Errors:**
    - 500: Database connection error or metrics server disabled
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    # Parse datetime strings
    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build filter clauses
    filters = []
    params: list[Any] = []
    param_count = 0

    # Add user filter if provided
    if user and user.strip():
        param_count += 1
        user_filter = "(pr_author = $" + str(param_count)
        user_filter += " OR sender = $" + str(param_count) + ")"
        filters.append(user_filter)
        params.append(user.strip())

    if start_datetime:
        param_count += 1
        filters.append("created_at >= $" + str(param_count))
        params.append(start_datetime)

    if end_datetime:
        param_count += 1
        filters.append("created_at <= $" + str(param_count))
        params.append(end_datetime)

    if repository:
        param_count += 1
        filters.append("repository = $" + str(param_count))
        params.append(repository)

    where_clause = " AND ".join(filters) if filters else "1=1"

    # Count total matching PRs
    count_query = (
        """
        SELECT COUNT(DISTINCT pr_number) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND pr_number IS NOT NULL
          AND """
        + where_clause
    )

    # Calculate pagination
    offset = (page - 1) * page_size
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )
    # Parameter indexing: limit and offset are added after filter params
    # count_query uses params[0:param_count], data_query uses params + [page_size, offset]
    param_count += 1
    limit_param_idx = param_count
    param_count += 1
    offset_param_idx = param_count

    # Query for PR data with pagination
    data_query = (
        """
        SELECT DISTINCT ON (repository, pr_number)
            pr_number,
            pr_title as title,
            pr_author as owner,
            repository,
            pr_state as state,
            COALESCE(pr_merged, false) as merged,
            pr_html_url as url,
            payload->'pull_request'->>'created_at' as created_at,
            payload->'pull_request'->>'updated_at' as updated_at,
            COALESCE(pr_commits_count, 0) as commits_count,
            payload->'pull_request'->'head'->>'sha' as head_sha
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND pr_number IS NOT NULL
          AND """
        + where_clause
        + """
        ORDER BY repository, pr_number DESC, webhooks.created_at DESC
        LIMIT $"""
        + str(limit_param_idx)
        + " OFFSET $"
        + str(offset_param_idx)
    )

    try:
        # Execute count and data queries in parallel
        count_result, pr_rows = await asyncio.gather(
            db_manager.fetchrow(count_query, *params),
            db_manager.fetch(data_query, *params, page_size, offset),
        )

        total = count_result["total"] if count_result else 0
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        # Format PR data
        prs = [
            {
                "number": row["pr_number"],
                "title": row["title"],
                "owner": row["owner"],
                "repository": row["repository"],
                "state": row["state"],
                "merged": row["merged"] or False,
                "url": row["url"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "commits_count": row["commits_count"] or 0,
                "head_sha": row["head_sha"],
            }
            for row in pr_rows
        ]

        return {
            "data": prs,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    except HTTPException:
        raise
    except asyncio.CancelledError:
        LOGGER.debug("User pull requests request was cancelled")
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch user pull requests from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user pull requests",
        ) from ex
