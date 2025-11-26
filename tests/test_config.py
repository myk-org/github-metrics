"""Tests for configuration module.

Tests configuration loading from environment variables including:
- Required environment variables validation
- Default values for optional settings
- Database URL construction
- Configuration dataclasses
"""

from __future__ import annotations

import os

import pytest

from github_metrics.config import (
    DatabaseConfig,
    GitHubConfig,
    MetricsConfig,
    ServerConfig,
    WebhookConfig,
    _reset_config_for_testing,
    get_config,
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""

    def test_connection_url(self) -> None:
        """Test PostgreSQL connection URL construction."""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            name="testdb",
            user="testuser",
            password="testpass",  # pragma: allowlist secret
            pool_size=20,
        )
        expected = "postgresql://testuser:testpass@localhost:5432/testdb"  # pragma: allowlist secret
        assert config.connection_url == expected

    def test_sqlalchemy_url(self) -> None:
        """Test SQLAlchemy async connection URL construction."""
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            name="metrics",
            user="admin",
            password="secret123",  # pragma: allowlist secret
            pool_size=10,
        )
        expected = "postgresql+asyncpg://admin:secret123@db.example.com:5433/metrics"  # pragma: allowlist secret
        assert config.sqlalchemy_url == expected


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_server_config_creation(self) -> None:
        """Test server configuration creation."""
        config = ServerConfig(host="0.0.0.0", port=8080, workers=4)
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.workers == 4


class TestWebhookConfig:
    """Tests for WebhookConfig dataclass."""

    def test_webhook_config_creation(self) -> None:
        """Test webhook configuration creation."""
        config = WebhookConfig(
            secret="webhook_secret",  # pragma: allowlist secret
            verify_github_ips=True,
            verify_cloudflare_ips=False,
        )
        assert config.secret == "webhook_secret"  # pragma: allowlist secret
        assert config.verify_github_ips is True
        assert config.verify_cloudflare_ips is False


class TestGitHubConfig:
    """Tests for GitHubConfig dataclass."""

    def test_has_token_with_valid_token(self) -> None:
        """Test has_token returns True with valid token."""
        config = GitHubConfig(
            token="ghp_test123",
            webhook_url="https://example.com/webhook",
            repositories=("org/repo",),
        )
        assert config.has_token is True

    def test_has_token_without_token(self) -> None:
        """Test has_token returns False without token."""
        config = GitHubConfig(token="", webhook_url="", repositories=())
        assert config.has_token is False


class TestMetricsConfig:
    """Tests for MetricsConfig class."""

    def test_config_loads_required_env_vars(self, test_config: MetricsConfig) -> None:
        """Test configuration loads required environment variables."""
        assert test_config.database.name == "test_metrics"
        assert test_config.database.user == "test_user"
        assert test_config.database.password == "test_pass"  # pragma: allowlist secret

    def test_config_loads_default_values(self, test_config: MetricsConfig) -> None:
        """Test configuration uses default values for optional vars."""
        assert test_config.database.host == "localhost"
        assert test_config.database.port == 5432
        assert test_config.database.pool_size == 10
        assert test_config.server.host == "0.0.0.0"
        assert test_config.server.port == 8080
        assert test_config.server.workers == 1

    def test_config_missing_required_env_var_raises_error(self) -> None:
        """Test missing required environment variable raises KeyError."""
        # Using try/finally for env var cleanup - context manager would be overkill for single test
        original_value = os.environ.pop("METRICS_DB_NAME", None)
        try:
            with pytest.raises(KeyError, match="METRICS_DB_NAME"):
                MetricsConfig()
        finally:
            # Restore env var
            if original_value:
                os.environ["METRICS_DB_NAME"] = original_value

    def test_config_parses_comma_separated_lists(self) -> None:
        """Test configuration parses comma-separated list values."""
        os.environ["METRICS_REPOSITORIES"] = "org1/repo1,org2/repo2"

        try:
            config = MetricsConfig()
            assert config.github.repositories == ("org1/repo1", "org2/repo2")
        finally:
            # Clean up
            os.environ.pop("METRICS_REPOSITORIES", None)

    def test_webhook_config_boolean_parsing(self) -> None:
        """Test webhook boolean configuration parsing."""
        os.environ["METRICS_VERIFY_GITHUB_IPS"] = "true"
        os.environ["METRICS_VERIFY_CLOUDFLARE_IPS"] = "True"

        try:
            config = MetricsConfig()
            assert config.webhook.verify_github_ips is True
            assert config.webhook.verify_cloudflare_ips is True
        finally:
            os.environ.pop("METRICS_VERIFY_GITHUB_IPS", None)
            os.environ.pop("METRICS_VERIFY_CLOUDFLARE_IPS", None)

    def test_webhook_config_false_by_default(self) -> None:
        """Test webhook verification disabled by default."""
        config = MetricsConfig()
        assert config.webhook.verify_github_ips is False
        assert config.webhook.verify_cloudflare_ips is False


class TestGetConfig:
    """Tests for get_config singleton function."""

    def test_get_config_returns_singleton(self) -> None:
        """Test get_config returns same instance on multiple calls."""
        # Reset singleton
        _reset_config_for_testing()

        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_returns_valid_config(self) -> None:
        """Test get_config returns valid MetricsConfig instance."""
        config = get_config()
        assert isinstance(config, MetricsConfig)
        assert config.database.name == "test_metrics"
