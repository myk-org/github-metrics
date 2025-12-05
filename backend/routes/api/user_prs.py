"""API routes for user pull requests."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.utils.contributor_queries import (
    ContributorRole,
    get_pr_creators_count_query,
    get_pr_creators_cte,
    get_pr_merged_status_cte,
    get_role_base_conditions,
)
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams
from backend.utils.response_formatters import format_paginated_response

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.user_prs")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/user-prs", operation_id="get_user_pull_requests")
async def get_user_pull_requests(
    users: Annotated[
        list[str] | None, Query(description="GitHub usernames (optional - shows all PRs if not specified)")
    ] = None,
    exclude_users: Annotated[list[str] | None, Query(description="Exclude users from results")] = None,
    role: str | None = Query(
        None,
        description=(
            "User role filter: pr_creators (author), pr_reviewers (reviewer), "
            "pr_approvers (approved), pr_lgtm (lgtm label)"
        ),
    ),
    repositories: Annotated[list[str] | None, Query(description="Filter by repositories (org/repo)")] = None,
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, description="Items per page"),
) -> dict[str, Any]:
    """Get pull requests with optional user and role filtering.

    Retrieves pull requests with pagination. Can show all PRs or filter by user and their role.
    Includes detailed commit information for each PR. Supports filtering by repository
    and time range.

    **Primary Use Cases:**
    - View all PRs across repositories with pagination
    - Filter PRs by specific user to track contributions
    - Filter by user role (creator, reviewer, approver, LGTM)
    - Analyze commit patterns per PR
    - Monitor PR lifecycle (created, merged, closed)
    - Filter PR activity by repository or time period

    **Parameters:**
    - `users` (list[str], optional): GitHub usernames to filter by (shows all PRs if not specified)
    - `exclude_users` (list[str], optional): Exclude users from results
    - `role` (str, optional): Filter by user role:
        - `pr_creators`: PRs created by the users
        - `pr_reviewers`: PRs reviewed by the users
        - `pr_approvers`: PRs approved by the users
        - `pr_lgtm`: PRs where users added LGTM label
    - `repositories` (list[str], optional): Filter by specific repositories (format: org/repo)
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `page` (int, optional): Page number for pagination (default: 1)
    - `page_size` (int, optional): Items per page (default: 10)

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

    # Validate role parameter
    valid_roles = [r.value for r in ContributorRole]
    if role and role not in valid_roles:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}",
        )

    # Convert role string to enum
    role_enum = ContributorRole(role) if role else None

    # Build queries based on role
    # For label-based and review-based roles, we query the events directly and JOIN to get PR details
    # This ensures time filters apply to the event (review/label), not the PR creation time
    params = QueryParams()

    if role_enum in (ContributorRole.PR_APPROVERS, ContributorRole.PR_LGTM, ContributorRole.PR_REVIEWERS):
        # For event-based roles: query events, then JOIN to get PR details
        # Build event filters
        event_filters = [get_role_base_conditions(role_enum)]

        if users:
            users_param = params.add(users)
            # For label-based roles, check SUBSTRING result; for other roles, check field directly
            if role_enum in (ContributorRole.PR_APPROVERS, ContributorRole.PR_LGTM):
                # For label roles: SUBSTRING(label_name FROM N) = ANY(array)
                label_offset = 10 if role_enum == ContributorRole.PR_APPROVERS else 6
                event_filters.append(f"SUBSTRING(events.label_name FROM {label_offset}) = ANY({users_param})")
            else:
                # For PR_REVIEWERS: sender = ANY(array)
                event_filters.append(f"events.sender = ANY({users_param})")

        if exclude_users:
            exclude_users_param = params.add(exclude_users)
            # Same logic for exclude
            if role_enum in (ContributorRole.PR_APPROVERS, ContributorRole.PR_LGTM):
                label_offset = 10 if role_enum == ContributorRole.PR_APPROVERS else 6
                event_filters.append(f"SUBSTRING(events.label_name FROM {label_offset}) != ALL({exclude_users_param})")
            else:
                event_filters.append(f"events.sender != ALL({exclude_users_param})")

        if start_datetime:
            event_filters.append(f"events.created_at >= {params.add(start_datetime)}")

        if end_datetime:
            event_filters.append(f"events.created_at <= {params.add(end_datetime)}")

        if repositories:
            repos_param = params.add(repositories)
            event_filters.append(f"events.repository = ANY({repos_param})")

        event_where_clause = " AND ".join(event_filters)

        # Count query: count distinct PRs from matching events with EXISTS to ensure PR data exists
        count_query = f"""
            WITH matching_events AS (
                SELECT DISTINCT events.repository, events.pr_number
                FROM webhooks events
                WHERE {event_where_clause}
                  AND events.pr_number IS NOT NULL
            )
            SELECT COUNT(*) as total
            FROM matching_events
            WHERE EXISTS (
                SELECT 1 FROM webhooks pr_data
                WHERE pr_data.repository = matching_events.repository
                  AND pr_data.pr_number = matching_events.pr_number
                  AND pr_data.pr_number IS NOT NULL
            )
        """

        # Mark pagination start before adding pagination parameters
        params.mark_pagination_start()
        # Add pagination parameters
        limit_placeholder = params.add(page_size)
        offset_placeholder = params.add((page - 1) * page_size)

        # Data query: JOIN events with PR details from any event with pr_number
        # Extract PR details using COALESCE across all possible payload locations:
        # - pr_* indexed columns (fastest)
        # - payload->'pull_request' (pull_request, pull_request_review, pull_request_review_comment events)
        # - payload->'issue' (issue_comment events)
        data_query = f"""
            WITH matching_events AS (
                SELECT DISTINCT events.repository, events.pr_number
                FROM webhooks events
                WHERE {event_where_clause}
                  AND events.pr_number IS NOT NULL
            ),
            {get_pr_merged_status_cte()}
            SELECT DISTINCT ON (pr_data.repository, pr_data.pr_number)
                pr_data.pr_number,
                COALESCE(
                    pr_data.pr_title,
                    pr_data.payload->'pull_request'->>'title',
                    pr_data.payload->'issue'->>'title'
                ) as title,
                COALESCE(
                    pr_data.pr_author,
                    pr_data.payload->'pull_request'->'user'->>'login',
                    pr_data.payload->'issue'->'user'->>'login'
                ) as owner,
                pr_data.repository,
                COALESCE(
                    pr_data.pr_state,
                    pr_data.payload->'pull_request'->>'state',
                    pr_data.payload->'issue'->>'state'
                ) as state,
                COALESCE(pms.merged, false) as merged,
                COALESCE(
                    pr_data.pr_html_url,
                    pr_data.payload->'pull_request'->>'html_url',
                    pr_data.payload->'issue'->>'html_url'
                ) as url,
                COALESCE(
                    pr_data.payload->'pull_request'->>'created_at',
                    pr_data.payload->'issue'->>'created_at'
                ) as created_at,
                COALESCE(
                    pr_data.payload->'pull_request'->>'updated_at',
                    pr_data.payload->'issue'->>'updated_at'
                ) as updated_at,
                COALESCE(pr_data.pr_commits_count, 0) as commits_count,
                pr_data.payload->'pull_request'->'head'->>'sha' as head_sha
            FROM matching_events
            INNER JOIN webhooks pr_data
                ON pr_data.repository = matching_events.repository
                AND pr_data.pr_number = matching_events.pr_number
                AND pr_data.pr_number IS NOT NULL
            LEFT JOIN pr_merged_status pms
                ON pms.repository = pr_data.repository
                AND pms.pr_number = pr_data.pr_number
            ORDER BY pr_data.repository, pr_data.pr_number DESC, pr_data.created_at DESC
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """
    else:
        # For PR creators (or no role): use shared query builders
        if role_enum == ContributorRole.PR_CREATORS:
            # Build time and repository filters
            time_filter = ""
            if start_datetime:
                time_filter += f" AND created_at >= {params.add(start_datetime)}"
            if end_datetime:
                time_filter += f" AND created_at <= {params.add(end_datetime)}"

            repository_filter = ""
            if repositories:
                repos_param = params.add(repositories)
                repository_filter = f" AND repository = ANY({repos_param})"

            # User filters for pr_creator in CTEs
            user_filter = ""
            if users:
                user_filter = f" AND pr_creator = ANY({params.add(users)})"

            exclude_user_filter = ""
            if exclude_users:
                exclude_user_filter = f" AND pr_creator != ALL({params.add(exclude_users)})"

            # Count query - use shared function
            count_query = get_pr_creators_count_query(time_filter, repository_filter, user_filter + exclude_user_filter)

            # Mark pagination start before adding pagination parameters
            params.mark_pagination_start()
            # Add pagination parameters
            limit_placeholder = params.add(page_size)
            offset_placeholder = params.add((page - 1) * page_size)

            # Data query - use pr_creators CTE then JOIN to get PR details
            # Extract PR details from any event with pr_number using COALESCE
            cte = get_pr_creators_cte(time_filter, repository_filter)
            data_query = f"""
                WITH {cte},
                {get_pr_merged_status_cte()}
                SELECT DISTINCT ON (pr_data.repository, pr_data.pr_number)
                    pr_data.pr_number,
                    COALESCE(
                        pr_data.pr_title,
                        pr_data.payload->'pull_request'->>'title',
                        pr_data.payload->'issue'->>'title'
                    ) as title,
                    pc.pr_creator as owner,
                    pr_data.repository,
                    COALESCE(
                        pr_data.pr_state,
                        pr_data.payload->'pull_request'->>'state',
                        pr_data.payload->'issue'->>'state'
                    ) as state,
                    COALESCE(pms.merged, false) as merged,
                    COALESCE(
                        pr_data.pr_html_url,
                        pr_data.payload->'pull_request'->>'html_url',
                        pr_data.payload->'issue'->>'html_url'
                    ) as url,
                    COALESCE(
                        pr_data.payload->'pull_request'->>'created_at',
                        pr_data.payload->'issue'->>'created_at'
                    ) as created_at,
                    COALESCE(
                        pr_data.payload->'pull_request'->>'updated_at',
                        pr_data.payload->'issue'->>'updated_at'
                    ) as updated_at,
                    COALESCE(pr_data.pr_commits_count, 0) as commits_count,
                    pr_data.payload->'pull_request'->'head'->>'sha' as head_sha
                FROM pr_creators pc
                INNER JOIN webhooks pr_data
                    ON pr_data.repository = pc.repository
                    AND pr_data.pr_number = pc.pr_number
                    AND pr_data.pr_number IS NOT NULL
                LEFT JOIN pr_merged_status pms
                    ON pms.repository = pr_data.repository
                    AND pms.pr_number = pr_data.pr_number
                WHERE pc.pr_creator IS NOT NULL{user_filter}{exclude_user_filter}
                ORDER BY pr_data.repository, pr_data.pr_number DESC, pr_data.created_at DESC
                LIMIT {limit_placeholder} OFFSET {offset_placeholder}
            """
        else:
            # No role specified - filter by PR author only
            filters = []

            if users:
                users_placeholder = params.add(users)
                filters.append(f"pr_author = ANY({users_placeholder})")

            if exclude_users:
                exclude_users_placeholder = params.add(exclude_users)
                filters.append(f"pr_author != ALL({exclude_users_placeholder})")

            if start_datetime:
                filters.append(f"created_at >= {params.add(start_datetime)}")

            if end_datetime:
                filters.append(f"created_at <= {params.add(end_datetime)}")

            if repositories:
                repos_param = params.add(repositories)
                filters.append(f"repository = ANY({repos_param})")

            where_clause = " AND ".join(filters) if filters else "1=1"

            # Count query
            count_query = f"""
                SELECT COUNT(DISTINCT pr_number) as total
                FROM webhooks
                WHERE event_type = 'pull_request'
                  AND pr_number IS NOT NULL
                  AND {where_clause}
            """

            # Mark pagination start before adding pagination parameters
            params.mark_pagination_start()
            # Add pagination parameters
            limit_placeholder = params.add(page_size)
            offset_placeholder = params.add((page - 1) * page_size)

            # Data query
            data_query = f"""
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
                  AND {where_clause}
                ORDER BY repository, pr_number DESC, webhooks.created_at DESC
                LIMIT {limit_placeholder} OFFSET {offset_placeholder}
            """

    try:
        # Get params for count query (without LIMIT/OFFSET)
        count_params = params.get_params_excluding_pagination()
        # Get all params for data query
        all_params = params.get_params()

        # Execute count and data queries in parallel
        count_result, pr_rows = await asyncio.gather(
            db_manager.fetchrow(count_query, *count_params),
            db_manager.fetch(data_query, *all_params),
        )

        total = count_result["total"] if count_result else 0

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

        return format_paginated_response(prs, total, page, page_size)
    except HTTPException:
        raise
    except asyncio.CancelledError:
        LOGGER.debug("User pull requests request was cancelled")
        raise  # Re-raise directly, let FastAPI handle
    except Exception as ex:
        LOGGER.exception("Failed to fetch user pull requests from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user pull requests",
        ) from ex
