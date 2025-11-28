"""
Configuration for GitHub Metrics service.

All configuration is loaded from environment variables - no config files.
This ensures clean containerized deployment with Docker/Kubernetes.

Required environment variables:
- METRICS_DB_NAME: PostgreSQL database name
- METRICS_DB_USER: PostgreSQL username
- METRICS_DB_PASSWORD: PostgreSQL password

Optional environment variables (with defaults):
- METRICS_DB_HOST: Database host (default: localhost)
- METRICS_DB_PORT: Database port (default: 5432)
- METRICS_DB_POOL_SIZE: Connection pool size (default: 20)
- METRICS_SERVER_HOST: Server bind host (default: 0.0.0.0)
- METRICS_SERVER_PORT: Server bind port (default: 8080)
- METRICS_SERVER_WORKERS: Uvicorn workers (default: 4)

Webhook security configuration:
- METRICS_WEBHOOK_SECRET: Secret for validating webhook payloads
- METRICS_VERIFY_GITHUB_IPS: Verify requests from GitHub IPs (default: false)
- METRICS_VERIFY_CLOUDFLARE_IPS: Verify requests from Cloudflare IPs (default: false)

GitHub webhook setup (optional - for automatic webhook creation):
- METRICS_SETUP_WEBHOOK: Enable webhook setup on startup (default: false)
- METRICS_GITHUB_TOKEN: GitHub token for API access
- METRICS_WEBHOOK_URL: URL where metrics service receives webhooks
- METRICS_REPOSITORIES: Comma-separated list of org/repo to configure webhooks
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from urllib.parse import quote_plus


def _parse_bool(value: str) -> bool:
    """Parse boolean string accepting common truthy variants.

    Args:
        value: String value to parse

    Returns:
        bool: True if value is truthy, False otherwise

    Accepts (case-insensitive):
        - "true", "1", "yes", "on" → True
        - Everything else → False
    """
    return value.lower() in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL database configuration."""

    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int

    @property
    def connection_url(self) -> str:
        """Build asyncpg connection URL."""
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"postgresql://{user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def sqlalchemy_url(self) -> str:
        """Build SQLAlchemy async connection URL."""
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class ServerConfig:
    """Server configuration."""

    host: str
    port: int
    workers: int
    reload: bool


@dataclass(frozen=True)
class WebhookConfig:
    """Webhook security configuration."""

    secret: str
    verify_github_ips: bool
    verify_cloudflare_ips: bool


@dataclass(frozen=True)
class GitHubConfig:
    """GitHub API configuration for webhook setup."""

    token: str
    webhook_url: str
    repositories: tuple[str, ...]

    @property
    def has_token(self) -> bool:
        """Check if a valid token is configured."""
        return bool(self.token)


@dataclass(frozen=True)
class MCPConfig:
    """MCP server configuration."""

    enabled: bool


class MetricsConfig:
    """
    Configuration for GitHub Metrics service.

    All configuration is loaded from environment variables.
    Raises KeyError for missing required environment variables (fail-fast).

    Example:
        config = MetricsConfig()
        print(config.database.connection_url)
        print(config.server.port)
    """

    def __init__(self) -> None:
        """
        Initialize configuration from environment variables.

        Raises:
            KeyError: If required environment variable is missing
            ValueError: If environment variable has invalid value
        """
        # Database configuration
        self.database = DatabaseConfig(
            host=os.environ.get("METRICS_DB_HOST", "localhost"),
            port=int(os.environ.get("METRICS_DB_PORT", "5432")),
            name=os.environ["METRICS_DB_NAME"],  # Required - KeyError if missing
            user=os.environ["METRICS_DB_USER"],  # Required - KeyError if missing
            password=os.environ["METRICS_DB_PASSWORD"],  # Required - KeyError if missing
            pool_size=int(os.environ.get("METRICS_DB_POOL_SIZE", "20")),
        )

        # Server configuration
        self.server = ServerConfig(
            host=os.environ.get("METRICS_SERVER_HOST", "0.0.0.0"),  # noqa: S104
            port=int(os.environ.get("METRICS_SERVER_PORT", "8080")),
            workers=int(os.environ.get("METRICS_SERVER_WORKERS", "4")),
            reload=_parse_bool(os.environ.get("METRICS_SERVER_RELOAD", "")),
        )

        # Webhook security configuration
        webhook_secret = os.environ.get("METRICS_WEBHOOK_SECRET", "")
        verify_github_ips = _parse_bool(os.environ.get("METRICS_VERIFY_GITHUB_IPS", ""))
        verify_cloudflare_ips = _parse_bool(os.environ.get("METRICS_VERIFY_CLOUDFLARE_IPS", ""))

        self.webhook = WebhookConfig(
            secret=webhook_secret,
            verify_github_ips=verify_github_ips,
            verify_cloudflare_ips=verify_cloudflare_ips,
        )

        # GitHub configuration (for webhook setup)
        github_token = os.environ.get("METRICS_GITHUB_TOKEN", "")
        webhook_url = os.environ.get("METRICS_WEBHOOK_URL", "")
        repositories_str = os.environ.get("METRICS_REPOSITORIES", "")

        self.github = GitHubConfig(
            token=github_token.strip(),
            webhook_url=webhook_url,
            repositories=tuple(r.strip() for r in repositories_str.split(",") if r.strip()),
        )

        # MCP server configuration
        self.mcp = MCPConfig(
            enabled=_parse_bool(os.environ.get("METRICS_MCP_ENABLED", "true")),
        )


# Singleton instance - lazy loaded with thread-safe initialization
_config: MetricsConfig | None = None
_config_lock = threading.Lock()


def get_config() -> MetricsConfig:
    """
    Get the global configuration instance.

    Thread-safe singleton using double-checked locking pattern.

    Returns:
        MetricsConfig: The configuration instance

    Raises:
        KeyError: If required environment variable is missing
    """
    global _config
    # First check without lock for performance
    if _config is None:
        # Acquire lock for initialization
        with _config_lock:
            # Double-check after acquiring lock
            if _config is None:
                _config = MetricsConfig()
    return _config


def _reset_config_for_testing() -> None:
    """Reset config singleton for testing purposes only."""
    global _config
    _config = None
