"""Tests for FastAPI application endpoints.

Tests HTTP endpoints including:
- Health check endpoint
- Webhook receiver endpoint
- Dashboard endpoint
- API metrics endpoints
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from concurrent.futures import CancelledError
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import asyncpg
import httpx
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from github_metrics import app as app_module
from github_metrics.app import app, create_app, parse_datetime_string


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_healthy(self) -> None:
        """Test health endpoint returns healthy status."""
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.health_check = AsyncMock(return_value=False)

            client = TestClient(app)
            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] is False

    def test_health_check_without_db_manager(self) -> None:
        """Test health endpoint when db_manager is None."""
        with patch("github_metrics.app.db_manager", None):
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
            patch("github_metrics.app.metrics_tracker") as mock_tracker,
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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
            patch("github_metrics.app.metrics_tracker") as mock_tracker,
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
            patch("github_metrics.app.verify_signature") as mock_verify_sig,
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
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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
            patch("github_metrics.app.metrics_tracker") as mock_tracker,
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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


class TestDashboardEndpoint:
    """Tests for /dashboard endpoint."""

    def test_dashboard_returns_html(self) -> None:
        """Test dashboard endpoint returns HTML page."""
        with patch("github_metrics.app.dashboard_controller") as mock_controller:
            mock_controller.get_dashboard_page = Mock(return_value="<html>Dashboard</html>")

            client = TestClient(app)
            response = client.get("/dashboard")

            assert response.status_code == status.HTTP_200_OK
            assert "html" in response.headers["content-type"].lower()

    def test_dashboard_error_when_controller_not_initialized(self) -> None:
        """Test dashboard returns error when controller not initialized."""
        with patch("github_metrics.app.dashboard_controller", None):
            client = TestClient(app)
            response = client.get("/dashboard")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


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

        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager", None):
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

        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=mock_row)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["delivery_id"] == "test-123"
            assert data["payload"] == {"test": "data"}

    def test_get_webhook_event_by_id_not_found(self) -> None:
        """Test webhook event retrieval for non-existent ID."""
        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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
            patch("github_metrics.app.get_config") as mock_config,
            patch("github_metrics.app.get_database_manager") as mock_db_manager_factory,
            patch("github_metrics.app.get_logger") as mock_logger_factory,
            patch("github_metrics.app.httpx.AsyncClient") as mock_http_client_class,
            patch("github_metrics.app.get_github_allowlist") as mock_get_github,
            patch("github_metrics.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            # Setup mocks
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = True
            config_mock.webhook.verify_cloudflare_ips = False
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
            patch("github_metrics.app.get_config") as mock_config,
            patch("github_metrics.app.get_database_manager") as mock_db_manager_factory,
            patch("github_metrics.app.get_logger") as mock_logger_factory,
            patch("github_metrics.app.httpx.AsyncClient") as mock_http_client_class,
            patch("github_metrics.app.get_github_allowlist") as mock_get_github,
            patch("github_metrics.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            # Setup mocks
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = False
            config_mock.webhook.verify_cloudflare_ips = True
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
            patch("github_metrics.app.get_config") as mock_config,
            patch("github_metrics.app.httpx.AsyncClient") as mock_http_client_class,
            patch("github_metrics.app.get_github_allowlist") as mock_get_github,
        ):
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = True
            config_mock.webhook.verify_cloudflare_ips = False
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
            patch("github_metrics.app.get_config") as mock_config,
            patch("github_metrics.app.httpx.AsyncClient") as mock_http_client_class,
            patch("github_metrics.app.get_github_allowlist"),
            patch("github_metrics.app.get_cloudflare_allowlist") as mock_get_cloudflare,
        ):
            config_mock = Mock()
            config_mock.webhook.verify_github_ips = False
            config_mock.webhook.verify_cloudflare_ips = True
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
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_webhook_events_with_datetime_params(self) -> None:
        """Test webhook events with valid datetime parameters."""
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_webhook_event_by_id_database_unavailable(self) -> None:
        """Test webhook event by ID when database unavailable."""
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/webhooks/test-123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestRepositoryStatisticsErrors:
    """Tests for /api/metrics/repositories error handling."""

    def test_get_repository_statistics_database_error(self) -> None:
        """Test repository statistics handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/repositories")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_repository_statistics_with_datetime_params(self) -> None:
        """Test repository statistics with datetime parameters."""
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/repositories")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestMetricsSummaryErrors:
    """Tests for /api/metrics/summary error handling."""

    def test_get_metrics_summary_database_error(self) -> None:
        """Test metrics summary handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager", None):
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
            patch("github_metrics.app.metrics_tracker") as mock_tracker,
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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
            patch("github_metrics.app.metrics_tracker") as mock_tracker,
            patch("github_metrics.app.allowed_ips", ()),
            patch("github_metrics.app.get_config") as mock_config,
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
        # Mock count queries
        mock_creators_count = 5
        mock_reviewers_count = 3
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
        mock_reviewers_rows = [
            {
                "user": "bob",
                "total_reviews": 15,
                "prs_reviewed": 12,
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

        with patch("github_metrics.app.db_manager") as mock_db:
            # Mock fetchval for count queries (4 calls)
            mock_db.fetchval = AsyncMock(
                side_effect=[mock_creators_count, mock_reviewers_count, mock_approvers_count, mock_lgtm_count],
            )
            # Mock fetch for data queries (4 calls)
            mock_db.fetch = AsyncMock(
                side_effect=[mock_creators_rows, mock_reviewers_rows, mock_approvers_rows, mock_lgtm_rows],
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

    def test_get_contributors_with_filters(self) -> None:
        """Test contributors with user and repository filters."""
        with patch("github_metrics.app.db_manager") as mock_db:
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
        mock_reviewers_count = 80
        mock_approvers_count = 60
        mock_lgtm_count = 40

        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(
                side_effect=[mock_creators_count, mock_reviewers_count, mock_approvers_count, mock_lgtm_count],
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
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_contributors_database_error(self) -> None:
        """Test contributors handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/contributors")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_contributors_cancelled_error(self) -> None:
        """Test contributors handles asyncio.CancelledError."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=asyncio.CancelledError())

            client = TestClient(app)

            # TestClient wraps asyncio.CancelledError into concurrent.futures.CancelledError
            with pytest.raises(CancelledError):
                client.get("/api/metrics/contributors")


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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/user-prs")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_user_prs_database_error(self) -> None:
        """Test user PRs handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchrow = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/user-prs")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


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

        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager"):
            client = TestClient(app)
            response = client.get("/api/metrics/trends", params={"bucket": "invalid"})

            # FastAPI validation should reject this
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_trends_database_unavailable(self) -> None:
        """Test trends when database unavailable."""
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/trends")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_trends_database_error(self) -> None:
        """Test trends handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/trends")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_trends_cancelled_error(self) -> None:
        """Test trends handles asyncio.CancelledError."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=asyncio.CancelledError())

            client = TestClient(app)

            # TestClient wraps asyncio.CancelledError into concurrent.futures.CancelledError
            with pytest.raises(CancelledError):
                client.get("/api/metrics/trends")


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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetchval = AsyncMock(return_value=0)

            client = TestClient(app)
            response = client.get("/api/metrics/webhooks", params={"start_time": "invalid"})

            # Should get the HTTPException from parse_datetime_string
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_repositories_reraises_http_exception(self) -> None:
        """Test repositories re-raises HTTPException from parse_datetime_string."""
        with patch("github_metrics.app.db_manager"):
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

        with patch("github_metrics.app.db_manager") as mock_db:
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

        with patch("github_metrics.app.db_manager") as mock_db:
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
