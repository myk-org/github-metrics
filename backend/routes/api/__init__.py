"""API route modules for GitHub Metrics service."""

from backend.routes.api import (
    contributors,
    pr_story,
    repositories,
    summary,
    trends,
    turnaround,
    user_prs,
    webhooks,
)

__all__ = [
    "contributors",
    "pr_story",
    "repositories",
    "summary",
    "trends",
    "turnaround",
    "user_prs",
    "webhooks",
]
