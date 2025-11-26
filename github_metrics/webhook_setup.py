"""
GitHub webhook setup for metrics service.

Creates webhooks on configured repositories to send events to the metrics service.
Only runs if METRICS_SETUP_WEBHOOK=true environment variable is set.

Environment Variables:
- METRICS_SETUP_WEBHOOK: Set to "true" to enable webhook setup (default: disabled)
- METRICS_GITHUB_TOKEN: GitHub token for API access
- METRICS_WEBHOOK_URL: URL where webhooks will be sent
- METRICS_WEBHOOK_SECRET: Secret for webhook validation (optional)
- METRICS_REPOSITORIES: Comma-separated list of org/repo to configure
"""

from __future__ import annotations

import asyncio
import logging
import os

import github
from github.Hook import Hook
from github.Repository import Repository
from simple_logger.logger import get_logger

from github_metrics.config import MetricsConfig, get_config


async def setup_webhooks(
    config: MetricsConfig | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, tuple[bool, str]]:
    """
    Set up webhooks on all configured repositories.

    Only runs if METRICS_SETUP_WEBHOOK=true environment variable is set.
    All PyGithub calls are wrapped in asyncio.to_thread() to avoid blocking.

    Args:
        config: MetricsConfig instance (uses get_config() if not provided)
        logger: Logger instance (creates default if not provided)

    Returns:
        Dictionary of repository -> (success, message)
    """
    if config is None:
        config = get_config()

    if logger is None:
        logger = get_logger(name="github_metrics.webhook_setup")

    # Check if webhook setup is enabled
    setup_enabled = os.environ.get("METRICS_SETUP_WEBHOOK", "").lower() == "true"
    if not setup_enabled:
        logger.info("Webhook setup disabled (METRICS_SETUP_WEBHOOK != true)")
        return {}

    results: dict[str, tuple[bool, str]] = {}

    # Validate configuration
    if not config.github.has_token:
        logger.error("No GitHub token configured (METRICS_GITHUB_TOKEN)")
        return {"error": (False, "No GitHub token configured")}

    if not config.github.webhook_url:
        logger.error("No webhook URL configured (METRICS_WEBHOOK_URL)")
        return {"error": (False, "No webhook URL configured")}

    if not config.github.repositories:
        logger.warning("No repositories configured (METRICS_REPOSITORIES)")
        return {}

    # Create GitHub API client
    try:
        github_api = github.Github(auth=github.Auth.Token(config.github.token))
    except github.GithubException:
        logger.exception("Failed to authenticate with GitHub")
        return {"error": (False, "Failed to authenticate with GitHub")}

    # Process each repository
    for repo_name in config.github.repositories:
        success, message = await _create_webhook_for_repository(
            repository_name=repo_name,
            github_api=github_api,
            webhook_url=config.github.webhook_url,
            webhook_secret=config.webhook.secret or None,
            logger=logger,
        )
        results[repo_name] = (success, message)
        if success:
            logger.info(message)
        else:
            logger.error(message)

    return results


async def _create_webhook_for_repository(
    repository_name: str,
    github_api: github.Github,
    webhook_url: str,
    webhook_secret: str | None,
    logger: logging.Logger,
) -> tuple[bool, str]:
    """
    Create webhook for a repository if it doesn't exist.

    All PyGithub calls wrapped in asyncio.to_thread() to avoid blocking.

    Args:
        repository_name: Repository in org/repo format
        github_api: Authenticated GitHub API instance
        webhook_url: URL for webhook delivery
        webhook_secret: Secret for webhook validation (optional)
        logger: Logger instance

    Returns:
        Tuple of (success, message)
    """
    try:
        repo: Repository = await asyncio.to_thread(github_api.get_repo, repository_name)
    except github.GithubException as ex:
        return False, f"Could not find repository {repository_name}: {ex}"

    # Build webhook config
    hook_config: dict[str, str] = {
        "url": webhook_url,
        "content_type": "json",
    }
    if webhook_secret:
        hook_config["secret"] = webhook_secret

    # Check existing hooks
    try:
        hooks: list[Hook] = await asyncio.to_thread(lambda: list(repo.get_hooks()))
    except github.GithubException as ex:
        return False, f"Could not list webhooks for {repository_name}: {ex}"

    # Check if webhook already exists
    for hook in hooks:
        if hook.config.get("url") == webhook_url:
            return True, f"{repository_name}: Webhook already exists"

    # Create new webhook
    logger.info(f"Creating webhook for {repository_name}: {webhook_url}")
    try:
        await asyncio.to_thread(
            repo.create_hook,
            name="web",
            config=hook_config,
            events=["*"],
            active=True,
        )
    except github.GithubException as ex:
        return False, f"Failed to create webhook for {repository_name}: {ex}"

    return True, f"{repository_name}: Webhook created successfully"
