"""
Pytest fixtures for GitHub Metrics test suite.

Provides reusable test fixtures including:
- Mock database manager
- Mock configuration
- FastAPI test client
- Sample webhook payloads
- Environment variable setup
"""

import hashlib
import hmac
import json
import logging
import os
import signal
import subprocess
import time
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from playwright.async_api import Page

from backend.config import DatabaseConfig, MetricsConfig
from backend.database import DatabaseManager
from tests.test_js_coverage_utils import JSCoverageCollector


class DevServerStartupError(Exception):
    """Raised when the development server fails to start during testing."""


# IMPORTANT: app.py reads configuration at module import time (get_config() at module level).
# Environment variables MUST be set BEFORE importing backend.app.
os.environ.update({
    "METRICS_DB_NAME": "github_metrics_dev",
    "METRICS_DB_USER": "postgres",
    "METRICS_DB_PASSWORD": "devpassword123",  # pragma: allowlist secret
    "METRICS_DB_HOST": "localhost",
    "METRICS_DB_PORT": "15432",
    "METRICS_DB_POOL_SIZE": "10",
    "METRICS_SERVER_HOST": "127.0.0.1",
    "METRICS_SERVER_PORT": "8765",
    "METRICS_SERVER_WORKERS": "1",
    "METRICS_WEBHOOK_SECRET": "test_webhook_secret",  # pragma: allowlist secret
    "METRICS_VERIFY_GITHUB_IPS": "false",
    "METRICS_VERIFY_CLOUDFLARE_IPS": "false",
    "METRICS_MCP_ENABLED": "true",
})

# E402: app import must be after os.environ.update() because
# app.py calls get_config() at module level which requires these env vars
from backend.app import app  # noqa: E402


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

    Starts the development server using ./dev/run-all.sh (React frontend on port 3003 + backend on port 8765)
    and waits for the frontend to be ready. The servers run for the entire test session and are automatically
    shut down.

    Returns:
        Base URL of the React frontend development server (http://localhost:3003).

    Raises:
        DevServerStartupError: If the server fails to start within the timeout period.
    """
    base_url = "http://localhost:3003"  # React dev server
    server_already_running = False
    try:
        response = httpx.get(base_url, timeout=2.0)
        if response.status_code == 200:
            print(f"Dev server {base_url} is already up, reusing it.")
            server_already_running = True
    except httpx.RequestError as e:
        # Server not running, start it
        print(f"Dev server probe failed for {base_url}: {e}")

    if server_already_running:
        yield base_url
        return

    # Start server subprocess
    # CRITICAL: Use DEVNULL for stdout/stderr to prevent buffering deadlock
    # The script produces significant output (Docker startup, PostgreSQL logs, migrations, Vite dev server)
    # Using PIPE causes the process to block when buffers fill up
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(project_dir, "dev", "run-all.sh")

    process = subprocess.Popen(
        [script_path],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Create new process group to kill entire process tree
    )

    # Wait for React frontend to be ready
    # Startup: Docker (3s) + PostgreSQL + migrations + backend + Vite
    max_retries = 30  # 30 seconds total timeout
    for _ in range(max_retries):
        # Check if process died
        if process.poll() is not None:
            raise DevServerStartupError(
                f"Dev server process died during startup (exit code: {process.returncode}). "
                "Check ./dev/run-all.sh manually for errors."
            )

        try:
            response = httpx.get(base_url, timeout=2.0)
            if response.status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(1)
    else:
        # Kill entire process group (shell script + child processes)
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass  # Process already dead
        raise DevServerStartupError(
            f"Dev server failed to start within {max_retries} seconds. "
            f"Process status: {'running' if process.poll() is None else f'exited with code {process.returncode}'}"
        )

    yield base_url

    # Cleanup - kill entire process group to ensure child processes are terminated
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass  # Process already dead
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # Force kill if graceful shutdown fails
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass  # Process already dead
        process.wait()


@pytest.fixture(scope="session")
def js_coverage_collector() -> Generator[JSCoverageCollector]:
    """Session-scoped JavaScript coverage collector.

    Collects V8 JavaScript coverage across all UI tests and generates
    reports in htmlcov/js/ after all tests complete.
    """
    collector = JSCoverageCollector()
    yield collector
    overall_pct = collector.generate_reports()

    if collector.coverage_entries:
        print(f"\n[JS Coverage] Report generated: {collector.output_dir}/index.html")
        minimum_coverage_threshold = 55.0

        if float(overall_pct) < minimum_coverage_threshold:
            pytest.fail(
                f"JavaScript coverage {overall_pct:.1f}% is below minimum threshold of {minimum_coverage_threshold}%"
            )
        else:
            print(f"JavaScript coverage is: {overall_pct:.1f}%")


@pytest.fixture
async def page_with_js_coverage(
    page: Page,
    js_coverage_collector: JSCoverageCollector,
) -> AsyncGenerator[Page]:
    """Page fixture that collects JavaScript coverage.

    Wraps the Playwright page to collect V8 JavaScript coverage
    for each test using CDP (Chrome DevTools Protocol).
    Coverage is aggregated in the session-scoped js_coverage_collector.
    """
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("Profiler.enable")
    await cdp.send(
        "Profiler.startPreciseCoverage",
        {
            "callCount": True,
            "detailed": True,
        },
    )

    yield page

    result = await cdp.send("Profiler.takePreciseCoverage")
    await cdp.send("Profiler.stopPreciseCoverage")
    await cdp.send("Profiler.disable")

    if "result" in result:
        js_coverage_collector.add_coverage(result["result"])
