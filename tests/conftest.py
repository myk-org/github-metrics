"""
Pytest fixtures for GitHub Metrics test suite.

Provides reusable test fixtures including:
- Mock database manager
- Mock configuration
- FastAPI test client
- Sample webhook payloads
- Environment variable setup
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import subprocess
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from github_metrics.config import DatabaseConfig, MetricsConfig
from github_metrics.database import DatabaseManager

# IMPORTANT: app.py reads configuration at module import time (get_config() at module level).
# Environment variables MUST be set BEFORE importing github_metrics.app.
os.environ.update({
    "METRICS_DB_NAME": "test_metrics",
    "METRICS_DB_USER": "test_user",
    "METRICS_DB_PASSWORD": "test_pass",  # pragma: allowlist secret
    "METRICS_DB_HOST": "localhost",
    "METRICS_DB_PORT": "5432",
    "METRICS_DB_POOL_SIZE": "10",
    "METRICS_SERVER_HOST": "127.0.0.1",
    "METRICS_SERVER_PORT": "8080",
    "METRICS_SERVER_WORKERS": "1",
    "METRICS_WEBHOOK_SECRET": "test_webhook_secret",  # pragma: allowlist secret
    "METRICS_VERIFY_GITHUB_IPS": "false",
    "METRICS_VERIFY_CLOUDFLARE_IPS": "false",
    "METRICS_MCP_ENABLED": "true",
})

# E402: app import must be after os.environ.update() because
# app.py calls get_config() at module level which requires these env vars
from github_metrics.app import app  # noqa: E402


@pytest.fixture
def test_config() -> MetricsConfig:
    """Create test configuration instance."""
    return MetricsConfig()


@pytest.fixture
def mock_db_manager() -> AsyncMock:
    """Create mock DatabaseManager for testing."""
    mock = AsyncMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.execute = AsyncMock(return_value="INSERT 0 1")
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.fetchval = AsyncMock(return_value=0)
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_metrics_tracker() -> AsyncMock:
    """Create mock MetricsTracker for testing."""
    mock = AsyncMock()
    mock.track_webhook_event = AsyncMock()
    return mock


@pytest.fixture
def sample_pull_request_payload() -> dict[str, Any]:
    """Sample GitHub pull_request webhook payload."""
    return {
        "action": "opened",
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "Test PR",
            "state": "open",
            "user": {"login": "testuser"},
            "head": {"ref": "feature-branch", "sha": "abc123"},
            "base": {"ref": "main", "sha": "def456"},
        },
        "repository": {
            "full_name": "testorg/testrepo",
            "name": "testrepo",
            "owner": {"login": "testorg"},
        },
        "sender": {"login": "testuser"},
    }


@pytest.fixture
def sample_issue_comment_payload() -> dict[str, Any]:
    """Sample GitHub issue_comment webhook payload."""
    return {
        "action": "created",
        "issue": {
            "number": 10,
            "title": "Test Issue",
            "state": "open",
            "user": {"login": "testuser"},
            "pull_request": {"url": "https://api.github.com/repos/testorg/testrepo/pulls/10"},
        },
        "comment": {
            "id": 123456,
            "body": "/test-command",
            "user": {"login": "testuser"},
        },
        "repository": {
            "full_name": "testorg/testrepo",
            "name": "testrepo",
            "owner": {"login": "testorg"},
        },
        "sender": {"login": "testuser"},
    }


@pytest.fixture
def sample_push_payload() -> dict[str, Any]:
    """Sample GitHub push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "commits": [
            {
                "id": "def456",
                "message": "Test commit",
                "author": {"name": "Test User", "email": "test@example.com"},
            }
        ],
        "repository": {
            "full_name": "testorg/testrepo",
            "name": "testrepo",
            "owner": {"login": "testorg"},
        },
        "sender": {"login": "testuser"},
    }


@pytest.fixture
def webhook_headers() -> dict[str, str]:
    """Standard GitHub webhook headers."""
    return {
        "X-GitHub-Delivery": "12345-67890-abcdef",
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=test_signature",
        "Content-Type": "application/json",
    }


