"""Shared query builders for contributor metrics.

This module provides a single source of truth for role-based queries.
Both contributors.py and user_prs.py should use these definitions.
"""

from dataclasses import dataclass
from enum import Enum


class ContributorRole(Enum):
    """Contributor role types."""

    PR_CREATORS = "pr_creators"
    PR_REVIEWERS = "pr_reviewers"
    PR_APPROVERS = "pr_approvers"
    PR_LGTM = "pr_lgtm"


@dataclass
class RoleConfig:
    """Configuration for a contributor role."""

    event_type: str
    action: str | None  # None means no action filter
    label_pattern: str | None  # For label-based roles (approved-%, lgtm-%)
    user_field: str  # Which field contains the user (sender, pr_author, or label extraction)
    extra_conditions: str | None  # Additional WHERE conditions


# Role configurations - SINGLE SOURCE OF TRUTH
ROLE_CONFIGS: dict[ContributorRole, RoleConfig] = {
    ContributorRole.PR_CREATORS: RoleConfig(
        event_type="pull_request",
        action=None,
        label_pattern=None,
        user_field="pr_author",
        extra_conditions="pr_number IS NOT NULL",
    ),
    ContributorRole.PR_REVIEWERS: RoleConfig(
        event_type="pull_request_review",
        action="submitted",
        label_pattern=None,
        user_field="sender",
        extra_conditions="sender IS DISTINCT FROM pr_author",
    ),
    ContributorRole.PR_APPROVERS: RoleConfig(
        event_type="pull_request",
        action="labeled",
        label_pattern="approved-",  # User extracted: SUBSTRING(label_name FROM 10)
        user_field="label",  # Special: user is in label name
        extra_conditions=None,
    ),
    ContributorRole.PR_LGTM: RoleConfig(
        event_type="pull_request",
        action="labeled",
        label_pattern="lgtm-",  # User extracted: SUBSTRING(label_name FROM 6)
        user_field="label",  # Special: user is in label name
        extra_conditions=None,
    ),
}


def get_role_base_conditions(role: ContributorRole) -> str:
    """Get the base WHERE conditions for a role (without user filter).

    Note: Uses string interpolation with hardcoded enum values only.
    All user-supplied values MUST use parameterized queries via QueryParams.
    """
    config = ROLE_CONFIGS[role]
    conditions = [f"event_type = '{config.event_type}'"]

    if config.action:
        conditions.append(f"action = '{config.action}'")

    if config.label_pattern:
        conditions.append(f"label_name LIKE '{config.label_pattern}%'")

    if config.extra_conditions:
        conditions.append(config.extra_conditions)

    return " AND ".join(conditions)


def get_pr_creators_cte(time_filter: str = "", repository_filter: str = "") -> str:
    """Generate the pr_creators CTE for identifying PR authors.

    PR creators can be identified from any event with pr_number set:
    - pr_author field (available in most PR-related events)
    - payload->'pull_request'->'user'->>'login' (pull_request events)
    - payload->'issue'->'user'->>'login' (issue_comment events)

    Args:
        time_filter: Optional SQL time filter (e.g., " AND created_at >= $1")
        repository_filter: Optional SQL repository filter (e.g., " AND repository = $2")

    Returns:
        SQL CTE definition string (without WITH keyword)
    """
    return f"""pr_creators AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                COALESCE(
                    pr_author,
                    payload->'pull_request'->'user'->>'login',
                    payload->'issue'->'user'->>'login'
                ) as pr_creator
            FROM webhooks
            WHERE pr_number IS NOT NULL{time_filter}{repository_filter}
            ORDER BY repository, pr_number, created_at ASC
        )"""


def get_pr_creators_count_query(time_filter: str = "", repository_filter: str = "", user_filter: str = "") -> str:
    """Generate count query for PR creators.

    Args:
        time_filter: Optional SQL time filter (e.g., " AND created_at >= $1")
        repository_filter: Optional SQL repository filter (e.g., " AND repository = $2")
        user_filter: Optional user filter (e.g., " AND pr_creator = $3")

    Returns:
        Complete SQL count query

    Note: COUNT(*) counts PRs correctly because pr_creators CTE produces
    distinct (repository, pr_number, pr_creator) rows, so each row represents
    one unique PR for a specific user.
    """
    cte = get_pr_creators_cte(time_filter, repository_filter)
    return f"""
        WITH {cte}
        SELECT COUNT(*) as total
        FROM pr_creators
        WHERE pr_creator IS NOT NULL{user_filter}
    """


def get_pr_merged_status_cte() -> str:
    """Get CTE for determining PR merged status using BOOL_OR.

    This checks if ANY webhook event for a PR has pr_merged=true,
    ensuring correct merged status even when latest event doesn't have it.
    """
    return """pr_merged_status AS (
        SELECT repository, pr_number, BOOL_OR(pr_merged) as merged
        FROM webhooks
        WHERE pr_number IS NOT NULL
        GROUP BY repository, pr_number
    )"""


def get_pr_creators_data_query(
    time_filter: str = "",
    repository_filter: str = "",
    user_filter: str = "",
    limit_param: str = "$1",
    offset_param: str = "$2",
) -> str:
    """Generate data query for PR creators with statistics.

    Args:
        time_filter: Optional SQL time filter (e.g., " AND created_at >= $1")
        repository_filter: Optional SQL repository filter (e.g., " AND repository = $2")
                          NOTE: Applied in pr_creators CTE, NOT in user_prs CTE
        user_filter: Optional user filter (e.g., " AND pr_creator = $3")
        limit_param: SQL parameter for LIMIT (e.g., "$4")
        offset_param: SQL parameter for OFFSET (e.g., "$5")

    Returns:
        Complete SQL data query with PR creator statistics

    Important:
        The user_prs CTE does NOT include {repository_filter} in its WHERE clause.
        This is intentional to avoid ambiguous column references:
        - Both webhooks (w) and pr_creators (pc) have 'repository' columns
        - pr_creators is already filtered by repository_filter
        - JOIN condition ensures user_prs only includes filtered repositories
        - Adding unqualified 'repository' filter would cause PostgreSQL error:
          "column reference 'repository' is ambiguous"
    """
    cte = get_pr_creators_cte(time_filter, repository_filter)
    return f"""
        WITH {cte},
        user_prs AS (
            SELECT
                pc.pr_creator,
                w.pr_number,
                COALESCE(w.pr_commits_count, 0) as commits,
                COALESCE(w.pr_merged, false) as is_merged,
                (w.pr_state = 'closed' AND COALESCE(w.pr_merged, false) = false) as is_closed
            FROM webhooks w
            INNER JOIN pr_creators pc ON w.repository = pc.repository AND w.pr_number = pc.pr_number
            WHERE w.pr_number IS NOT NULL{time_filter}
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
        WHERE 1=1{user_filter}
        GROUP BY pr_creator
        ORDER BY total_prs DESC
        LIMIT {limit_param} OFFSET {offset_param}
    """
