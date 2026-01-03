"""API routes for comment resolution time metrics."""

import asyncio
import json
from datetime import datetime
from typing import Annotated, TypedDict

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.utils.datetime_utils import parse_datetime_string
from backend.utils.query_builders import QueryParams, build_pagination_sql, build_repository_filter, build_time_filter
from backend.utils.response_formatters import PaginationMetadata, format_pagination_metadata

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.comment_resolution")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


class ThreadData(TypedDict):
    """Thread-level comment resolution data."""

    thread_node_id: str | None
    repository: str
    pr_number: int
    pr_title: str | None
    first_comment_at: str | None
    resolved_at: str | None
    resolution_time_hours: float | None
    time_to_first_response_hours: float | None
    comment_count: int
    resolver: str | None
    participants: list[str]
    file_path: str | None
    can_be_merged_at: str | None
    time_from_can_be_merged_hours: float | None


class RepositoryStats(TypedDict):
    """Repository-level comment resolution statistics."""

    repository: str
    avg_resolution_time_hours: float
    total_threads: int
    resolved_threads: int


class SummaryStats(TypedDict):
    """Global summary statistics for comment resolution."""

    avg_resolution_time_hours: float
    median_resolution_time_hours: float
    avg_time_to_first_response_hours: float
    avg_comments_per_thread: float
    total_threads_analyzed: int
    resolution_rate: float
    unresolved_outside_range: int


class CommentResolutionResponse(TypedDict):
    """Response structure for comment resolution time endpoint."""

    summary: SummaryStats
    by_repository: list[RepositoryStats]
    threads: list[ThreadData]
    pagination: PaginationMetadata


