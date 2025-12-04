"""API routes for team dynamics and workload metrics."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string
from github_metrics.utils.query_builders import QueryParams, build_repository_filter, build_time_filter

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.team_dynamics")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


def calculate_gini_coefficient(values: list[int]) -> float:
    """Calculate Gini coefficient to measure workload inequality.

    The Gini coefficient measures inequality in a distribution:
    - 0.0 = perfect equality (everyone has the same workload)
    - 1.0 = perfect inequality (one person does everything)

    Args:
        values: List of workload counts (e.g., PRs per contributor)

    Returns:
        Gini coefficient (0.0 to 1.0)
    """
    if not values or len(values) == 1:
        return 0.0

    # Sort values in ascending order
    sorted_values = sorted(values)
    n = len(sorted_values)
    total = sum(sorted_values)

    if total == 0:
        return 0.0

    # Calculate Gini coefficient using standard formula
    # Gini = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    weighted_sum = sum((i + 1) * value for i, value in enumerate(sorted_values))
    gini = (2 * weighted_sum) / (n * total) - (n + 1) / n

    return round(gini, 3)


@router.get("/team-dynamics", operation_id="get_team_dynamics")
async def get_team_dynamics(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    repository: str | None = Query(default=None, description="Filter by repository (org/repo format)"),
    user: str | None = Query(default=None, description="Filter by user (username)"),
) -> dict[str, Any]:
    """Get team dynamics and workload distribution metrics.

    Analyzes team collaboration patterns, workload distribution, and review efficiency
    to identify bottlenecks and optimize team performance.

    **Primary Use Cases:**
    - Monitor workload distribution across team members
    - Identify review efficiency and bottlenecks
    - Detect approval delays and overloaded approvers
    - Balance workload across contributors
    - Track team collaboration patterns
    - Optimize review processes based on data

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format
      Default: No time filter (all-time stats)
    - `end_time` (str, optional): End of time range in ISO 8601 format
      Default: No time filter (up to current time)
    - `repository` (str, optional): Filter by repository (org/repo format)
    - `user` (str, optional): Filter by user (username)

    **Return Structure:**
    ```json
    {
      "workload": {
        "summary": {
          "total_contributors": 15,
          "avg_prs_per_contributor": 8.5,
          "top_contributor": {"user": "alice", "total_prs": 45},
          "workload_gini": 0.35
        },
        "by_contributor": [
          {
            "user": "alice",
            "prs_created": 45,
            "prs_reviewed": 120,
            "prs_approved": 85
          }
        ]
      },
      "review_efficiency": {
        "summary": {
          "avg_review_time_hours": 4.2,
          "median_review_time_hours": 2.5,
          "fastest_reviewer": {"user": "bob", "avg_hours": 1.2},
          "slowest_reviewer": {"user": "charlie", "avg_hours": 12.5}
        },
        "by_reviewer": [
          {
            "user": "bob",
            "avg_review_time_hours": 1.2,
            "median_review_time_hours": 0.8,
            "total_reviews": 150
          }
        ]
      },
      "bottlenecks": {
        "alerts": [
          {
            "approver": "charlie",
            "avg_approval_hours": 50.5,
            "team_pending_count": 5,
            "severity": "critical"
          }
        ],
        "by_approver": [
          {
            "approver": "charlie",
            "avg_approval_hours": 48.5,
            "total_approvals": 25
          }
        ]
      }
    }
    ```

    **Metrics Explained:**
    - `total_contributors`: Number of unique contributors in the time range
    - `avg_prs_per_contributor`: Average PRs created per contributor
    - `top_contributor`: User with most PRs created
    - `workload_gini`: Gini coefficient (0=equal distribution, 1=one person does everything)
    - `avg_review_time_hours`: Average time from PR creation to first review
    - `median_review_time_hours`: Median review time (less affected by outliers)
    - `fastest_reviewer`: User with lowest average review time
    - `slowest_reviewer`: User with highest average review time
    - `avg_approval_hours`: Average time from PR creation to approval (per-approver metric)
    - `team_pending_count`: Total number of PRs currently awaiting approval (team-wide metric)
    - `severity`: Alert severity based on `avg_approval_hours` only ("critical" if >48h, "warning" if >24h)

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

    # Build base filter parameters
    params = QueryParams()
    time_filter = build_time_filter(params, start_datetime, end_datetime)
    repository_filter = build_repository_filter(params, repository)

    # Build user filter
    user_filter_pr_author = ""
    user_filter_sender = ""
    user_filter_label = ""
    if user:
        user_param = params.add(user)
        user_filter_pr_author = f" AND pr_author = {user_param}"
        user_filter_sender = f" AND sender = {user_param}"
        user_filter_label = f" AND SUBSTRING(label_name FROM 10) = {user_param}"

    # Query 1: Workload distribution by contributor
    workload_query = (
        """
        WITH pr_creators AS (
            SELECT
                pr_author as user,
                COUNT(DISTINCT pr_number) as prs_created
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND pr_author IS NOT NULL
              """
        + time_filter
        + repository_filter
        + user_filter_pr_author
        + """
            GROUP BY pr_author
        ),
        pr_reviewers AS (
            SELECT
                sender as user,
                COUNT(*) as prs_reviewed
            FROM webhooks
            WHERE event_type = 'pull_request_review'
              AND action = 'submitted'
              AND sender IS DISTINCT FROM pr_author
              """
        + time_filter
        + repository_filter
        + user_filter_sender
        + """
            GROUP BY sender
        ),
        pr_approvers AS (
            SELECT
                SUBSTRING(label_name FROM 10) as user,
                COUNT(DISTINCT pr_number) as prs_approved
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'labeled'
              AND label_name LIKE 'approved-%'
              """
        + time_filter
        + repository_filter
        + user_filter_label
        + """
            GROUP BY SUBSTRING(label_name FROM 10)
        )
        SELECT
            COALESCE(pc.user, pr.user, pa.user) as user,
            COALESCE(pc.prs_created, 0) as prs_created,
            COALESCE(pr.prs_reviewed, 0) as prs_reviewed,
            COALESCE(pa.prs_approved, 0) as prs_approved
        FROM pr_creators pc
        FULL OUTER JOIN pr_reviewers pr ON pc.user = pr.user
        FULL OUTER JOIN pr_approvers pa ON COALESCE(pc.user, pr.user) = pa.user
        WHERE COALESCE(pc.user, pr.user, pa.user) IS NOT NULL
        ORDER BY prs_created DESC, prs_reviewed DESC
    """
    )

    # Query 2: Review efficiency (time to first review)
    review_efficiency_query = (
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
        review_times AS (
            SELECT
                w.sender as reviewer,
                EXTRACT(EPOCH FROM (w.created_at - po.opened_at)) / 3600 as hours_to_review
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request_review'
              AND w.action = 'submitted'
              AND w.sender IS DISTINCT FROM w.pr_author
              AND w.created_at >= po.opened_at
              """
        + user_filter_sender.replace("sender", "w.sender")
        + """
        ),
        overall_median AS (
            SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY hours_to_review)::numeric, 1) as median_hours
            FROM review_times
        )
        SELECT
            reviewer as user,
            ROUND(AVG(hours_to_review)::numeric, 1) as avg_review_time_hours,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY hours_to_review)::numeric, 1) as median_review_time_hours,
            COUNT(*) as total_reviews,
            (SELECT median_hours FROM overall_median) as overall_median_hours
        FROM review_times
        WHERE reviewer IS NOT NULL
        GROUP BY reviewer
        ORDER BY avg_review_time_hours ASC
    """
    )

    # Query 3: Approval bottlenecks (time to approval)
    approval_bottleneck_query = (
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
        approval_times AS (
            SELECT
                SUBSTRING(w.label_name FROM 10) as approver,
                w.repository,
                w.pr_number,
                EXTRACT(EPOCH FROM (w.created_at - po.opened_at)) / 3600 as hours_to_approval
            FROM webhooks w
            INNER JOIN pr_opened po ON w.repository = po.repository AND w.pr_number = po.pr_number
            WHERE w.event_type = 'pull_request'
              AND w.action = 'labeled'
              AND w.label_name LIKE 'approved-%'
              AND w.created_at >= po.opened_at
              """
        + user_filter_label.replace("SUBSTRING(label_name FROM 10)", "SUBSTRING(w.label_name FROM 10)")
        + """
        )
        SELECT
            approver,
            ROUND(AVG(hours_to_approval)::numeric, 1) as avg_approval_hours,
            COUNT(*) as total_approvals
        FROM approval_times
        WHERE approver IS NOT NULL
        GROUP BY approver
        ORDER BY avg_approval_hours DESC
    """
    )

    # Query 4: Pending PRs awaiting approval (for bottleneck alerts)
    pending_prs_query = (
        """
        WITH latest_pr_state AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                pr_state
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + user_filter_pr_author
        + """
            ORDER BY repository, pr_number, created_at DESC
        ),
        approved_prs AS (
            SELECT DISTINCT repository, pr_number
            FROM webhooks
            WHERE event_type = 'pull_request'
              AND action = 'labeled'
              AND label_name LIKE 'approved-%'
              """
        + time_filter
        + repository_filter
        + user_filter_label
        + """
        )
        SELECT COUNT(*) as pending_count
        FROM latest_pr_state lps
        WHERE lps.pr_state = 'open'
          AND NOT EXISTS (
              SELECT 1 FROM approved_prs ap
              WHERE ap.repository = lps.repository
                AND ap.pr_number = lps.pr_number
          )
    """
    )

    try:
        param_list = params.get_params()

        # Execute all queries in parallel
        workload_rows, review_rows, approval_rows, pending_row = await asyncio.gather(
            db_manager.fetch(workload_query, *param_list),
            db_manager.fetch(review_efficiency_query, *param_list),
            db_manager.fetch(approval_bottleneck_query, *param_list),
            db_manager.fetchrow(pending_prs_query, *param_list),
        )

        # Process workload data
        workload_data = [
            {
                "user": row["user"],
                "prs_created": row["prs_created"],
                "prs_reviewed": row["prs_reviewed"],
                "prs_approved": row["prs_approved"],
            }
            for row in workload_rows
        ]

        # Calculate workload summary
        total_contributors = len(workload_data)
        total_prs = sum(row["prs_created"] for row in workload_data)
        avg_prs = round(total_prs / total_contributors, 1) if total_contributors > 0 else 0.0

        top_contributor = None
        if workload_data:
            top = max(workload_data, key=lambda x: x["prs_created"])
            top_contributor = {"user": top["user"], "total_prs": top["prs_created"]}

        # Calculate Gini coefficient for workload inequality
        pr_counts = [row["prs_created"] for row in workload_data]
        workload_gini = calculate_gini_coefficient(pr_counts)

        workload_summary = {
            "total_contributors": total_contributors,
            "avg_prs_per_contributor": avg_prs,
            "top_contributor": top_contributor,
            "workload_gini": workload_gini,
        }

        # Process review efficiency data
        review_data = [
            {
                "user": row["user"],
                "avg_review_time_hours": float(row["avg_review_time_hours"] or 0),
                "median_review_time_hours": float(row["median_review_time_hours"] or 0),
                "total_reviews": row["total_reviews"],
            }
            for row in review_rows
        ]

        # Calculate review efficiency summary
        avg_review_time = 0.0
        median_review_time = 0.0
        fastest_reviewer = None
        slowest_reviewer = None

        if review_data:
            # Note: avg_review_time is an unweighted average-of-averages (approximation).
            # For accurate aggregate statistics, use median_review_time which is computed
            # directly from the database using PERCENTILE_CONT(0.5).
            avg_review_time = round(sum(r["avg_review_time_hours"] for r in review_data) / len(review_data), 1)
            # Use proper aggregate median from database query
            median_review_time = float(review_rows[0]["overall_median_hours"] or 0) if review_rows else 0.0

            fastest = min(review_data, key=lambda x: x["avg_review_time_hours"])
            fastest_reviewer = {"user": fastest["user"], "avg_hours": fastest["avg_review_time_hours"]}

            slowest = max(review_data, key=lambda x: x["avg_review_time_hours"])
            slowest_reviewer = {"user": slowest["user"], "avg_hours": slowest["avg_review_time_hours"]}

        review_summary = {
            "avg_review_time_hours": avg_review_time,
            "median_review_time_hours": median_review_time,
            "fastest_reviewer": fastest_reviewer,
            "slowest_reviewer": slowest_reviewer,
        }

        # Process approval bottleneck data
        approval_data = [
            {
                "approver": row["approver"],
                "avg_approval_hours": float(row["avg_approval_hours"] or 0),
                "total_approvals": row["total_approvals"],
            }
            for row in approval_rows
        ]

        # Generate bottleneck alerts (based on approval time only)
        pending_count = pending_row["pending_count"] if pending_row else 0
        alerts = []

        for approver_data in approval_data:
            avg_hours = approver_data["avg_approval_hours"]

            # Severity based on approval time only
            # Critical: >48 hours
            # Warning: >24 hours
            if avg_hours > 48:
                severity = "critical"
            elif avg_hours > 24:
                severity = "warning"
            else:
                continue

            alerts.append({
                "approver": approver_data["approver"],
                "avg_approval_hours": avg_hours,
                "team_pending_count": pending_count,
                "severity": severity,
            })

        # Sort alerts: critical first (False < True), then by avg_approval_hours descending
        alerts.sort(key=lambda x: (x["severity"] != "critical", -x["avg_approval_hours"]))

    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch team dynamics metrics")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch team dynamics metrics",
        ) from ex
    else:
        return {
            "workload": {
                "summary": workload_summary,
                "by_contributor": workload_data,
            },
            "review_efficiency": {
                "summary": review_summary,
                "by_reviewer": review_data,
            },
            "bottlenecks": {
                "alerts": alerts,
                "by_approver": approval_data,
            },
        }
