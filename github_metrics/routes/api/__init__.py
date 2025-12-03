"""API route modules for GitHub Metrics service."""

from __future__ import annotations

from github_metrics.routes.api import (
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