def _build_can_be_merged_cte(time_filter: str, repository_filter: str) -> str:
    """Build CTE for finding first can-be-merged event per head_sha.

    Supports two sources:
    1. check_run events with name 'can-be-merged' and conclusion 'success'
    2. pull_request events with action 'labeled' and label_name 'can-be-merged'

    Matches check_run events to PRs via head_sha instead of pull_requests array,
    since the pull_requests array is often empty in check_run webhooks.

    Args:
        time_filter: SQL WHERE clause for time filtering
        repository_filter: SQL WHERE clause for repository filtering

    Returns:
        SQL CTE string for can_be_merged query
    """
    return (
        """
    can_be_merged AS (
        -- Source 1: check_run events with can-be-merged check
        SELECT
            w.repository,
            w.payload->'check_run'->>'head_sha' as head_sha,
            MIN(w.created_at) as can_be_merged_at
        FROM webhooks w
        WHERE w.event_type = 'check_run'
          AND w.payload->'check_run'->>'name' = 'can-be-merged'
          AND w.payload->'check_run'->>'conclusion' = 'success'
          AND w.payload->'check_run'->>'head_sha' IS NOT NULL
          """
        + time_filter
        + repository_filter
        + """
        GROUP BY w.repository, w.payload->'check_run'->>'head_sha'

        UNION

        -- Source 2: pull_request events with can-be-merged label
        SELECT
            w.repository,
            w.payload->'pull_request'->'head'->>'sha' as head_sha,
            MIN(w.created_at) as can_be_merged_at
        FROM webhooks w
        WHERE w.event_type = 'pull_request'
          AND w.action = 'labeled'
          AND w.payload->'label'->>'name' = 'can-be-merged'
          AND w.payload->'pull_request'->'head'->>'sha' IS NOT NULL
          """
        + time_filter
        + repository_filter
        + """
        GROUP BY w.repository, w.payload->'pull_request'->'head'->>'sha'
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
) -> CommentResolutionResponse:
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
    - (Optional) Repository uses one of the following for correlation:
      - "can-be-merged" check run (check_run events)
      - "can-be-merged" label (pull_request labeled events)

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
        "resolution_rate": 85.5,
        "unresolved_outside_range": 12
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
          "pr_title": "Add new feature X",
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
    - `unresolved_outside_range`: Number of unresolved threads older than start_time (0 if no start_time filter)
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

    # Query 1: Get all thread events with extracted metadata
    threads_query = (
        """
        WITH """
        + _build_can_be_merged_cte(time_filter, repository_filter)
        + """,
        -- Collect head SHAs from multiple event types to match can-be-merged check runs to PRs
        -- Need 3 UNIONs because check_run webhooks often have empty pull_requests array
        pr_shas AS (
            -- Source 1: Pull request events (most reliable for PR number → SHA mapping)
            SELECT
                repository,
                pr_number,
                payload->'pull_request'->'head'->>'sha' as head_sha
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND pr_number IS NOT NULL
              AND payload->'pull_request'->'head'->>'sha' IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
            UNION
            -- Source 2: Check run events with PR associations (when pull_requests array is populated)
            SELECT
                w.repository,
                (pr_elem->>'number')::int as pr_number,
                w.payload->'check_run'->>'head_sha' as head_sha
            FROM webhooks w,
                 jsonb_array_elements(w.payload->'check_run'->'pull_requests') as pr_elem
            WHERE w.event_type = 'check_run'
              AND w.payload->'check_run'->>'head_sha' IS NOT NULL
              AND jsonb_array_length(w.payload->'check_run'->'pull_requests') > 0
              """
        + time_filter
        + repository_filter
        + """
            UNION
            -- Source 3: Check suite events with PR associations (alternative source for SHA → PR mapping)
            SELECT
                w.repository,
                (pr_elem->>'number')::int as pr_number,
                w.payload->'check_suite'->>'head_sha' as head_sha
            FROM webhooks w,
                 jsonb_array_elements(w.payload->'check_suite'->'pull_requests') as pr_elem
            WHERE w.event_type = 'check_suite'
              AND w.payload->'check_suite'->>'head_sha' IS NOT NULL
              AND jsonb_array_length(w.payload->'check_suite'->'pull_requests') > 0
              """
        + time_filter
        + repository_filter
        + """
        ),
        -- Match can-be-merged check runs to PRs via head_sha, get earliest success per PR
        pr_can_be_merged AS (
            SELECT DISTINCT ON (ps.repository, ps.pr_number)
                ps.repository,
                ps.pr_number,
                cm.can_be_merged_at
            FROM pr_shas ps
            JOIN can_be_merged cm ON ps.repository = cm.repository AND ps.head_sha = cm.head_sha
            ORDER BY ps.repository, ps.pr_number, cm.can_be_merged_at ASC
        ),
        -- Get PR titles (latest title for each PR)
        pr_titles AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                payload->'pull_request'->>'title' as pr_title
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND pr_number IS NOT NULL
              AND payload->'pull_request'->>'title' IS NOT NULL
            ORDER BY repository, pr_number, created_at DESC
        ),
        -- Extract thread root comments (first comment in each thread)
        -- These are comments with in_reply_to_id = NULL
        comment_threads AS (
            SELECT
                w.repository,
                w.pr_number,
                w.payload->'comment'->>'id' as root_comment_id,
                w.payload->'comment'->>'path' as file_path,
                (w.payload->'comment'->>'created_at')::timestamptz as first_comment_at,
                w.payload->'comment'->'user'->>'login' as first_commenter,
                w.created_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.action = 'created'
              AND w.payload->'comment'->>'in_reply_to_id' IS NULL
              AND w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        -- Count total comments per thread (replies + root comment)
        comment_counts AS (
            SELECT
                w.payload->'comment'->>'in_reply_to_id' as parent_id,
                COUNT(*) + 1 as comment_count
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.payload->'comment'->>'in_reply_to_id' IS NOT NULL
            GROUP BY w.payload->'comment'->>'in_reply_to_id'
        ),
        -- Collect all participants per thread (all users who commented in thread)
        comment_participants AS (
            SELECT
                COALESCE(w.payload->'comment'->>'in_reply_to_id', w.payload->'comment'->>'id') as thread_root_id,
                jsonb_agg(DISTINCT w.payload->'comment'->'user'->>'login') as participants
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.payload->'comment'->'user'->>'login' IS NOT NULL
            GROUP BY COALESCE(w.payload->'comment'->>'in_reply_to_id', w.payload->'comment'->>'id')
        ),
        -- Get latest resolution state per thread (resolved or unresolved)
        -- Uses DISTINCT ON to get most recent state for each thread
        latest_resolution_state AS (
            SELECT DISTINCT ON (repository, pr_number, root_comment_id)
                repository,
                pr_number,
                root_comment_id,
                thread_node_id,
                resolved_at,
                resolver,
                action
            FROM (
                SELECT
                    repository,
                    pr_number,
                    payload->'thread'->'comments'->0->>'id' as root_comment_id,
                    payload->'thread'->>'node_id' as thread_node_id,
                    CASE WHEN action = 'resolved' THEN created_at ELSE NULL END as resolved_at,
                    CASE WHEN action = 'resolved' THEN payload->'sender'->>'login' ELSE NULL END as resolver,
                    created_at,
                    action
                FROM webhooks
                WHERE event_type = 'pull_request_review_thread'
                  AND pr_number IS NOT NULL
                  """
        + time_filter
        + repository_filter
        + """
            ) sub
            ORDER BY repository, pr_number, root_comment_id, created_at DESC
        ),
        -- Find earliest reply per thread for response time calculation
        second_comments AS (
            SELECT
                w.payload->'comment'->>'in_reply_to_id' as thread_root_id,
                MIN((w.payload->'comment'->>'created_at')::timestamptz) as second_comment_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.payload->'comment'->>'in_reply_to_id' IS NOT NULL
            GROUP BY w.payload->'comment'->>'in_reply_to_id'
        ),
        -- Join all thread data: comments + resolution state + counts + participants
        all_threads AS (
            SELECT
                ct.repository,
                ct.pr_number,
                ct.root_comment_id,
                ct.file_path,
                ct.first_comment_at,
                ct.first_commenter,
                lrs.thread_node_id,
                lrs.resolved_at,
                lrs.resolver,
                CASE WHEN lrs.action = 'resolved' THEN true ELSE false END as is_resolved,
                COALESCE(cc.comment_count, 1) as comment_count,
                cp.participants,
                sc.second_comment_at
            FROM comment_threads ct
            LEFT JOIN latest_resolution_state lrs
                ON ct.repository = lrs.repository
                AND ct.pr_number = lrs.pr_number
                AND ct.root_comment_id = lrs.root_comment_id
            LEFT JOIN comment_counts cc ON ct.root_comment_id = cc.parent_id
            LEFT JOIN comment_participants cp ON ct.root_comment_id = cp.thread_root_id
            LEFT JOIN second_comments sc ON ct.root_comment_id = sc.thread_root_id
        ),
        -- Calculate resolution metrics and join with can-be-merged data
        threads_with_resolution AS (
            SELECT
                COALESCE(at.thread_node_id, 'comment-' || at.root_comment_id) as thread_node_id,
                at.repository,
                at.pr_number,
                pt.pr_title,
                at.file_path,
                at.first_comment_at,
                at.second_comment_at,
                CASE
                    WHEN at.second_comment_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (at.second_comment_at - at.first_comment_at)) / 3600
                    ELSE NULL
                END as time_to_first_response_hours,
                at.resolved_at,
                at.resolver,
                CASE
                    WHEN at.resolved_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (at.resolved_at - at.first_comment_at)) / 3600
                    ELSE NULL
                END as resolution_time_hours,
                at.comment_count,
                at.participants,
                pcm.can_be_merged_at,
                CASE
                    WHEN at.resolved_at IS NOT NULL AND pcm.can_be_merged_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (at.resolved_at - pcm.can_be_merged_at)) / 3600
                    ELSE NULL
                END as time_from_can_be_merged_hours
            FROM all_threads at
            LEFT JOIN pr_can_be_merged pcm ON at.repository = pcm.repository AND at.pr_number = pcm.pr_number
            LEFT JOIN pr_titles pt ON at.repository = pt.repository AND at.pr_number = pt.pr_number
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
        """
        + build_pagination_sql(base_params, page, page_size)
    )

    # Query 2: Get repository-level statistics
    repo_stats_query = (
        """
        WITH comment_threads AS (
            SELECT
                w.repository,
                w.pr_number,
                w.payload->'comment'->>'id' as root_comment_id,
                (w.payload->'comment'->>'created_at')::timestamptz as first_comment_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.action = 'created'
              AND w.payload->'comment'->>'in_reply_to_id' IS NULL
              AND w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        latest_resolution_state AS (
            SELECT DISTINCT ON (repository, pr_number, root_comment_id)
                repository,
                pr_number,
                root_comment_id,
                resolved_at,
                action
            FROM (
                SELECT
                    repository,
                    pr_number,
                    payload->'thread'->'comments'->0->>'id' as root_comment_id,
                    CASE WHEN action = 'resolved' THEN created_at ELSE NULL END as resolved_at,
                    created_at,
                    action
                FROM webhooks
                WHERE event_type = 'pull_request_review_thread'
                  AND pr_number IS NOT NULL
                  """
        + time_filter
        + repository_filter
        + """
            ) sub
            ORDER BY repository, pr_number, root_comment_id, created_at DESC
        ),
        all_threads AS (
            SELECT
                ct.repository,
                ct.root_comment_id,
                ct.first_comment_at,
                lrs.resolved_at,
                CASE WHEN lrs.action = 'resolved' THEN true ELSE false END as is_resolved
            FROM comment_threads ct
            LEFT JOIN latest_resolution_state lrs
                ON ct.repository = lrs.repository
                AND ct.pr_number = lrs.pr_number
                AND ct.root_comment_id = lrs.root_comment_id
        ),
        thread_counts AS (
            SELECT
                repository,
                COUNT(*) as total_threads,
                COUNT(CASE WHEN is_resolved THEN 1 END) as resolved_threads
            FROM all_threads
            GROUP BY repository
        ),
        resolution_times_calculated AS (
            SELECT
                repository,
                EXTRACT(EPOCH FROM (resolved_at - first_comment_at)) / 3600 as resolution_hours
            FROM all_threads
            WHERE resolved_at IS NOT NULL
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

    # Query 3: Calculate global summary statistics (avg/median) over ALL matching threads
    global_stats_query = (
        """
        WITH comment_threads AS (
            SELECT
                w.repository,
                w.pr_number,
                w.payload->'comment'->>'id' as root_comment_id,
                (w.payload->'comment'->>'created_at')::timestamptz as first_comment_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.action = 'created'
              AND w.payload->'comment'->>'in_reply_to_id' IS NULL
              AND w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        ),
        comment_counts AS (
            SELECT
                w.payload->'comment'->>'in_reply_to_id' as parent_id,
                COUNT(*) + 1 as comment_count
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.payload->'comment'->>'in_reply_to_id' IS NOT NULL
            GROUP BY w.payload->'comment'->>'in_reply_to_id'
        ),
        latest_resolution_state AS (
            SELECT DISTINCT ON (repository, pr_number, root_comment_id)
                repository,
                pr_number,
                root_comment_id,
                resolved_at,
                action
            FROM (
                SELECT
                    repository,
                    pr_number,
                    payload->'thread'->'comments'->0->>'id' as root_comment_id,
                    CASE WHEN action = 'resolved' THEN created_at ELSE NULL END as resolved_at,
                    created_at,
                    action
                FROM webhooks
                WHERE event_type = 'pull_request_review_thread'
                  AND pr_number IS NOT NULL
                  """
        + time_filter
        + repository_filter
        + """
            ) sub
            ORDER BY repository, pr_number, root_comment_id, created_at DESC
        ),
        second_comments AS (
            SELECT
                w.payload->'comment'->>'in_reply_to_id' as thread_root_id,
                MIN((w.payload->'comment'->>'created_at')::timestamptz) as second_comment_at
            FROM webhooks w
            WHERE w.event_type = 'pull_request_review_comment'
              AND w.payload->'comment'->>'in_reply_to_id' IS NOT NULL
            GROUP BY w.payload->'comment'->>'in_reply_to_id'
        ),
        all_threads AS (
            SELECT
                ct.root_comment_id,
                ct.first_comment_at,
                lrs.resolved_at,
                COALESCE(cc.comment_count, 1) as comment_count,
                sc.second_comment_at
            FROM comment_threads ct
            LEFT JOIN latest_resolution_state lrs
                ON ct.repository = lrs.repository
                AND ct.pr_number = lrs.pr_number
                AND ct.root_comment_id = lrs.root_comment_id
            LEFT JOIN comment_counts cc ON ct.root_comment_id = cc.parent_id
            LEFT JOIN second_comments sc ON ct.root_comment_id = sc.thread_root_id
        ),
        resolution_metrics AS (
            SELECT
                EXTRACT(EPOCH FROM (resolved_at - first_comment_at)) / 3600 as resolution_hours,
                EXTRACT(EPOCH FROM (second_comment_at - first_comment_at)) / 3600 as response_hours,
                comment_count
            FROM all_threads
        )
        SELECT
            percentile_cont(0.5) WITHIN GROUP (ORDER BY resolution_hours) as median_resolution_hours,
            AVG(resolution_hours) as avg_resolution_hours,
            AVG(response_hours) as avg_response_hours,
            AVG(comment_count) as avg_comments
        FROM resolution_metrics
    """
    )

    # Query 4: Count unresolved threads outside time range (only if start_time provided)
    unresolved_outside_query: str | None = None
    unresolved_outside_params: list[str | int | float | datetime | list[str] | None] = []
    if start_datetime is not None:
        # Build query to count unresolved threads before start_time
        unresolved_params = QueryParams()
        unresolved_repo_filter = build_repository_filter(unresolved_params, repositories)

        unresolved_outside_query = (
            """
            WITH comment_threads AS (
                SELECT
                    w.repository,
                    w.pr_number,
                    w.payload->'comment'->>'id' as root_comment_id,
                    (w.payload->'comment'->>'created_at')::timestamptz as first_comment_at
                FROM webhooks w
                WHERE w.event_type = 'pull_request_review_comment'
                  AND w.action = 'created'
                  AND w.payload->'comment'->>'in_reply_to_id' IS NULL
                  AND w.pr_number IS NOT NULL
                  """
            + unresolved_repo_filter
            + """
            ),
            latest_resolution_state AS (
                SELECT DISTINCT ON (repository, pr_number, root_comment_id)
                    repository,
                    pr_number,
                    root_comment_id,
                    action
                FROM (
                    SELECT
                        repository,
                        pr_number,
                        payload->'thread'->'comments'->0->>'id' as root_comment_id,
                        created_at,
                        action
                    FROM webhooks
                    WHERE event_type = 'pull_request_review_thread'
                      AND pr_number IS NOT NULL
                      """
            + unresolved_repo_filter
            + """
                ) sub
                ORDER BY repository, pr_number, root_comment_id, created_at DESC
            ),
            all_threads AS (
                SELECT
                    ct.first_comment_at,
                    CASE WHEN lrs.action = 'resolved' THEN true ELSE false END as is_resolved
                FROM comment_threads ct
                LEFT JOIN latest_resolution_state lrs
                    ON ct.repository = lrs.repository
                    AND ct.pr_number = lrs.pr_number
                    AND ct.root_comment_id = lrs.root_comment_id
            )
            SELECT COUNT(*) as unresolved_outside_count
            FROM all_threads
            WHERE is_resolved = false
              AND first_comment_at < """
            + unresolved_params.add(start_datetime)
            + """
        """
        )
        unresolved_outside_params = unresolved_params.get_params()

    try:
        param_list = base_params.get_params()

        # Execute queries in parallel
        # Note: unresolved_outside_count is set in both branches to ensure it's always defined
        if unresolved_outside_query is not None:
            try:
                threads_rows, repo_stats_rows, global_stats_rows, unresolved_outside_rows = await asyncio.gather(
                    db_manager.fetch(threads_query, *param_list),
                    db_manager.fetch(repo_stats_query, *base_params.get_params_excluding_pagination()),
                    db_manager.fetch(global_stats_query, *base_params.get_params_excluding_pagination()),
                    db_manager.fetch(unresolved_outside_query, *unresolved_outside_params),
                )
            except Exception:
                LOGGER.exception(
                    "Failed to execute parallel queries "
                    "(threads_query, repo_stats_query, global_stats_query, unresolved_outside_query)"
                )
                raise
            unresolved_outside_count = (
                unresolved_outside_rows[0]["unresolved_outside_count"] if unresolved_outside_rows else 0
            )
        else:
            # No start_time filter, so no unresolved threads outside range
            try:
                threads_rows, repo_stats_rows, global_stats_rows = await asyncio.gather(
                    db_manager.fetch(threads_query, *param_list),
                    db_manager.fetch(repo_stats_query, *base_params.get_params_excluding_pagination()),
                    db_manager.fetch(global_stats_query, *base_params.get_params_excluding_pagination()),
                )
            except Exception:
                LOGGER.exception(
                    "Failed to execute parallel queries (threads_query, repo_stats_query, global_stats_query)"
                )
                raise
            unresolved_outside_count = 0

        # Extract total count from first row (or 0 if no rows)
        total_threads = threads_rows[0]["total_count"] if threads_rows else 0

        # Calculate totals from repo_stats (which has accurate counts across ALL threads)
        total_threads_from_stats = sum(row["total_threads"] for row in repo_stats_rows)
        resolved_count_from_stats = sum(row["resolved_threads"] for row in repo_stats_rows)

        # Extract global summary statistics from global_stats_query (calculated over ALL matching threads)
        global_stats = global_stats_rows[0] if global_stats_rows else {}

        # Use default of 0.0 for None, but preserve actual values (including negative values)
        avg_resolution_raw = global_stats.get("avg_resolution_hours")
        avg_resolution = round(float(avg_resolution_raw) if avg_resolution_raw is not None else 0.0, 1)

        median_resolution_raw = global_stats.get("median_resolution_hours")
        median_resolution = round(
            float(median_resolution_raw) if median_resolution_raw is not None else 0.0,
            1,
        )

        avg_response_raw = global_stats.get("avg_response_hours")
        avg_response = round(float(avg_response_raw) if avg_response_raw is not None else 0.0, 1)

        avg_comments_raw = global_stats.get("avg_comments")
        avg_comments = round(float(avg_comments_raw) if avg_comments_raw is not None else 0.0, 1)

        # Use accurate counts from repo_stats for resolution_rate
        resolution_rate = (
            round((resolved_count_from_stats / total_threads_from_stats * 100), 1)
            if total_threads_from_stats > 0
            else 0.0
        )

        # Helper function to parse participants field (handles both list and JSON string)
        def parse_participants(value: list | str | None) -> list[str]:
            """Parse participants field from database (handles JSONB array serialization)."""
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else []
                except (json.JSONDecodeError, TypeError):
                    return []
            return []

        # Format threads for response
        threads_list: list[ThreadData] = [
            {
                # COALESCE in query should prevent None, but preserve it for malformed test data
                "thread_node_id": row["thread_node_id"],
                "repository": row["repository"],
                "pr_number": row["pr_number"],
                "pr_title": row["pr_title"],
                "first_comment_at": row["first_comment_at"].isoformat() if row["first_comment_at"] else None,
                "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
                "resolution_time_hours": float(round(row["resolution_time_hours"], 1))
                if row["resolution_time_hours"] is not None
                else None,
                "time_to_first_response_hours": float(round(row["time_to_first_response_hours"], 1))
                if row["time_to_first_response_hours"] is not None
                else None,
                "comment_count": row["comment_count"],
                "resolver": row["resolver"],
                "participants": parse_participants(row["participants"]),
                "file_path": row["file_path"],
                "can_be_merged_at": row["can_be_merged_at"].isoformat() if row["can_be_merged_at"] else None,
                "time_from_can_be_merged_hours": float(round(row["time_from_can_be_merged_hours"], 1))
                if row["time_from_can_be_merged_hours"] is not None
                else None,
            }
            for row in threads_rows
        ]

        # Format repository stats
        by_repository: list[RepositoryStats] = [
            {
                "repository": row["repository"],
                "avg_resolution_time_hours": float(round(row["avg_resolution_time_hours"], 1)),
                "total_threads": row["total_threads"],
                "resolved_threads": row["resolved_threads"],
            }
            for row in repo_stats_rows
        ]

        # Calculate pagination metadata using shared utility
        pagination: PaginationMetadata = format_pagination_metadata(total_threads, page, page_size)

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
        summary: SummaryStats = {
            "avg_resolution_time_hours": avg_resolution,
            "median_resolution_time_hours": median_resolution,
            "avg_time_to_first_response_hours": avg_response,
            "avg_comments_per_thread": avg_comments,
            "total_threads_analyzed": total_threads,
            "resolution_rate": resolution_rate,
            "unresolved_outside_range": unresolved_outside_count,
        }

        response: CommentResolutionResponse = {
            "summary": summary,
            "by_repository": by_repository,
            "threads": threads_list,
            "pagination": pagination,
        }

        return response
