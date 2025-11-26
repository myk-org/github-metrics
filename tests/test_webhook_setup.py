"""Tests for webhook setup module.

Tests webhook creation and management including:
- Webhook setup for repositories
- Environment variable checking
- GitHub API interaction
- Error handling
"""

from __future__ import annotations

import logging
import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import github
import pytest

from github_metrics.config import GitHubConfig, MetricsConfig, WebhookConfig
from github_metrics.webhook_setup import (
    _create_webhook_for_repository,
    setup_webhooks,
)


class TestSetupWebhooks:
    """Tests for setup_webhooks function."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create mock configuration."""
        config = Mock(spec=MetricsConfig)
        config.github = GitHubConfig(
            token="ghp_test_token_123",  # pragma: allowlist secret
            webhook_url="https://example.com/webhook",
            repositories=("testorg/repo1", "testorg/repo2"),
        )
        config.webhook = WebhookConfig(
            secret="webhook_secret",  # pragma: allowlist secret
            verify_github_ips=False,
            verify_cloudflare_ips=False,
        )
        return config

    @pytest.fixture
    def mock_logger(self) -> Mock:
        """Create mock logger."""
        return Mock(spec=logging.Logger)

    async def test_setup_webhooks_disabled_by_default(
        self,
        mock_config: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup is disabled when env var not set."""
        # Ensure env var is not set
        os.environ.pop("METRICS_SETUP_WEBHOOK", None)

        result = await setup_webhooks(config=mock_config, logger=mock_logger)

        assert result == {}
        mock_logger.info.assert_called_once()
        assert "disabled" in mock_logger.info.call_args[0][0]

    async def test_setup_webhooks_enabled_with_env_var(
        self,
        mock_config: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup runs when env var is true."""
        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            with patch("github.Github") as mock_github_class:
                mock_github_instance = Mock()
                mock_github_class.return_value = mock_github_instance

                with patch(
                    "github_metrics.webhook_setup._create_webhook_for_repository",
                    new=AsyncMock(return_value=(True, "Webhook created")),
                ):
                    result = await setup_webhooks(config=mock_config, logger=mock_logger)

                    assert "testorg/repo1" in result
                    assert "testorg/repo2" in result
                    assert result["testorg/repo1"] == (True, "Webhook created")
                    assert result["testorg/repo2"] == (True, "Webhook created")
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_without_github_token(
        self,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup fails without GitHub token."""
        config = Mock(spec=MetricsConfig)
        config.github = GitHubConfig(token="", webhook_url="", repositories=())
        config.webhook = WebhookConfig(secret="", verify_github_ips=False, verify_cloudflare_ips=False)

        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            result = await setup_webhooks(config=config, logger=mock_logger)

            assert "error" in result
            assert result["error"][0] is False
            assert "No GitHub token" in result["error"][1]
            mock_logger.error.assert_called_once()
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_without_webhook_url(
        self,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup fails without webhook URL."""
        config = Mock(spec=MetricsConfig)
        config.github = GitHubConfig(
            token="ghp_test_token",  # pragma: allowlist secret
            webhook_url="",
            repositories=("testorg/repo1",),
        )
        config.webhook = WebhookConfig(secret="", verify_github_ips=False, verify_cloudflare_ips=False)

        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            result = await setup_webhooks(config=config, logger=mock_logger)

            assert "error" in result
            assert result["error"][0] is False
            assert "No webhook URL" in result["error"][1]
            mock_logger.error.assert_called_once()
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_without_repositories(
        self,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup returns empty dict when no repositories configured."""
        config = Mock(spec=MetricsConfig)
        config.github = GitHubConfig(
            token="ghp_test_token",  # pragma: allowlist secret
            webhook_url="https://example.com/webhook",
            repositories=(),
        )
        config.webhook = WebhookConfig(secret="", verify_github_ips=False, verify_cloudflare_ips=False)

        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            result = await setup_webhooks(config=config, logger=mock_logger)

            assert result == {}
            mock_logger.warning.assert_called_once()
            assert "No repositories" in mock_logger.warning.call_args[0][0]
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_github_auth_failure(
        self,
        mock_config: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup handles GitHub authentication failure."""
        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            with patch("github.Github", side_effect=github.GithubException(401, "Bad credentials", None)):
                result = await setup_webhooks(config=mock_config, logger=mock_logger)

                assert "error" in result
                assert result["error"][0] is False
                assert "Failed to authenticate" in result["error"][1]
                mock_logger.exception.assert_called()
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_uses_default_config_and_logger(self) -> None:
        """Test webhook setup creates default config and logger if not provided."""
        os.environ["METRICS_SETUP_WEBHOOK"] = "false"

        try:
            result = await setup_webhooks()

            assert result == {}
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)

    async def test_setup_webhooks_mixed_results(
        self,
        mock_config: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook setup with some successes and some failures."""
        os.environ["METRICS_SETUP_WEBHOOK"] = "true"

        try:
            with patch("github.Github") as mock_github_class:
                mock_github_instance = Mock()
                mock_github_class.return_value = mock_github_instance

                async def mock_create_webhook(repository_name: str, **_kwargs: Any) -> tuple[bool, str]:
                    if repository_name == "testorg/repo1":
                        return True, f"{repository_name}: Webhook created successfully"
                    return False, f"Failed to create webhook for {repository_name}: Repository not found"

                with patch(
                    "github_metrics.webhook_setup._create_webhook_for_repository",
                    side_effect=mock_create_webhook,
                ):
                    result = await setup_webhooks(config=mock_config, logger=mock_logger)

                    assert result["testorg/repo1"][0] is True
                    assert result["testorg/repo2"][0] is False

                    # Verify logger calls for both success and failure
                    info_calls = list(mock_logger.info.call_args_list)
                    error_calls = list(mock_logger.error.call_args_list)
                    assert len(info_calls) >= 1
                    assert len(error_calls) >= 1
        finally:
            os.environ.pop("METRICS_SETUP_WEBHOOK", None)


class TestCreateWebhookForRepository:
    """Tests for _create_webhook_for_repository function."""

    @pytest.fixture
    def mock_logger(self) -> Mock:
        """Create mock logger."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def mock_github_api(self) -> Mock:
        """Create mock GitHub API instance."""
        return Mock(spec=github.Github)

    async def test_create_webhook_for_repository_success(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test successful webhook creation for repository."""
        mock_repo = Mock(spec=github.Repository.Repository)
        mock_repo.get_hooks = Mock(return_value=[])

        async def mock_to_thread(func: Any, *_args: Any, **_kwargs: Any) -> Any:
            if func == mock_github_api.get_repo:
                return mock_repo
            if callable(func):
                return func()
            return []

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",  # pragma: allowlist secret
                logger=mock_logger,
            )

            assert success is True
            assert "created successfully" in message
            mock_logger.info.assert_called()

    async def test_create_webhook_for_repository_not_found(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook creation fails for non-existent repository."""

        async def mock_to_thread(_func: Any, *_args: Any, **_kwargs: Any) -> Any:
            raise github.GithubException(404, "Not Found", None)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/nonexistent",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret=None,
                logger=mock_logger,
            )

            assert success is False
            assert "Could not find repository" in message

    async def test_create_webhook_for_repository_already_exists(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook creation when webhook already exists."""
        mock_hook = Mock(spec=github.Hook.Hook)
        mock_hook.config = {"url": "https://example.com/webhook"}

        mock_repo = Mock(spec=github.Repository.Repository)
        mock_repo.get_hooks = Mock(return_value=[mock_hook])

        async def mock_to_thread(func: Any, *_args: Any, **_kwargs: Any) -> Any:
            if func == mock_github_api.get_repo:
                return mock_repo
            if callable(func):
                return func()
            return [mock_hook]

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret=None,
                logger=mock_logger,
            )

            assert success is True
            assert "already exists" in message

    async def test_create_webhook_for_repository_list_hooks_failure(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook creation fails when listing hooks fails."""
        mock_repo = Mock(spec=github.Repository.Repository)

        call_count = 0

        async def mock_to_thread(_func: Any, *_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call is get_repo
                return mock_repo
            # Second call is get_hooks
            raise github.GithubException(403, "Forbidden", None)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret=None,
                logger=mock_logger,
            )

            assert success is False
            assert "Could not list webhooks" in message

    async def test_create_webhook_for_repository_create_failure(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook creation fails when create_hook fails."""
        mock_repo = Mock(spec=github.Repository.Repository)

        call_count = 0

        async def mock_to_thread(_func: Any, *_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call is get_repo
                return mock_repo
            if call_count == 2:  # Second call is get_hooks
                return []
            # Third call is create_hook
            raise github.GithubException(422, "Validation failed", None)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret="secret123",  # pragma: allowlist secret
                logger=mock_logger,
            )

            assert success is False
            assert "Failed to create webhook" in message

    async def test_create_webhook_for_repository_without_secret(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook creation without secret (optional parameter)."""
        mock_repo = Mock(spec=github.Repository.Repository)
        mock_hook = Mock(spec=github.Hook.Hook)

        call_count = 0

        async def mock_to_thread(_func: Any, *_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call is get_repo
                return mock_repo
            if call_count == 2:  # Second call is get_hooks
                return []
            # Third call is create_hook
            return mock_hook

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret=None,  # No secret provided
                logger=mock_logger,
            )

            assert success is True
            assert "created successfully" in message

    async def test_create_webhook_for_repository_url_exact_match_check(
        self,
        mock_github_api: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test webhook URL matching uses exact equality for robustness."""
        # Existing webhook with exact URL match
        mock_hook = Mock(spec=github.Hook.Hook)
        mock_hook.config = {"url": "https://example.com/webhook"}

        mock_repo = Mock(spec=github.Repository.Repository)

        call_count = 0

        async def mock_to_thread(_func: Any, *_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First call is get_repo
                return mock_repo
            if call_count == 2:  # Second call is get_hooks
                return [mock_hook]
            return None

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            # Webhook URL matches exactly
            success, message = await _create_webhook_for_repository(
                repository_name="testorg/testrepo",
                github_api=mock_github_api,
                webhook_url="https://example.com/webhook",
                webhook_secret=None,
                logger=mock_logger,
            )

            assert success is True
            assert "already exists" in message
