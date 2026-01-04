"""Tests for FastAPI application endpoints.

Tests HTTP endpoints including:
- Health check endpoint
- Webhook receiver endpoint
- Dashboard endpoint
- API metrics endpoints
"""

import asyncio
import concurrent.futures
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import asyncpg
import httpx
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import app, create_app
from backend.utils.datetime_utils import parse_datetime_string


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_healthy(self) -> None:
        """Test health endpoint returns healthy status."""
        with patch("backend.routes.health.db_manager") as mock_db:
            mock_db.health_check = AsyncMock(return_value=True)

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] is True
            assert "version" in data

    def test_health_check_degraded(self) -> None:
        """Test health endpoint returns degraded when database unhealthy."""
        with patch("backend.routes.health.db_manager") as mock_db:
            mock_db.health_check = AsyncMock(return_value=False)

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] is False

    def test_health_check_without_db_manager(self) -> None:
        """Test health endpoint when db_manager is None."""
        with patch("backend.routes.health.db_manager", None):
            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] is False


class TestFaviconEndpoint:
    """Tests for /favicon.ico endpoint."""

    def test_favicon_returns_png(self) -> None:
        """Test favicon endpoint returns PNG image."""
        client = TestClient(app)
        response = client.get("/favicon.ico")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 0


class TestWebhookEndpoint:
    """Tests for /metrics webhook endpoint."""

    @pytest.fixture
    def webhook_payload(self) -> dict[str, Any]:
        """Create test webhook payload."""
        return {
            "action": "opened",
            "number": 42,
            "pull_request": {"number": 42, "title": "Test PR"},
            "repository": {"full_name": "testorg/testrepo"},
            "sender": {"login": "testuser"},
        }

    def _create_signature(self, payload: dict[str, Any], secret: str) -> str:
        """Create valid HMAC signature for payload."""
        payload_bytes = json.dumps(payload).encode("utf-8")
        hash_object = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
        return "sha256=" + hash_object.hexdigest()

    def test_webhook_receive_success(self, webhook_payload: dict[str, Any]) -> None:
        """Test successful webhook reception."""
        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            # Setup mocks
            mock_tracker.track_webhook_event = AsyncMock()
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)

            response = client.post(
                "/metrics",
                json=webhook_payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-123",
                    "X-GitHub-Event": "pull_request",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "ok"
            assert data["delivery_id"] == "test-delivery-123"

    def test_webhook_receive_with_valid_signature(self, webhook_payload: dict[str, Any]) -> None:
        """Test webhook with valid signature verification."""
        # Note: TestClient processes JSON differently, making signature verification complex
        # This test verifies the signature validation path works by checking it doesn't
        # throw an error for invalid signature (tested separately)
        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
            patch("backend.routes.webhooks.verify_signature") as mock_verify_sig,
        ):
            mock_tracker.track_webhook_event = AsyncMock()
            config_mock = Mock()
            config_mock.webhook.secret = "test_secret"  # pragma: allowlist secret
            mock_config.return_value = config_mock
            mock_verify_sig.return_value = None  # Signature valid

            client = TestClient(app)

            response = client.post(
                "/metrics",
                json=webhook_payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-456",
                    "X-GitHub-Event": "pull_request",
                    "X-Hub-Signature-256": "sha256=test_signature",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            mock_verify_sig.assert_called_once()

    def test_webhook_receive_with_invalid_signature(self, webhook_payload: dict[str, Any]) -> None:
        """Test webhook rejection with invalid signature."""
        with (
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            config_mock = Mock()
            config_mock.webhook.secret = "test_secret"  # pragma: allowlist secret
            mock_config.return_value = config_mock

            client = TestClient(app)

            response = client.post(
                "/metrics",
                json=webhook_payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-789",
                    "X-GitHub-Event": "pull_request",
                    "X-Hub-Signature-256": "sha256=invalid_signature",
                },
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_webhook_receive_extracts_pr_number(self, webhook_payload: dict[str, Any]) -> None:
        """Test webhook extracts PR number from pull_request event."""
        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            mock_tracker.track_webhook_event = AsyncMock()
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)

            response = client.post(
                "/metrics",
                json=webhook_payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-pr",
                    "X-GitHub-Event": "pull_request",
                },
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify PR number was extracted
            mock_tracker.track_webhook_event.assert_called_once()
            call_kwargs = mock_tracker.track_webhook_event.call_args[1]
            assert call_kwargs["pr_number"] == 42

    def test_webhook_receive_invalid_json(self) -> None:
        """Test webhook rejection with invalid JSON payload."""
        with (
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)

            response = client.post(
                "/metrics",
                content=b"invalid json",
                headers={
                    "X-GitHub-Delivery": "test-delivery-invalid",
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestWebhookEventsEndpoint:
    """Tests for /api/metrics/webhooks endpoint."""

    def test_get_webhook_events_success(self) -> None:
        """Test successful webhook events retrieval."""
        mock_rows = [
            {
                "delivery_id": "test-123",
                "repository": "testorg/testrepo",
                "event_type": "pull_request",
                "action": "opened",
                "pr_number": 42,
                "sender": "testuser",
                "status": "success",
                "created_at": None,
                "processed_at": None,
                "duration_ms": 150,
                "api_calls_count": 3,
                "token_spend": 3,
                "token_remaining": 4997,
                "error_message": None,
            },
        ]

        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=1)
            mock_db.fetch = AsyncMock(return_value=mock_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["delivery_id"] == "test-123"

    def test_get_webhook_events_with_filters(self) -> None:
        """Test webhook events retrieval with filters."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/webhooks",
                params={
                    "repository": "testorg/testrepo",
                    "event_type": "pull_request",
                    "status": "success",
                    "page": 1,
                    "page_size": 50,
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"] == []
            assert data["pagination"]["total"] == 0

    def test_get_webhook_events_pagination(self) -> None:
        """Test webhook events pagination."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=150)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks", params={"page": 2, "page_size": 50})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["page_size"] == 50
            assert data["pagination"]["total"] == 150
            assert data["pagination"]["total_pages"] == 3
            assert data["pagination"]["has_next"] is True
            assert data["pagination"]["has_prev"] is True

    def test_get_webhook_events_database_unavailable(self) -> None:
        """Test webhook events when database unavailable."""
        with patch("backend.routes.api.webhooks.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/webhooks")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestWebhookEventByIdEndpoint:
    """Tests for /api/metrics/webhooks/{delivery_id} endpoint."""

    def test_get_webhook_event_by_id_success(self) -> None:
        """Test successful webhook event retrieval by ID."""
        mock_row = {
            "delivery_id": "test-123",
            "repository": "testorg/testrepo",
            "event_type": "pull_request",
            "action": "opened",
            "pr_number": 42,
            "sender": "testuser",
            "status": "success",
            "created_at": None,
            "processed_at": None,
            "duration_ms": 150,
            "api_calls_count": 3,
            "token_spend": 3,
            "token_remaining": 4997,
            "error_message": None,
            "payload": {"test": "data"},
        }

        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_row)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["delivery_id"] == "test-123"
            assert data["payload"] == {"test": "data"}

    def test_get_webhook_event_by_id_not_found(self) -> None:
        """Test webhook event retrieval for non-existent ID."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=None)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/nonexistent-id")

            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMetricsSummaryEndpoint:
    """Tests for /api/metrics/summary endpoint."""

    def test_get_metrics_summary_success(self) -> None:
        """Test successful metrics summary retrieval."""
        # Mock summary row
        mock_summary_row = {
            "total_events": 100,
            "successful_events": 95,
            "failed_events": 5,
            "success_rate": 95.0,
            "avg_processing_time_ms": 150,
            "median_processing_time_ms": 140,
            "p95_processing_time_ms": 300,
            "max_processing_time_ms": 500,
            "total_api_calls": 300,
            "avg_api_calls_per_event": 3.0,
            "total_token_spend": 300,
        }

        # Mock top repositories
        mock_top_repos = [
            {
                "repository": "testorg/testrepo",
                "total_events": 50,
                "success_rate": 96.0,
                "percentage": 50.0,
            },
        ]

        # Mock event type distribution
        mock_event_types = [
            {"event_type": "pull_request", "event_count": 60},
            {"event_type": "issue_comment", "event_count": 40},
        ]

        # Mock time range
        mock_time_range = {
            "first_event_time": None,
            "last_event_time": None,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            # Setup fetchrow to return summary_row and time_range_row
            mock_db.fetchrow = AsyncMock(side_effect=[mock_summary_row, mock_time_range])
            # Setup fetch to return top_repos and event_types
            mock_db.fetch = AsyncMock(side_effect=[mock_top_repos, mock_event_types])

            client = TestClient(app)
            response = client.get("/api/metrics/summary")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "summary" in data
            assert data["summary"]["total_events"] == 100
            assert data["summary"]["success_rate"] == 95.0
            assert "top_repositories" in data
            assert "event_type_distribution" in data

    def test_get_metrics_summary_empty_database(self) -> None:
        """Test metrics summary with empty database."""
        # Mock empty summary row
        mock_summary_row = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "success_rate": None,
            "avg_processing_time_ms": None,
            "median_processing_time_ms": None,
            "p95_processing_time_ms": None,
            "max_processing_time_ms": None,
            "total_api_calls": None,
            "avg_api_calls_per_event": None,
            "total_token_spend": None,
        }

        # Mock empty top repositories and event types
        mock_top_repos: list[dict[str, Any]] = []
        mock_event_types: list[dict[str, Any]] = []

        # Mock time range
        mock_time_range = {
            "first_event_time": None,
            "last_event_time": None,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            # Setup fetchrow to return summary_row and time_range_row
            mock_db.fetchrow = AsyncMock(side_effect=[mock_summary_row, mock_time_range])
            # Setup fetch to return empty arrays
            mock_db.fetch = AsyncMock(side_effect=[mock_top_repos, mock_event_types])

            client = TestClient(app)
            response = client.get("/api/metrics/summary")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["summary"]["total_events"] == 0
            assert data["summary"]["success_rate"] == 0.0


class TestRepositoryStatisticsEndpoint:
    """Tests for /api/metrics/repositories endpoint."""

    def test_get_repository_statistics_success(self) -> None:
        """Test successful repository statistics retrieval."""
        mock_rows = [
            {
                "repository": "testorg/testrepo",
                "total_events": 50,
                "successful_events": 48,
                "failed_events": 2,
                "success_rate": 96.0,
                "avg_processing_time_ms": 150,
                "total_api_calls": 150,
                "total_token_spend": 150,
            },
        ]

        with patch("backend.routes.api.repositories.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=1)
            mock_db.fetch = AsyncMock(return_value=mock_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/repositories")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "repositories" in data
            assert len(data["repositories"]) == 1
            assert data["repositories"][0]["repository"] == "testorg/testrepo"
            assert data["repositories"][0]["success_rate"] == 96.0


class TestParseDatetimeString:
    """Tests for parse_datetime_string utility function."""

    def test_parse_datetime_string_valid_iso8601(self) -> None:
        """Test parsing valid ISO 8601 datetime string."""
        result = parse_datetime_string("2024-01-15T10:30:00Z", "test_param")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_datetime_string_with_timezone(self) -> None:
        """Test parsing datetime with timezone offset."""
        result = parse_datetime_string("2024-01-15T10:30:00+00:00", "test_param")
        assert result is not None

    def test_parse_datetime_string_none(self) -> None:
        """Test parsing None returns None."""
        result = parse_datetime_string(None, "test_param")
        assert result is None

    def test_parse_datetime_string_invalid_format(self) -> None:
        """Test parsing invalid datetime format raises HTTPException."""
        with pytest.raises(HTTPException):
            parse_datetime_string("invalid-date", "test_param")


class TestLifespanContext:
    """Tests for application lifespan management."""

    async def test_lifespan_loads_github_ips(self) -> None:
        """Test lifespan loads GitHub IP allowlist when verification enabled."""

        with (
            patch("backend.app.get_config") as mock_config,
            patch("backend.app.get_database_manager") as mock_db_manager_factory,
            patch("backend.app.get_logger") as mock_logger_factory,
            patch("backend.app.httpx.AsyncClient") as mock_http_client_class,
            patch("backend.app.get_github_allowlist") as mock_get_github,
            patch("backend.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            # Setup mocks
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = True
            config_mock.webhook.verify_cloudflare_ips = False
            config_mock.sig_teams_config_path = None  # No SIG teams config for this test
            mock_config.return_value = config_mock

            mock_db = AsyncMock()
            mock_db_manager_factory.return_value = mock_db

            mock_logger_factory.return_value = Mock()

            mock_http_client = AsyncMock()
            mock_http_client_class.return_value = mock_http_client

            mock_get_github.return_value = ["192.30.252.0/22", "185.199.108.0/22"]
            mock_get_cloudflare.return_value = []

            async with app_module.lifespan(app_module.app):
                # Verify GitHub IPs were loaded
                mock_get_github.assert_called_once_with(mock_http_client)
                mock_get_cloudflare.assert_not_called()

                # Verify IP allowlist was set
                assert len(app_module.allowed_ips) == 2

    async def test_lifespan_loads_cloudflare_ips(self) -> None:
        """Test lifespan loads Cloudflare IP allowlist when verification enabled."""

        with (
            patch("backend.app.get_config") as mock_config,
            patch("backend.app.get_database_manager") as mock_db_manager_factory,
            patch("backend.app.get_logger") as mock_logger_factory,
            patch("backend.app.httpx.AsyncClient") as mock_http_client_class,
            patch("backend.app.get_github_allowlist") as mock_get_github,
            patch("backend.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            # Setup mocks
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = False
            config_mock.webhook.verify_cloudflare_ips = True
            config_mock.sig_teams_config_path = None  # No SIG teams config for this test
            mock_config.return_value = config_mock

            mock_db = AsyncMock()
            mock_db_manager_factory.return_value = mock_db

            mock_logger_factory.return_value = Mock()

            mock_http_client = AsyncMock()
            mock_http_client_class.return_value = mock_http_client

            mock_get_github.return_value = []
            mock_get_cloudflare.return_value = ["103.21.244.0/22", "2400:cb00::/32"]

            async with app_module.lifespan(app_module.app):
                # Verify Cloudflare IPs were loaded
                mock_get_cloudflare.assert_called_once_with(mock_http_client)
                mock_get_github.assert_not_called()

                # Verify IP allowlist was set
                assert len(app_module.allowed_ips) == 2

    async def test_lifespan_github_ip_fetch_failure_raises(self) -> None:
        """Test lifespan raises exception on GitHub IP fetch failure."""
        with (
            patch("backend.app.get_config") as mock_config,
            patch("backend.app.httpx.AsyncClient") as mock_http_client_class,
            patch("backend.app.get_github_allowlist") as mock_get_github,
        ):
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = True
            config_mock.webhook.verify_cloudflare_ips = False
            config_mock.sig_teams_config_path = None  # No SIG teams config for this test
            mock_config.return_value = config_mock

            mock_http_client = AsyncMock()
            mock_http_client_class.return_value = mock_http_client

            mock_get_github.side_effect = httpx.RequestError("Network error")

            with pytest.raises(httpx.RequestError):
                async with app_module.lifespan(app_module.app):
                    pass

    async def test_lifespan_cloudflare_ip_fetch_failure_raises(self) -> None:
        """Test lifespan raises exception on Cloudflare IP fetch failure."""
        with (
            patch("backend.app.get_config") as mock_config,
            patch("backend.app.httpx.AsyncClient") as mock_http_client_class,
            patch("backend.app.get_github_allowlist"),
            patch("backend.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = False
            config_mock.webhook.verify_cloudflare_ips = True
            config_mock.sig_teams_config_path = None  # No SIG teams config for this test
            mock_config.return_value = config_mock

            mock_http_client = AsyncMock()
            mock_http_client_class.return_value = mock_http_client

            mock_get_cloudflare.side_effect = Exception("API error")

            with pytest.raises(Exception, match="API error"):
                async with app_module.lifespan(app_module.app):
                    pass


class TestWebhookEventsEndpointErrors:
    """Tests for /api/metrics/webhooks error handling."""

    def test_get_webhook_events_with_invalid_time_format(self) -> None:
        """Test webhook events with invalid datetime format."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/webhooks",
                params={"start_time": "invalid-date"},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid datetime format" in response.json()["detail"]

    def test_get_webhook_events_database_error(self) -> None:
        """Test webhook events handles database errors."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_webhook_events_with_datetime_params(self) -> None:
        """Test webhook events with valid datetime parameters."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/webhooks",
                params={
                    "start_time": "2024-01-15T00:00:00Z",
                    "end_time": "2024-01-16T00:00:00Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK


class TestWebhookEventByIdErrors:
    """Tests for /api/metrics/webhooks/{delivery_id} error handling."""

    def test_get_webhook_event_by_id_database_error(self) -> None:
        """Test webhook event by ID handles database errors."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_webhook_event_by_id_database_unavailable(self) -> None:
        """Test webhook event by ID when database unavailable."""
        with patch("backend.routes.api.webhooks.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestRepositoryStatisticsErrors:
    """Tests for /api/metrics/repositories error handling."""

    def test_get_repository_statistics_database_error(self) -> None:
        """Test repository statistics handles database errors."""
        with patch("backend.routes.api.repositories.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/repositories")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_repository_statistics_with_datetime_params(self) -> None:
        """Test repository statistics with datetime parameters."""
        with patch("backend.routes.api.repositories.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/repositories",
                params={
                    "start_time": "2024-01-15T00:00:00Z",
                    "end_time": "2024-01-16T00:00:00Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK

    def test_get_repository_statistics_database_unavailable(self) -> None:
        """Test repository statistics when database unavailable."""
        with patch("backend.routes.api.repositories.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/repositories")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestMetricsSummaryErrors:
    """Tests for /api/metrics/summary error handling."""

    def test_get_metrics_summary_database_error(self) -> None:
        """Test metrics summary handles database errors."""
        with patch("backend.routes.api.summary.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/summary")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_metrics_summary_with_datetime_params(self) -> None:
        """Test metrics summary with datetime parameters."""
        # Mock summary row
        mock_summary_row = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "success_rate": None,
            "avg_processing_time_ms": None,
            "median_processing_time_ms": None,
            "p95_processing_time_ms": None,
            "max_processing_time_ms": None,
            "total_api_calls": 0,
            "avg_api_calls_per_event": None,
            "total_token_spend": 0,
        }

        # Mock previous period summary row (for trend calculation)
        mock_prev_summary_row = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "success_rate": None,
            "avg_processing_time_ms": None,
        }

        # Mock empty top repositories and event types
        mock_top_repos: list[dict[str, Any]] = []
        mock_event_types: list[dict[str, Any]] = []

        # Mock time range
        mock_time_range = {
            "first_event_time": None,
            "last_event_time": None,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            # Setup fetchrow to return summary_row, time_range_row, and prev_summary_row
            # Note: prev_summary_row is fetched after summary_row but before time_range_row in the code
            # Order: summary_row (line 862), top_repos (fetch line 863), event_types (fetch line 864),
            #        time_range_row (line 865), prev_summary_row (line 870)
            mock_db.fetchrow = AsyncMock(side_effect=[mock_summary_row, mock_time_range, mock_prev_summary_row])
            # Setup fetch to return top_repos and event_types
            mock_db.fetch = AsyncMock(side_effect=[mock_top_repos, mock_event_types])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/summary",
                params={
                    "start_time": "2024-01-15T00:00:00Z",
                    "end_time": "2024-01-16T00:00:00Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK

    def test_get_metrics_summary_database_unavailable(self) -> None:
        """Test metrics summary when database unavailable."""
        with patch("backend.routes.api.summary.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/summary")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestWebhookEndpointAdditional:
    """Additional tests for webhook endpoint edge cases."""

    def test_webhook_extracts_pr_number_from_issue(self) -> None:
        """Test webhook extracts PR number from issue with pull_request field."""
        payload = {
            "action": "created",
            "issue": {
                "number": 123,
                "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/123"},
            },
            "repository": {"full_name": "testorg/testrepo"},
            "sender": {"login": "testuser"},
        }

        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            mock_tracker.track_webhook_event = AsyncMock()
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)
            response = client.post(
                "/metrics",
                json=payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-issue-pr",
                    "X-GitHub-Event": "issue_comment",
                },
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify PR number was extracted from issue
            mock_tracker.track_webhook_event.assert_called_once()
            call_kwargs = mock_tracker.track_webhook_event.call_args[1]
            assert call_kwargs["pr_number"] == 123

    def test_webhook_tracking_failure_does_not_fail_webhook(self) -> None:
        """Test webhook succeeds even if tracking fails."""
        payload = {
            "action": "opened",
            "pull_request": {"number": 42},
            "repository": {"full_name": "testorg/testrepo"},
            "sender": {"login": "testuser"},
        }

        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
        ):
            mock_tracker.track_webhook_event = AsyncMock(side_effect=Exception("Tracking failed"))
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)
            response = client.post(
                "/metrics",
                json=payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-track-fail",
                    "X-GitHub-Event": "pull_request",
                },
            )

            # Webhook should still succeed
            assert response.status_code == status.HTTP_200_OK

    def test_webhook_tracking_failure_emits_critical_alert(self) -> None:
        """Test webhook tracking failure emits CRITICAL alert log for operational monitoring."""
        payload = {
            "action": "opened",
            "pull_request": {"number": 123},
            "repository": {"full_name": "testorg/testrepo"},
            "sender": {"login": "testuser"},
        }

        with (
            patch("backend.routes.webhooks.metrics_tracker") as mock_tracker,
            patch("backend.routes.webhooks.allowed_ips", ()),
            patch("backend.routes.webhooks.get_config") as mock_config,
            patch("backend.routes.webhooks.LOGGER") as mock_logger,
        ):
            mock_tracker.track_webhook_event = AsyncMock(side_effect=Exception("Database connection failed"))
            config_mock = Mock()
            config_mock.webhook.secret = ""
            mock_config.return_value = config_mock

            client = TestClient(app)
            response = client.post(
                "/metrics",
                json=payload,
                headers={
                    "X-GitHub-Delivery": "test-delivery-critical",
                    "X-GitHub-Event": "pull_request",
                },
            )

            # Webhook should still succeed
            assert response.status_code == status.HTTP_200_OK

            # Verify CRITICAL log was emitted with alertable structured fields
            mock_logger.critical.assert_called_once()
            critical_call_args = mock_logger.critical.call_args

            # Verify critical message
            assert "METRICS_TRACKING_FAILURE" in critical_call_args[0][0]
            assert "potential data loss" in critical_call_args[0][0]

            # Verify structured fields for operational alerting
            extra = critical_call_args[1]["extra"]
            assert extra["alert"] == "metrics_tracking_failure"
            assert extra["severity"] == "critical"
            assert extra["delivery_id"] == "test-delivery-critical"
            assert extra["repository"] == "testorg/testrepo"
            assert extra["event_type"] == "pull_request"
            assert extra["action"] == "opened"
            assert extra["sender"] == "testuser"
            assert extra["pr_number"] == 123
            assert extra["impact"] == "data_loss"
            assert "processing_time_ms" in extra

            # Verify exception details are also logged
            mock_logger.exception.assert_called_once()
            exception_call_args = mock_logger.exception.call_args
            assert "Failed to track webhook event" in exception_call_args[0][0]


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_without_static_directory(self) -> None:
        """Test create_app when static directory doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            test_app = create_app()

            assert test_app is not None
            assert test_app.title == "GitHub Metrics"

    def test_create_app_with_static_directory(self) -> None:
        """Test create_app mounts static files when directory exists."""
        with patch("pathlib.Path.exists", return_value=True):
            test_app = create_app()

            assert test_app is not None
            # Static files would be mounted in routes


class TestContributorsEndpoint:
    """Tests for /api/metrics/contributors endpoint."""

    def test_get_contributors_success(self) -> None:
        """Test successful contributors retrieval."""
        # Mock count queries (4 now - includes reviewers raw count for OOM safeguard)
        mock_creators_count = 5
        mock_reviewers_raw_count = 3  # Raw review rows (before Python processing)
        mock_approvers_count = 2
        mock_lgtm_count = 1

        # Mock data queries
        mock_creators_rows = [
            {
                "user": "alice",
                "total_prs": 10,
                "merged_prs": 8,
                "closed_prs": 2,
                "avg_commits": 3.5,
            },
        ]
        # Reviewers now returns raw review data (not aggregated)
        mock_reviewers_raw_rows = [
            {
                "user": "bob",
                "repository": "org/repo",
                "pr_number": 1,
                "pr_author": "alice",
                "pr_sig_label": "sig-storage",
            },
            {
                "user": "bob",
                "repository": "org/repo",
                "pr_number": 2,
                "pr_author": "alice",
                "pr_sig_label": "sig-network",
            },
            {
                "user": "bob",
                "repository": "org/repo",
                "pr_number": 1,
                "pr_author": "alice",
                "pr_sig_label": "sig-storage",
            },
        ]
        mock_approvers_rows = [
            {
                "user": "charlie",
                "total_approvals": 8,
                "prs_approved": 7,
            },
        ]
        mock_lgtm_rows = [
            {
                "user": "dave",
                "total_lgtm": 5,
                "prs_lgtm": 5,
            },
        ]

        with (
            patch("backend.routes.api.contributors.db_manager") as mock_db,
            patch("backend.routes.api.contributors.sig_teams_config"),
        ):
            # Mock fetchval for count queries (4 calls - includes reviewers raw count)
            mock_db.fetchval = AsyncMock(
                side_effect=[
                    mock_creators_count,
                    mock_reviewers_raw_count,
                    mock_approvers_count,
                    mock_lgtm_count,
                ],
            )
            # Mock fetch for data queries (4 calls)
            mock_db.fetch = AsyncMock(
                side_effect=[mock_creators_rows, mock_reviewers_raw_rows, mock_approvers_rows, mock_lgtm_rows],
            )

            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "pr_creators" in data
            assert "pr_reviewers" in data
            assert "pr_approvers" in data
            assert "pr_lgtm" in data

            # Verify pr_creators
            assert len(data["pr_creators"]["data"]) == 1
            assert data["pr_creators"]["data"][0]["user"] == "alice"
            assert data["pr_creators"]["data"][0]["total_prs"] == 10
            assert data["pr_creators"]["pagination"]["total"] == mock_creators_count

            # Verify pr_reviewers (computed in Python)
            assert len(data["pr_reviewers"]["data"]) == 1
            assert data["pr_reviewers"]["data"][0]["user"] == "bob"
            assert data["pr_reviewers"]["data"][0]["total_reviews"] == 3
            assert data["pr_reviewers"]["data"][0]["prs_reviewed"] == 2
            assert data["pr_reviewers"]["pagination"]["total"] == 1

    def test_get_contributors_with_filters(self) -> None:
        """Test contributors with user and repository filters."""
        with (
            patch("backend.routes.api.contributors.db_manager") as mock_db,
            patch("backend.routes.api.contributors.sig_teams_config"),
        ):
            # 4 fetchval calls (includes reviewers raw count)
            mock_db.fetchval = AsyncMock(side_effect=[0, 0, 0, 0])
            mock_db.fetch = AsyncMock(side_effect=[[], [], [], []])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/contributors",
                params={
                    "user": "testuser",
                    "repository": "testorg/testrepo",
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pr_creators"]["pagination"]["total"] == 0

    def test_get_contributors_pagination(self) -> None:
        """Test contributors pagination."""
        # Mock counts for pagination calculation
        mock_creators_count = 100
        mock_reviewers_raw_count = 50
        mock_approvers_count = 60
        mock_lgtm_count = 40

        with (
            patch("backend.routes.api.contributors.db_manager") as mock_db,
            patch("backend.routes.api.contributors.sig_teams_config"),
        ):
            # 4 fetchval calls (includes reviewers raw count)
            mock_db.fetchval = AsyncMock(
                side_effect=[
                    mock_creators_count,
                    mock_reviewers_raw_count,
                    mock_approvers_count,
                    mock_lgtm_count,
                ],
            )
            mock_db.fetch = AsyncMock(side_effect=[[], [], [], []])

            client = TestClient(app)
            response = client.get("/api/metrics/contributors", params={"page": 2, "page_size": 10})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Check pagination metadata
            assert data["pr_creators"]["pagination"]["page"] == 2
            assert data["pr_creators"]["pagination"]["page_size"] == 10
            assert data["pr_creators"]["pagination"]["total"] == 100
            assert data["pr_creators"]["pagination"]["total_pages"] == 10
            assert data["pr_creators"]["pagination"]["has_next"] is True
            assert data["pr_creators"]["pagination"]["has_prev"] is True

    def test_get_contributors_database_unavailable(self) -> None:
        """Test contributors when database unavailable."""
        with patch("backend.routes.api.contributors.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_contributors_database_error(self) -> None:
        """Test contributors handles database errors."""
        with patch("backend.routes.api.contributors.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_contributors_cancelled_error(self) -> None:
        """Test contributors handles asyncio.CancelledError."""

        with patch("backend.routes.api.contributors.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=asyncio.CancelledError)

            client = TestClient(app)
            # CancelledError is re-raised and handled by FastAPI/ASGI server
            # TestClient may wrap it in concurrent.futures.CancelledError (detect cancellation, not specific type)
            with pytest.raises((asyncio.CancelledError, concurrent.futures.CancelledError)):
                client.get("/api/metrics/contributors")

    def test_get_contributors_too_many_review_rows(self) -> None:
        """Test contributors rejects queries with too many review rows (OOM safeguard)."""
        # Mock count queries - pr_reviewers_raw_count exceeds MAX_REVIEWERS_RAW_ROWS (100,000)
        mock_creators_count = 5
        mock_reviewers_raw_count = 150_000  # Exceeds limit
        mock_approvers_count = 2
        mock_lgtm_count = 1

        with (
            patch("backend.routes.api.contributors.db_manager") as mock_db,
            patch("backend.routes.api.contributors.sig_teams_config"),
        ):
            # Mock fetchval for count queries (4 calls now - includes reviewers raw count)
            mock_db.fetchval = AsyncMock(
                side_effect=[
                    mock_creators_count,
                    mock_reviewers_raw_count,
                    mock_approvers_count,
                    mock_lgtm_count,
                ],
            )

            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            # Should return 413 Request Entity Too Large
            assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            assert "exceeding maximum of 100000" in response.json()["detail"]
            assert "narrow your filters" in response.json()["detail"].lower()


class TestUserPullRequestsEndpoint:
    """Tests for /api/metrics/user-prs endpoint."""

    def test_get_user_prs_success(self) -> None:
        """Test successful user PRs retrieval."""
        mock_count_row = {"total": 10}
        mock_pr_rows = [
            {
                "pr_number": 123,
                "title": "Test PR",
                "owner": "testuser",
                "repository": "testorg/testrepo",
                "state": "closed",
                "merged": True,
                "url": "https://github.com/testorg/testrepo/pull/123",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-16T12:00:00Z",
                "commits_count": 5,
                "head_sha": "abc123def456",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"user": "testuser"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["number"] == 123
            assert data["data"][0]["merged"] is True
            assert data["pagination"]["total"] == 10

    def test_get_user_prs_without_user_filter(self) -> None:
        """Test user PRs without user filter (shows all PRs)."""
        mock_count_row = {"total": 5}

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 5

    def test_get_user_prs_with_filters(self) -> None:
        """Test user PRs with multiple filters."""
        mock_count_row = {"total": 0}

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs",
                params={
                    "user": "testuser",
                    "repository": "testorg/testrepo",
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_pagination(self) -> None:
        """Test user PRs pagination."""
        mock_count_row = {"total": 50}

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"page": 2, "page_size": 20})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["total_pages"] == 3
            assert data["pagination"]["has_next"] is True
            assert data["pagination"]["has_prev"] is True

    def test_get_user_prs_database_unavailable(self) -> None:
        """Test user PRs when database unavailable."""
        with patch("backend.routes.api.user_prs.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/user-prs")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_user_prs_database_error(self) -> None:
        """Test user PRs handles database errors."""
        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_user_prs_invalid_role(self) -> None:
        """Test user PRs with invalid role parameter."""
        with patch("backend.routes.api.user_prs.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "invalid_role"})

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid role" in response.json()["detail"]

    def test_get_user_prs_pr_approvers_role(self) -> None:
        """Test user PRs with PR_APPROVERS role."""
        mock_count_row = {"total": 5}
        mock_pr_rows = [
            {
                "pr_number": 123,
                "title": "Approved PR",
                "owner": "alice",
                "repository": "testorg/testrepo",
                "state": "closed",
                "merged": True,
                "url": "https://github.com/testorg/testrepo/pull/123",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-16T12:00:00Z",
                "commits_count": 5,
                "head_sha": "abc123def456",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_approvers", "users": ["alice", "bob"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 5
            assert len(data["data"]) == 1

    def test_get_user_prs_pr_lgtm_role(self) -> None:
        """Test user PRs with PR_LGTM role."""
        mock_count_row = {"total": 3}
        mock_pr_rows = [
            {
                "pr_number": 456,
                "title": "LGTM PR",
                "owner": "charlie",
                "repository": "testorg/repo2",
                "state": "open",
                "merged": False,
                "url": "https://github.com/testorg/repo2/pull/456",
                "created_at": "2024-01-20T10:00:00Z",
                "updated_at": "2024-01-21T12:00:00Z",
                "commits_count": 3,
                "head_sha": "def456ghi789",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_lgtm", "exclude_users": ["bot-user"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 3

    def test_get_user_prs_pr_reviewers_role(self) -> None:
        """Test user PRs with PR_REVIEWERS role."""
        mock_count_row = {"total": 8}
        mock_pr_rows = [
            {
                "pr_number": 789,
                "title": "Reviewed PR",
                "owner": "dave",
                "repository": "testorg/repo3",
                "state": "closed",
                "merged": True,
                "url": "https://github.com/testorg/repo3/pull/789",
                "created_at": "2024-01-25T10:00:00Z",
                "updated_at": "2024-01-26T12:00:00Z",
                "commits_count": 7,
                "head_sha": "ghi789jkl012",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs", params={"role": "pr_reviewers", "repositories": ["testorg/repo3"]}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 8

    def test_get_user_prs_pr_approvers_with_time_range(self) -> None:
        """Test user PRs with PR_APPROVERS role and time range filters."""
        mock_count_row = {"total": 2}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs",
                params={
                    "role": "pr_approvers",
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 2

    def test_get_user_prs_pr_reviewers_with_users_filter(self) -> None:
        """Test user PRs with PR_REVIEWERS role and users filter."""
        mock_count_row = {"total": 4}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_reviewers", "users": ["alice"]})

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_pr_lgtm_with_repositories(self) -> None:
        """Test user PRs with PR_LGTM role and repositories filter."""
        mock_count_row = {"total": 6}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs", params={"role": "pr_lgtm", "repositories": ["testorg/repo1", "testorg/repo2"]}
            )

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_pr_creators_role(self) -> None:
        """Test user PRs with PR_CREATORS role."""
        mock_count_row = {"total": 10}
        mock_pr_rows = [
            {
                "pr_number": 111,
                "title": "Created PR",
                "owner": "alice",
                "repository": "testorg/repo1",
                "state": "open",
                "merged": False,
                "url": "https://github.com/testorg/repo1/pull/111",
                "created_at": "2024-02-01T10:00:00Z",
                "updated_at": "2024-02-02T12:00:00Z",
                "commits_count": 4,
                "head_sha": "jkl012mno345",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_creators", "users": ["alice"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 10

    def test_get_user_prs_pr_creators_with_exclude_users(self) -> None:
        """Test user PRs with PR_CREATORS role and exclude_users filter."""
        mock_count_row = {"total": 7}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_creators", "exclude_users": ["bot"]})

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_pr_creators_with_time_and_repo_filters(self) -> None:
        """Test user PRs with PR_CREATORS role, time range, and repository filters."""
        mock_count_row = {"total": 3}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs",
                params={
                    "role": "pr_creators",
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                    "repositories": ["testorg/repo1"],
                },
            )

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_pr_approvers_with_all_filters(self) -> None:
        """Test user PRs with PR_APPROVERS role and all filters combined."""
        mock_count_row = {"total": 1}
        mock_pr_rows = [
            {
                "pr_number": 999,
                "title": "Fully Filtered PR",
                "owner": "eve",
                "repository": "testorg/repo4",
                "state": "closed",
                "merged": True,
                "url": "https://github.com/testorg/repo4/pull/999",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-16T12:00:00Z",
                "commits_count": 2,
                "head_sha": "mno345pqr678",  # pragma: allowlist secret
            },
        ]

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/user-prs",
                params={
                    "role": "pr_approvers",
                    "users": ["alice", "bob"],
                    "exclude_users": ["bot-user"],
                    "repositories": ["testorg/repo4"],
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 1
            assert len(data["data"]) == 1

    def test_get_user_prs_no_role_with_exclude_users(self) -> None:
        """Test user PRs without role but with exclude_users filter."""
        mock_count_row = {"total": 12}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"exclude_users": ["bot-user", "dependabot"]})

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_no_role_with_repositories(self) -> None:
        """Test user PRs without role but with repositories filter."""
        mock_count_row = {"total": 15}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"repositories": ["testorg/repo1"]})

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_no_role_with_users_filter(self) -> None:
        """Test user PRs without role but with users filter (checks pr_author or sender)."""
        mock_count_row = {"total": 8}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"users": ["alice", "bob"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["total"] == 8

    def test_get_user_prs_pr_reviewers_with_exclude_users(self) -> None:
        """Test user PRs with PR_REVIEWERS role and exclude_users filter."""
        mock_count_row = {"total": 5}
        mock_pr_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.user_prs.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_count_row)
            mock_db.fetch = AsyncMock(return_value=mock_pr_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"role": "pr_reviewers", "exclude_users": ["bot"]})

            assert response.status_code == status.HTTP_200_OK

    def test_get_user_prs_http_exception_reraise(self) -> None:
        """Test user PRs re-raises HTTPException from parse_datetime_string."""
        with patch("backend.routes.api.user_prs.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/user-prs", params={"start_time": "invalid-date"})

            # Should get the HTTPException from parse_datetime_string
            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTrendsEndpoint:
    """Tests for /api/metrics/trends endpoint."""

    def test_get_trends_success(self) -> None:
        """Test successful trends retrieval."""
        mock_rows = [
            {
                "bucket": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "total_events": 50,
                "successful_events": 48,
                "failed_events": 2,
            },
            {
                "bucket": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "total_events": 45,
                "successful_events": 44,
                "failed_events": 1,
            },
        ]

        with patch("backend.routes.api.trends.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(return_value=mock_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/trends", params={"bucket": "hour"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "trends" in data
            assert len(data["trends"]) == 2
            assert data["trends"][0]["total_events"] == 50
            assert data["trends"][0]["successful_events"] == 48

    def test_get_trends_with_time_range(self) -> None:
        """Test trends with time range filters."""
        with patch("backend.routes.api.trends.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/trends",
                params={
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                    "bucket": "day",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["time_range"]["start_time"] == "2024-01-01T00:00:00+00:00"

    def test_get_trends_invalid_bucket(self) -> None:
        """Test trends with invalid bucket parameter."""
        with patch("backend.routes.api.trends.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/trends", params={"bucket": "invalid"})

            # FastAPI validation should reject this
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_trends_database_unavailable(self) -> None:
        """Test trends when database unavailable."""
        with patch("backend.routes.api.trends.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/trends")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_trends_database_error(self) -> None:
        """Test trends handles database errors."""
        with patch("backend.routes.api.trends.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/trends")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_trends_cancelled_error(self) -> None:
        """Test trends handles asyncio.CancelledError."""
        with patch("backend.routes.api.trends.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=asyncio.CancelledError)

            client = TestClient(app)
            response = client.get("/api/metrics/trends")

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.json()["detail"] == "Request was cancelled"


class TestMetricsSummaryTrends:
    """Tests for metrics summary trend calculations."""

    def test_get_metrics_summary_with_trends(self) -> None:
        """Test metrics summary with trend calculations."""
        # Current period summary
        mock_summary_row = {
            "total_events": 100,
            "successful_events": 95,
            "failed_events": 5,
            "success_rate": 95.0,
            "avg_processing_time_ms": 150,
            "median_processing_time_ms": 140,
            "p95_processing_time_ms": 300,
            "max_processing_time_ms": 500,
            "total_api_calls": 300,
            "avg_api_calls_per_event": 3.0,
            "total_token_spend": 300,
        }

        # Previous period summary (for trend calculation)
        mock_prev_summary_row = {
            "total_events": 80,
            "successful_events": 75,
            "failed_events": 5,
            "success_rate": 93.75,
            "avg_processing_time_ms": 170,
        }

        # Mock time range with actual datetime objects
        start_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        end_time = datetime(2024, 1, 16, 0, 0, 0, tzinfo=UTC)
        mock_time_range = {
            "first_event_time": start_time,
            "last_event_time": end_time,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            # Order: summary_row, top_repos, event_types, time_range_row, prev_summary_row
            mock_db.fetchrow = AsyncMock(side_effect=[mock_summary_row, mock_time_range, mock_prev_summary_row])
            mock_db.fetch = AsyncMock(side_effect=[[], []])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/summary",
                params={
                    "start_time": "2024-01-15T00:00:00Z",
                    "end_time": "2024-01-16T00:00:00Z",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify trend calculations are present
            assert "total_events_trend" in data["summary"]
            assert "success_rate_trend" in data["summary"]
            assert "failed_events_trend" in data["summary"]
            assert "avg_duration_trend" in data["summary"]

            # Verify event rate calculations
            assert "hourly_event_rate" in data
            assert "daily_event_rate" in data

    def test_get_metrics_summary_with_time_range_calculations(self) -> None:
        """Test metrics summary time range and rate calculations."""
        # Mock summary with data
        mock_summary_row = {
            "total_events": 240,
            "successful_events": 230,
            "failed_events": 10,
            "success_rate": 95.83,
            "avg_processing_time_ms": 150,
            "median_processing_time_ms": 140,
            "p95_processing_time_ms": 300,
            "max_processing_time_ms": 500,
            "total_api_calls": 720,
            "avg_api_calls_per_event": 3.0,
            "total_token_spend": 720,
        }

        # Mock time range - 24 hour period
        start_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        end_time = datetime(2024, 1, 16, 0, 0, 0, tzinfo=UTC)
        mock_time_range = {
            "first_event_time": start_time,
            "last_event_time": end_time,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            # Order: summary_row, top_repos, event_types, time_range_row (no prev period)
            mock_db.fetchrow = AsyncMock(side_effect=[mock_summary_row, mock_time_range])
            mock_db.fetch = AsyncMock(side_effect=[[], []])

            client = TestClient(app)
            response = client.get("/api/metrics/summary")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # With 240 events over 24 hours, hourly rate should be 10
            assert data["hourly_event_rate"] == 10.0
            # Daily rate should be 240
            assert data["daily_event_rate"] == 240.0


class TestHTTPExceptionReraise:
    """Tests for HTTPException re-raise in error handlers."""

    def test_webhook_events_reraises_http_exception(self) -> None:
        """Test webhook events re-raises HTTPException from parse_datetime_string."""
        with patch("backend.routes.api.webhooks.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks", params={"start_time": "invalid"})

            # Should get the HTTPException from parse_datetime_string
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_repositories_reraises_http_exception(self) -> None:
        """Test repositories re-raises HTTPException from parse_datetime_string."""
        with patch("backend.routes.api.repositories.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/repositories", params={"end_time": "invalid"})

            # Should get the HTTPException from parse_datetime_string
            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCalculateTrendFunction:
    """Tests for calculate_trend helper function in metrics summary."""

    def test_calculate_trend_with_positive_change(self) -> None:
        """Test trend calculation with positive change."""
        # This is tested implicitly through the metrics summary endpoint
        # The function is defined inside get_metrics_summary and calculates:
        # - total_events_trend
        # - success_rate_trend
        # - failed_events_trend
        # - avg_duration_trend

        mock_summary_row = {
            "total_events": 100,
            "successful_events": 95,
            "failed_events": 5,
            "success_rate": 95.0,
            "avg_processing_time_ms": 150,
            "median_processing_time_ms": 140,
            "p95_processing_time_ms": 300,
            "max_processing_time_ms": 500,
            "total_api_calls": 300,
            "avg_api_calls_per_event": 3.0,
            "total_token_spend": 300,
        }

        # Previous period with lower values (should show positive trend)
        mock_prev_summary_row = {
            "total_events": 50,
            "successful_events": 45,
            "failed_events": 5,
            "success_rate": 90.0,
            "avg_processing_time_ms": 200,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_summary_row,
                    {"first_event_time": None, "last_event_time": None},
                    mock_prev_summary_row,
                ],
            )
            mock_db.fetch = AsyncMock(side_effect=[[], []])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/summary",
                params={"start_time": "2024-01-15T00:00:00Z", "end_time": "2024-01-16T00:00:00Z"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # 100 vs 50 = 100% increase
            assert data["summary"]["total_events_trend"] == 100.0

    def test_calculate_trend_with_zero_previous(self) -> None:
        """Test trend calculation when previous period is zero."""
        mock_summary_row = {
            "total_events": 100,
            "successful_events": 95,
            "failed_events": 5,
            "success_rate": 95.0,
            "avg_processing_time_ms": 150,
            "median_processing_time_ms": 140,
            "p95_processing_time_ms": 300,
            "max_processing_time_ms": 500,
            "total_api_calls": 300,
            "avg_api_calls_per_event": 3.0,
            "total_token_spend": 300,
        }

        # Previous period with zero values
        mock_prev_summary_row = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "success_rate": None,
            "avg_processing_time_ms": None,
        }

        with patch("backend.routes.api.summary.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_summary_row,
                    {"first_event_time": None, "last_event_time": None},
                    mock_prev_summary_row,
                ],
            )
            mock_db.fetch = AsyncMock(side_effect=[[], []])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/summary",
                params={"start_time": "2024-01-15T00:00:00Z", "end_time": "2024-01-16T00:00:00Z"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # When previous is 0 and current > 0, trend should be 100.0
            assert data["summary"]["total_events_trend"] == 100.0


class TestCrossTeamReviewsEndpoint:
    """Tests for /api/metrics/cross-team-reviews endpoint."""

    def test_get_cross_team_reviews_empty(self) -> None:
        """Test cross-team reviews returns empty data when no reviews exist."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            # Mock database fetch - no review events
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            assert "data" in data
            assert "summary" in data
            assert "pagination" in data

            # Verify empty data
            assert data["data"] == []
            assert data["summary"]["total_cross_team_reviews"] == 0
            assert data["summary"]["by_reviewer_team"] == {}
            assert data["summary"]["by_pr_team"] == {}

            # Verify pagination
            assert data["pagination"]["total"] == 0
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["page_size"] == 25

    def test_get_cross_team_reviews_with_filters(self) -> None:
        """Test cross-team reviews with time range, repositories, and team filters."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(
            side_effect=lambda repo, user: {
                ("org/repo1", "alice"): "sig-storage",
                ("org/repo1", "bob"): "sig-storage",
            }.get((repo, user))
        )
        mock_sig_config.is_cross_team_review = Mock(
            side_effect=lambda repo, user, label: {
                ("org/repo1", "alice", "sig-network"): True,
                ("org/repo1", "bob", "sig-compute"): True,
            }.get((repo, user, label))
        )

        # Mock database rows with proper webhook payload structure
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "alice",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            },
            {
                "pr_number": 456,
                "repository": "org/repo1",
                "reviewer": "bob",
                "review_type": "changes_requested",
                "created_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-compute",
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/cross-team-reviews",
                params={
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                    "repositories": ["org/repo1"],
                    "reviewer_team": "sig-storage",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify data array
            assert len(data["data"]) == 2
            assert data["data"][0]["pr_number"] == 123
            assert data["data"][0]["reviewer"] == "alice"
            assert data["data"][0]["reviewer_team"] == "sig-storage"
            assert data["data"][0]["pr_sig_label"] == "sig-network"
            assert data["data"][0]["review_type"] == "approved"

            # Verify summary
            assert data["summary"]["total_cross_team_reviews"] == 2
            assert data["summary"]["by_reviewer_team"]["sig-storage"] == 2
            assert data["summary"]["by_pr_team"]["sig-network"] == 1
            assert data["summary"]["by_pr_team"]["sig-compute"] == 1

            # Verify pagination
            assert data["pagination"]["total"] == 2
            assert data["pagination"]["page"] == 1

    def test_get_cross_team_reviews_filters_non_cross_team(self) -> None:
        """Test that non-cross-team reviews are filtered out."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(return_value="sig-storage")
        # Simulate is_cross_team_review returning False for same-team review
        mock_sig_config.is_cross_team_review = Mock(return_value=False)

        # Mock database rows
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "alice",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-storage",  # Same team as reviewer
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be filtered out because it's not cross-team
            assert len(data["data"]) == 0
            assert data["summary"]["total_cross_team_reviews"] == 0

    def test_get_cross_team_reviews_filters_no_sig_label(self) -> None:
        """Test that reviews without sig labels are filtered out."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True

        # Mock database rows - PR without sig label
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "alice",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": None,  # No sig label
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be filtered out because no sig label
            assert len(data["data"]) == 0
            assert data["summary"]["total_cross_team_reviews"] == 0

    def test_get_cross_team_reviews_filters_unknown_reviewer(self) -> None:
        """Test that reviews from unknown reviewers (not in config) are filtered out."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(return_value=None)  # Unknown reviewer
        mock_sig_config.is_cross_team_review = Mock(return_value=None)  # Cannot determine

        # Mock database rows
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "unknown_user",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should be filtered out because reviewer not in config
            assert len(data["data"]) == 0
            assert data["summary"]["total_cross_team_reviews"] == 0

    def test_get_cross_team_reviews_pagination(self) -> None:
        """Test cross-team reviews pagination with Python-level filtering."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(return_value="sig-storage")
        mock_sig_config.is_cross_team_review = Mock(return_value=True)

        # Create 50 mock rows
        mock_db_rows = [
            {
                "pr_number": i,
                "repository": "org/repo1",
                "reviewer": f"user{i}",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            }
            for i in range(50)
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/cross-team-reviews",
                params={"page": 2, "page_size": 10},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pagination metadata
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["page_size"] == 10
            assert data["pagination"]["total"] == 50
            assert data["pagination"]["total_pages"] == 5
            assert data["pagination"]["has_next"] is True
            assert data["pagination"]["has_prev"] is True

            # Verify we get the right page of data (items 10-19)
            assert len(data["data"]) == 10
            assert data["data"][0]["pr_number"] == 10

    def test_get_cross_team_reviews_with_pr_team_filter(self) -> None:
        """Test cross-team reviews with PR team filter."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(return_value="sig-storage")
        mock_sig_config.is_cross_team_review = Mock(return_value=True)

        # Mock database rows with different PR teams
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "alice",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            },
            {
                "pr_number": 456,
                "repository": "org/repo1",
                "reviewer": "bob",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-compute",
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/cross-team-reviews",
                params={"pr_team": "sig-network"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should only include sig-network PR
            assert data["pagination"]["total"] == 1
            assert len(data["data"]) == 1
            assert data["data"][0]["pr_sig_label"] == "sig-network"

    def test_get_cross_team_reviews_with_reviewer_team_filter(self) -> None:
        """Test cross-team reviews with reviewer team filter."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.get_user_team = Mock(
            side_effect=lambda repo, user: {
                ("org/repo1", "alice"): "sig-storage",
                ("org/repo1", "bob"): "sig-compute",
            }.get((repo, user))
        )
        mock_sig_config.is_cross_team_review = Mock(return_value=True)

        # Mock database rows with different reviewers
        mock_db_rows = [
            {
                "pr_number": 123,
                "repository": "org/repo1",
                "reviewer": "alice",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            },
            {
                "pr_number": 456,
                "repository": "org/repo1",
                "reviewer": "bob",
                "review_type": "approved",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "extracted_pr_sig_label": "sig-network",
            },
        ]

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(return_value=mock_db_rows)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/cross-team-reviews",
                params={"reviewer_team": "sig-storage"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should only include alice (sig-storage reviewer)
            assert data["pagination"]["total"] == 1
            assert len(data["data"]) == 1
            assert data["data"][0]["reviewer"] == "alice"
            assert data["data"][0]["reviewer_team"] == "sig-storage"

    def test_get_cross_team_reviews_sig_config_not_loaded(self) -> None:
        """Test cross-team reviews when SIG config not loaded."""
        # Create mock SIG teams config that's not loaded
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = False

        with (
            patch("backend.routes.api.cross_team.db_manager"),
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"] == []
            assert data["summary"]["total_cross_team_reviews"] == 0

    def test_get_cross_team_reviews_sig_config_none(self) -> None:
        """Test cross-team reviews when SIG config is None."""
        with (
            patch("backend.routes.api.cross_team.db_manager"),
            patch("backend.routes.api.cross_team.sig_teams_config", None),
        ):
            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"] == []
            assert data["summary"]["total_cross_team_reviews"] == 0

    def test_get_cross_team_reviews_database_unavailable(self) -> None:
        """Test cross-team reviews when database unavailable."""
        with patch("backend.routes.api.cross_team.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Metrics database not available" in response.json()["detail"]

    def test_get_cross_team_reviews_database_error(self) -> None:
        """Test cross-team reviews handles database errors."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/cross-team-reviews")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to fetch cross-team review metrics" in response.json()["detail"]

    def test_get_cross_team_reviews_invalid_datetime(self) -> None:
        """Test cross-team reviews with invalid datetime format."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True

        with (
            patch("backend.routes.api.cross_team.db_manager"),
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            client = TestClient(app)
            response = client.get(
                "/api/metrics/cross-team-reviews",
                params={"start_time": "invalid-date"},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid datetime format" in response.json()["detail"]

    def test_get_cross_team_reviews_cancelled_error(self) -> None:
        """Test cross-team reviews handles asyncio.CancelledError."""
        # Create mock SIG teams config
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True

        with (
            patch("backend.routes.api.cross_team.db_manager") as mock_db,
            patch("backend.routes.api.cross_team.sig_teams_config", mock_sig_config),
        ):
            mock_db.fetch = AsyncMock(side_effect=asyncio.CancelledError)

            client = TestClient(app)
            # CancelledError is re-raised and handled by FastAPI/ASGI server
            # TestClient may wrap it in concurrent.futures.CancelledError (detect cancellation, not specific type)
            with pytest.raises((asyncio.CancelledError, concurrent.futures.CancelledError)):
                client.get("/api/metrics/cross-team-reviews")


class TestReviewTurnaroundEndpoint:
    """Tests for /api/metrics/turnaround endpoint."""

    def test_get_review_turnaround_success(self) -> None:
        """Test successful review turnaround metrics retrieval."""
        # Mock data for all queries
        mock_first_review_rows = [
            {"hours_to_first_review": 2.5},
            {"hours_to_first_review": 3.0},
        ]
        mock_approval_rows = [
            {"hours_to_approval": 8.0},
            {"hours_to_approval": 9.0},
        ]
        mock_verified_rows = [
            {"hours_to_verified": 10.0},
            {"hours_to_verified": 11.0},
        ]
        mock_changes_requested_rows = [
            {"hours_to_changes_requested": 4.5},
            {"hours_to_changes_requested": 5.0},
        ]
        mock_lifecycle_row = {
            "avg_hours": 24.5,
            "total_prs": 50,  # Completed PRs only
        }
        mock_total_prs_row = {
            "total_prs": 150,  # All PRs opened in time range
        }
        mock_by_repo_rows = [
            {
                "repository": "org/repo1",
                "avg_time_to_first_review_hours": 1.2,
                "avg_time_to_approval_hours": 4.5,
                "avg_time_to_first_verified_hours": 6.0,
                "avg_time_to_first_changes_requested_hours": 3.5,
                "avg_pr_lifecycle_hours": 12.0,
                "total_prs": 50,
            },
            {
                "repository": "org/repo2",
                "avg_time_to_first_review_hours": 2.8,
                "avg_time_to_approval_hours": 10.5,
                "avg_time_to_first_verified_hours": 12.5,
                "avg_time_to_first_changes_requested_hours": 6.0,
                "avg_pr_lifecycle_hours": 30.0,
                "total_prs": 100,
            },
        ]
        mock_by_reviewer_rows = [
            {
                "reviewer": "user1",
                "avg_response_time_hours": 1.5,
                "total_reviews": 30,
                "repositories": ["org/repo1", "org/repo2"],
            },
            {
                "reviewer": "user2",
                "avg_response_time_hours": 2.8,
                "total_reviews": 25,
                "repositories": ["org/repo1"],
            },
        ]

        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_first_review_rows,
                    mock_approval_rows,
                    mock_verified_rows,
                    mock_changes_requested_rows,
                    mock_by_repo_rows,
                    mock_by_reviewer_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_lifecycle_row,
                    mock_total_prs_row,
                ]
            )

            client = TestClient(app)
            response = client.get("/api/metrics/turnaround")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Check summary
            assert "summary" in data
            assert data["summary"]["avg_time_to_first_review_hours"] == 2.8
            assert data["summary"]["avg_time_to_approval_hours"] == 8.5
            assert data["summary"]["avg_time_to_first_verified_hours"] == 10.5
            assert data["summary"]["avg_time_to_first_changes_requested_hours"] == 4.8
            assert data["summary"]["avg_pr_lifecycle_hours"] == 24.5
            assert data["summary"]["total_prs_analyzed"] == 150

            # Check by_repository
            assert "by_repository" in data
            assert len(data["by_repository"]) == 2
            assert data["by_repository"][0]["repository"] == "org/repo1"
            assert data["by_repository"][0]["avg_time_to_first_review_hours"] == 1.2
            assert data["by_repository"][0]["avg_time_to_first_verified_hours"] == 6.0
            assert data["by_repository"][0]["avg_time_to_first_changes_requested_hours"] == 3.5

            # Check by_reviewer
            assert "by_reviewer" in data
            assert len(data["by_reviewer"]) == 2
            assert data["by_reviewer"][0]["reviewer"] == "user1"
            assert data["by_reviewer"][0]["total_reviews"] == 30
            assert data["by_reviewer"][0]["repositories_reviewed"] == ["org/repo1", "org/repo2"]

    def test_get_review_turnaround_with_filters(self) -> None:
        """Test review turnaround metrics with time and repository filters."""
        mock_first_review_rows = [{"hours_to_first_review": 1.5}]
        mock_approval_rows = [{"hours_to_approval": 4.0}]
        mock_verified_rows = [{"hours_to_verified": 5.5}]
        mock_changes_requested_rows = [{"hours_to_changes_requested": 3.0}]
        mock_lifecycle_row = {"avg_hours": 10.0, "total_prs": 10}  # Completed PRs only
        mock_total_prs_row = {"total_prs": 25}  # All PRs opened
        mock_by_repo_rows = [
            {
                "repository": "org/specific-repo",
                "avg_time_to_first_review_hours": 1.5,
                "avg_time_to_approval_hours": 4.0,
                "avg_time_to_first_verified_hours": 5.5,
                "avg_time_to_first_changes_requested_hours": 3.0,
                "avg_pr_lifecycle_hours": 10.0,
                "total_prs": 25,
            }
        ]
        mock_by_reviewer_rows = [
            {
                "reviewer": "reviewer1",
                "avg_response_time_hours": 1.5,
                "total_reviews": 15,
                "repositories": ["org/specific-repo"],
            }
        ]

        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_first_review_rows,
                    mock_approval_rows,
                    mock_verified_rows,
                    mock_changes_requested_rows,
                    mock_by_repo_rows,
                    mock_by_reviewer_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_lifecycle_row,
                    mock_total_prs_row,
                ]
            )

            client = TestClient(app)
            response = client.get(
                "/api/metrics/turnaround",
                params={
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                    "repository": "org/specific-repo",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["summary"]["total_prs_analyzed"] == 25
            assert len(data["by_repository"]) == 1
            assert data["by_repository"][0]["repository"] == "org/specific-repo"

    def test_get_review_turnaround_with_user_filter(self) -> None:
        """Test review turnaround metrics filtered by reviewer."""
        mock_first_review_rows = [{"hours_to_first_review": 2.0}]
        mock_approval_rows = [{"hours_to_approval": 6.0}]
        mock_verified_rows = [{"hours_to_verified": 7.5}]
        mock_changes_requested_rows = [{"hours_to_changes_requested": 4.0}]
        mock_lifecycle_row = {"avg_hours": 15.0, "total_prs": 20}  # Completed PRs only
        mock_total_prs_row = {"total_prs": 40}  # All PRs opened
        mock_by_repo_rows = [
            {
                "repository": "org/repo1",
                "avg_time_to_first_review_hours": 2.0,
                "avg_time_to_approval_hours": 6.0,
                "avg_time_to_first_verified_hours": 7.5,
                "avg_time_to_first_changes_requested_hours": 4.0,
                "avg_pr_lifecycle_hours": 15.0,
                "total_prs": 40,
            }
        ]
        mock_by_reviewer_rows = [
            {
                "reviewer": "specific-reviewer",
                "avg_response_time_hours": 2.0,
                "total_reviews": 20,
                "repositories": ["org/repo1", "org/repo2"],
            }
        ]

        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_first_review_rows,
                    mock_approval_rows,
                    mock_verified_rows,
                    mock_changes_requested_rows,
                    mock_by_repo_rows,
                    mock_by_reviewer_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_lifecycle_row,
                    mock_total_prs_row,
                ]
            )

            client = TestClient(app)
            response = client.get("/api/metrics/turnaround", params={"user": "specific-reviewer"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["by_reviewer"]) == 1
            assert data["by_reviewer"][0]["reviewer"] == "specific-reviewer"

    def test_get_review_turnaround_empty_results(self) -> None:
        """Test review turnaround metrics with no data."""
        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[[], [], [], [], [], []])
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    {"avg_hours": None, "total_prs": 0},  # lifecycle_row
                    {"total_prs": 0},  # total_prs_row
                ]
            )

            client = TestClient(app)
            response = client.get("/api/metrics/turnaround")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["summary"]["avg_time_to_first_review_hours"] == 0.0
            assert data["summary"]["avg_time_to_approval_hours"] == 0.0
            assert data["summary"]["avg_time_to_first_verified_hours"] == 0.0
            assert data["summary"]["avg_time_to_first_changes_requested_hours"] == 0.0
            assert data["summary"]["avg_pr_lifecycle_hours"] == 0.0
            assert data["summary"]["total_prs_analyzed"] == 0
            assert len(data["by_repository"]) == 0
            assert len(data["by_reviewer"]) == 0

    def test_get_review_turnaround_handles_null_values(self) -> None:
        """Test review turnaround metrics handles NULL values gracefully."""
        mock_first_review_rows = [{"hours_to_first_review": None}, {"hours_to_first_review": 3.0}]
        mock_approval_rows = [{"hours_to_approval": None}]
        mock_verified_rows = [{"hours_to_verified": None}]
        mock_changes_requested_rows = [{"hours_to_changes_requested": None}]
        mock_lifecycle_row = {"avg_hours": None, "total_prs": 5}  # Completed PRs only
        mock_total_prs_row = {"total_prs": 10}  # All PRs opened
        mock_by_repo_rows = [
            {
                "repository": "org/repo1",
                "avg_time_to_first_review_hours": None,
                "avg_time_to_approval_hours": None,
                "avg_time_to_first_verified_hours": None,
                "avg_time_to_first_changes_requested_hours": None,
                "avg_pr_lifecycle_hours": None,
                "total_prs": 10,
            }
        ]
        mock_by_reviewer_rows = [
            {
                "reviewer": "user1",
                "avg_response_time_hours": None,
                "total_reviews": 5,
                "repositories": ["org/repo1"],
            }
        ]

        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_first_review_rows,
                    mock_approval_rows,
                    mock_verified_rows,
                    mock_changes_requested_rows,
                    mock_by_repo_rows,
                    mock_by_reviewer_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    mock_lifecycle_row,
                    mock_total_prs_row,
                ]
            )

            client = TestClient(app)
            response = client.get("/api/metrics/turnaround")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should handle NULL values and still compute averages
            assert data["summary"]["avg_time_to_first_review_hours"] == 3.0
            assert data["summary"]["avg_time_to_approval_hours"] == 0.0
            assert data["summary"]["avg_time_to_first_verified_hours"] == 0.0
            assert data["summary"]["avg_time_to_first_changes_requested_hours"] == 0.0
            assert data["summary"]["avg_pr_lifecycle_hours"] == 0.0
            assert data["by_repository"][0]["avg_time_to_first_review_hours"] == 0.0
            assert data["by_repository"][0]["avg_time_to_first_verified_hours"] == 0.0
            assert data["by_repository"][0]["avg_time_to_first_changes_requested_hours"] == 0.0
            assert data["by_reviewer"][0]["avg_response_time_hours"] == 0.0

    def test_get_review_turnaround_invalid_datetime(self) -> None:
        """Test review turnaround metrics with invalid datetime format."""
        with patch("backend.routes.api.turnaround.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/turnaround", params={"start_time": "invalid-date"})

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid datetime format" in response.json()["detail"]

    def test_get_review_turnaround_database_unavailable(self) -> None:
        """Test review turnaround metrics when database is unavailable."""
        with patch("backend.routes.api.turnaround.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/turnaround")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database not available" in response.json()["detail"]

    def test_get_review_turnaround_database_error(self) -> None:
        """Test review turnaround metrics handles database errors."""
        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/turnaround")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to fetch review turnaround metrics" in response.json()["detail"]

    def test_get_review_turnaround_cancelled(self) -> None:
        """Test review turnaround metrics handles asyncio.CancelledError."""
        with patch("backend.routes.api.turnaround.db_manager") as mock_db:
            # Mock both fetch and fetchrow since endpoint uses asyncio.gather with both
            mock_db.fetch = AsyncMock(side_effect=asyncio.CancelledError)
            mock_db.fetchrow = AsyncMock(side_effect=asyncio.CancelledError)

            client = TestClient(app)
            # CancelledError is re-raised and handled by FastAPI/ASGI server
            # TestClient may wrap it in concurrent.futures.CancelledError (detect cancellation, not specific type)
            with pytest.raises((asyncio.CancelledError, concurrent.futures.CancelledError)):
                client.get("/api/metrics/turnaround")


class TestMaintainersEndpoint:
    """Tests for /api/metrics/maintainers endpoint.

    This endpoint returns repository maintainers configured in SIG teams YAML.
    Used by frontend to exclude maintainers from contributor metrics when the
    'Exclude Maintainers' filter is enabled.

    Response format:
        {
            "maintainers": {"org/repo": ["user1", "user2"]},
            "all_maintainers": ["user1", "user2", ...]
        }
    """

    def test_get_maintainers_success(self) -> None:
        """Test successful retrieval of maintainers."""
        # Create mock SIG teams config with maintainers
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.repositories = ["org/repo1", "org/repo2"]
        mock_sig_config.get_maintainers = Mock(
            side_effect=lambda repo: {
                "org/repo1": ["maintainer1", "maintainer2"],
                "org/repo2": ["maintainer3"],
            }.get(repo, [])
        )
        mock_sig_config.get_all_maintainers = Mock(return_value=["maintainer1", "maintainer2", "maintainer3"])

        with patch("backend.routes.api.maintainers.get_sig_teams_config", return_value=mock_sig_config):
            client = TestClient(app)
            response = client.get("/api/metrics/maintainers")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            assert "maintainers" in data
            assert "all_maintainers" in data

            # Verify maintainers per repository
            assert data["maintainers"]["org/repo1"] == ["maintainer1", "maintainer2"]
            assert data["maintainers"]["org/repo2"] == ["maintainer3"]

            # Verify all_maintainers list
            assert data["all_maintainers"] == ["maintainer1", "maintainer2", "maintainer3"]

    def test_get_maintainers_empty_repositories(self) -> None:
        """Test maintainers endpoint with repositories but no maintainers."""
        # Create mock SIG teams config with repositories but no maintainers
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = True
        mock_sig_config.repositories = ["org/repo1", "org/repo2"]
        mock_sig_config.get_maintainers = Mock(return_value=[])
        mock_sig_config.get_all_maintainers = Mock(return_value=[])

        with patch("backend.routes.api.maintainers.get_sig_teams_config", return_value=mock_sig_config):
            client = TestClient(app)
            response = client.get("/api/metrics/maintainers")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Should return empty structures
            assert data["maintainers"] == {}
            assert data["all_maintainers"] == []

    def test_get_maintainers_config_not_loaded(self) -> None:
        """Test maintainers endpoint when SIG config not loaded."""
        # Create mock SIG teams config that's not loaded
        mock_sig_config = Mock()
        mock_sig_config.is_loaded = False

        with patch("backend.routes.api.maintainers.get_sig_teams_config", return_value=mock_sig_config):
            client = TestClient(app)
            response = client.get("/api/metrics/maintainers")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["maintainers"] == {}
            assert data["all_maintainers"] == []