@pytest.fixture
def valid_signature() -> str:
    """Valid HMAC signature for test webhook payload."""
    secret = "test_webhook_secret"  # pragma: allowlist secret
    payload = {"test": "data"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    hash_object = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    return "sha256=" + hash_object.hexdigest()


@pytest.fixture
def test_client() -> TestClient:
    """Create FastAPI test client.

    Note: This fixture creates a real app but tests should mock
    the database and other dependencies in app lifespan.
    """
    return TestClient(app)


# Database test fixtures
@pytest.fixture
def db_config() -> DatabaseConfig:
    """Create test database configuration."""
    return DatabaseConfig(
        host="localhost",
        port=5432,
        name="test_db",
        user="test_user",
        password="test_pass",  # pragma: allowlist secret
        pool_size=10,
    )


@pytest.fixture
def mock_logger() -> Mock:
    """Create mock logger."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_metrics_config(db_config: DatabaseConfig) -> Mock:
    """Create mock MetricsConfig."""
    config = Mock(spec=MetricsConfig)
    config.database = db_config
    return config


@pytest.fixture
def db_manager(mock_metrics_config: Mock, mock_logger: Mock) -> DatabaseManager:
    """Create DatabaseManager instance with mocked dependencies."""
    return DatabaseManager(config=mock_metrics_config, logger=mock_logger)


# Playwright UI test fixtures
@pytest.fixture
def mock_dashboard_data() -> dict[str, Any]:
    """Mock dashboard data for UI tests."""
    return {
        "summary": {
            "total_events": 150,
            "successful_events": 145,
            "failed_events": 5,
            "success_rate": 96.67,
            "avg_processing_time_ms": 234,
            "total_events_trend": 12.5,
            "success_rate_trend": 2.3,
            "failed_events_trend": -10.0,
            "avg_duration_trend": -5.2,
        },
        "top_repositories": [
            {"repository": "org/repo1", "total_events": 80, "percentage": 53.33, "success_rate": 98.75},
            {"repository": "org/repo2", "total_events": 50, "percentage": 33.33, "success_rate": 94.0},
            {"repository": "org/repo3", "total_events": 20, "percentage": 13.33, "success_rate": 95.0},
        ],
        "event_type_distribution": {
            "pull_request": 80,
            "issue_comment": 40,
            "push": 30,
        },
    }


@pytest.fixture
def mock_contributors_data() -> dict[str, Any]:
    """Mock contributors data for UI tests."""
    return {
        "pr_creators": {
            "data": [
                {"user": "alice", "total_prs": 25, "merged_prs": 23, "closed_prs": 2, "avg_commits_per_pr": 3.2},
                {"user": "bob", "total_prs": 18, "merged_prs": 17, "closed_prs": 1, "avg_commits_per_pr": 2.8},
            ],
            "pagination": {
                "total": 2,
                "page": 1,
                "page_size": 10,
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        },
        "pr_reviewers": {
            "data": [
                {"user": "charlie", "total_reviews": 45, "prs_reviewed": 30, "avg_reviews_per_pr": 1.5},
                {"user": "diana", "total_reviews": 35, "prs_reviewed": 28, "avg_reviews_per_pr": 1.25},
            ],
            "pagination": {
                "total": 2,
                "page": 1,
                "page_size": 10,
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        },
        "pr_approvers": {
            "data": [
                {"user": "eve", "total_approvals": 40, "prs_approved": 38},
                {"user": "frank", "total_approvals": 32, "prs_approved": 30},
            ],
            "pagination": {
                "total": 2,
                "page": 1,
                "page_size": 10,
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        },
        "pr_lgtm": {
            "data": [
                {"user": "grace", "total_lgtm": 28, "prs_lgtm": 26},
                {"user": "henry", "total_lgtm": 22, "prs_lgtm": 20},
            ],
            "pagination": {
                "total": 2,
                "page": 1,
                "page_size": 10,
                "total_pages": 1,
                "has_next": False,
                "has_prev": False,
            },
        },
    }


@pytest.fixture
def mock_user_prs_data() -> dict[str, Any]:
    """Mock user PRs data for UI tests."""
    return {
        "data": [
            {
                "number": 123,
                "title": "Add feature X",
                "owner": "alice",
                "repository": "org/repo1",
                "state": "closed",
                "merged": True,
                "url": "https://github.com/org/repo1/pull/123",
                "created_at": "2024-11-20T10:00:00Z",
                "updated_at": "2024-11-21T15:30:00Z",
                "commits_count": 5,
                "head_sha": "abc123",  # pragma: allowlist secret
            },
            {
                "number": 124,
                "title": "Fix bug Y",
                "owner": "bob",
                "repository": "org/repo1",
                "state": "open",
                "merged": False,
                "url": "https://github.com/org/repo1/pull/124",
                "created_at": "2024-11-22T09:00:00Z",
                "updated_at": "2024-11-22T16:45:00Z",
                "commits_count": 3,
                "head_sha": "def456",  # pragma: allowlist secret
            },
        ],
        "pagination": {"total": 2, "page": 1, "page_size": 10, "total_pages": 1, "has_next": False, "has_prev": False},
    }


@pytest.fixture
def mock_recent_events_data() -> list[dict[str, Any]]:
    """Mock recent events data for UI tests."""
    return [
        {
            "created_at": "2024-11-30T10:30:00Z",
            "repository": "org/repo1",
            "event_type": "pull_request",
            "status": "success",
        },
        {
            "created_at": "2024-11-30T10:25:00Z",
            "repository": "org/repo2",
            "event_type": "issue_comment",
            "status": "success",
        },
        {
            "created_at": "2024-11-30T10:20:00Z",
            "repository": "org/repo1",
            "event_type": "push",
            "status": "error",
        },
    ]


# Playwright UI test configuration
@pytest.fixture(scope="session")
def browser_context_args() -> dict[str, Any]:
    """Configure Playwright browser context.

    Returns:
        Browser context arguments for Playwright tests.
    """
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "accept_downloads": False,
    }


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, Any]:
    """Configure Playwright browser launch arguments.

    Returns:
        Browser launch arguments for Playwright tests.
    """
    return {
        "headless": True,
        "slow_mo": 0,  # No slow motion by default
    }


@pytest.fixture(scope="session")
def dev_server() -> Generator[str]:
    """Start dev server for UI tests, shut down after all tests complete.

    Starts the development server using ./dev/run.sh and waits for it to be ready.
    The server runs for the entire test session and is automatically shut down.

    Returns:
        Base URL of the development server.

    Raises:
        RuntimeError: If the server fails to start within the timeout period.
    """
    # Cleanup any existing dev container from previous runs
    # This prevents "container name already exists" errors
    container_name = "github-metrics-dev-db"
    subprocess.run(
        ["docker", "stop", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        ["docker", "rm", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    # Start server subprocess
    # CRITICAL: Use DEVNULL for stdout/stderr to prevent buffering deadlock
    # The script produces significant output (Docker startup, PostgreSQL logs, migrations)
    # Using PIPE causes the process to block when buffers fill up
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(project_dir, "dev", "run.sh")
    process = subprocess.Popen(
        [script_path],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to be ready
    # Startup sequence: Docker (3s) + PostgreSQL (variable) + migrations (variable) + server (variable)
    base_url = "http://localhost:8765"
    max_retries = 30  # 30 seconds total timeout
    for _ in range(max_retries):
        # Check if process died
        if process.poll() is not None:
            raise RuntimeError(
                f"Dev server process died during startup (exit code: {process.returncode}). "
                "Check ./dev/run.sh manually for errors."
            )

        try:
            response = httpx.get(f"{base_url}/dashboard", timeout=2.0)
            if response.status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(1)
    else:
        process.terminate()
        raise RuntimeError(
            f"Dev server failed to start within {max_retries} seconds. "
            f"Process status: {'running' if process.poll() is None else f'exited with code {process.returncode}'}"
        )

    yield base_url

    # Cleanup
    process.terminate()
    process.wait(timeout=10)
