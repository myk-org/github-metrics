"""Tests for MetricsTracker class.

Tests webhook event tracking including:
- Event storage with full payload
- Processing metrics tracking
- Error handling and logging
"""

import json
import logging
from datetime import datetime
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest

from backend.metrics_tracker import MetricsTracker


class TestMetricsTracker:
    """Tests for MetricsTracker class."""

    @pytest.fixture
    def mock_logger(self) -> Mock:
        """Create mock logger."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def tracker(self, mock_db_manager: Mock, mock_logger: Mock) -> MetricsTracker:
        """Create MetricsTracker instance with mocked dependencies."""
        return MetricsTracker(db_manager=mock_db_manager, logger=mock_logger)

    async def test_track_webhook_event_success(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test successful webhook event tracking."""
        payload = {"test": "data", "number": 42}

        await tracker.track_webhook_event(
            delivery_id="test-delivery-123",
            repository="testorg/testrepo",
            event_type="pull_request",
            action="opened",
            sender="testuser",
            payload=payload,
            processing_time_ms=150,
            status="success",
            pr_number=42,
        )

        # Verify database execute was called
        mock_db_manager.execute.assert_called_once()

        # Get the call arguments
        call_args = mock_db_manager.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        # Verify query structure
        assert "INSERT INTO webhooks" in query
        assert "delivery_id" in query
        assert "repository" in query

        # Verify parameters (skip UUID at index 0)
        # Parameter order: id (UUID), delivery_id, repository, event_type, action, pr_number,
        # sender, payload, processing_time_ms, status, error_message, api_calls_count,
        # token_spend, token_remaining, metrics_available
        assert params[1] == "test-delivery-123"  # delivery_id
        assert params[2] == "testorg/testrepo"  # repository
        assert params[3] == "pull_request"  # event_type
        assert params[4] == "opened"  # action
        assert params[5] == 42  # pr_number
        assert params[6] == "testuser"  # sender
        assert json.loads(params[7]) == payload  # payload
        assert params[8] == 150  # processing_time_ms
        assert params[9] == "success"  # status

        # Verify UUID parameter
        assert isinstance(params[0], UUID)

        # Verify logging
        mock_logger.info.assert_called_once()
        assert "successfully" in mock_logger.info.call_args[0][0]

    async def test_track_webhook_event_with_optional_fields(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
    ) -> None:
        """Test webhook tracking with all optional fields."""
        payload = {"test": "data"}

        await tracker.track_webhook_event(
            delivery_id="test-delivery-456",
            repository="testorg/testrepo",
            event_type="issue_comment",
            action="created",
            sender="testuser",
            payload=payload,
            processing_time_ms=250,
            status="error",
            pr_number=10,
            error_message="Test error",
            api_calls_count=5,
            token_spend=5,
            token_remaining=4995,
            metrics_available=True,
        )

        # Verify all parameters passed to database
        call_args = mock_db_manager.execute.call_args[0]
        params = call_args[1:]

        assert params[10] == "Test error"  # error_message
        assert params[11] == 5  # api_calls_count
        assert params[12] == 5  # token_spend
        assert params[13] == 4995  # token_remaining
        assert params[14] is True  # metrics_available

    async def test_track_webhook_event_without_pr_number(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
    ) -> None:
        """Test webhook tracking without PR number (e.g., push event)."""
        payload = {"ref": "refs/heads/main"}

        await tracker.track_webhook_event(
            delivery_id="test-delivery-789",
            repository="testorg/testrepo",
            event_type="push",
            action="",
            sender="testuser",
            payload=payload,
            processing_time_ms=100,
            status="success",
            pr_number=None,
        )

        # Verify pr_number is None
        call_args = mock_db_manager.execute.call_args[0]
        params = call_args[1:]
        assert params[5] is None  # pr_number

    async def test_track_webhook_event_with_complex_payload(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
    ) -> None:
        """Test webhook tracking with complex nested payload."""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "labels": [{"name": "bug"}, {"name": "urgent"}],
            },
            "repository": {"full_name": "testorg/testrepo"},
        }

        await tracker.track_webhook_event(
            delivery_id="test-delivery-complex",
            repository="testorg/testrepo",
            event_type="pull_request",
            action="opened",
            sender="testuser",
            payload=payload,
            processing_time_ms=200,
            status="success",
        )

        # Verify payload was serialized correctly
        call_args = mock_db_manager.execute.call_args[0]
        params = call_args[1:]
        payload_json = params[7]
        deserialized = json.loads(payload_json)
        assert deserialized == payload

    async def test_track_webhook_event_database_error(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
        mock_logger: Mock,
    ) -> None:
        """Test error handling when database insert fails."""
        mock_db_manager.execute.side_effect = Exception("Database error")

        payload = {"test": "data"}

        with pytest.raises(Exception, match="Database error"):
            await tracker.track_webhook_event(
                delivery_id="test-delivery-error",
                repository="testorg/testrepo",
                event_type="pull_request",
                action="opened",
                sender="testuser",
                payload=payload,
                processing_time_ms=150,
                status="success",
            )

        # Verify error was logged
        mock_logger.exception.assert_called_once()
        assert "Failed to track" in mock_logger.exception.call_args[0][0]

    async def test_track_webhook_event_default_values(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
    ) -> None:
        """Test webhook tracking uses correct default values."""
        payload = {"test": "data"}

        await tracker.track_webhook_event(
            delivery_id="test-delivery-defaults",
            repository="testorg/testrepo",
            event_type="pull_request",
            action="opened",
            sender="testuser",
            payload=payload,
            processing_time_ms=150,
            status="success",
        )

        # Verify default values in parameters
        call_args = mock_db_manager.execute.call_args[0]
        params = call_args[1:]

        assert params[10] is None  # error_message default
        assert params[11] == 0  # api_calls_count default
        assert params[12] == 0  # token_spend default
        assert params[13] == 0  # token_remaining default
        assert params[14] is True  # metrics_available default

    async def test_track_webhook_event_json_serialization_with_datetime(
        self,
        tracker: MetricsTracker,
        mock_db_manager: Mock,
    ) -> None:
        """Test JSON serialization handles non-serializable types (datetime)."""
        # Intentionally using naive datetime to test serialization fallback
        payload: dict[str, Any] = {"timestamp": datetime(2024, 1, 15, 12, 0, 0), "data": "test"}

        await tracker.track_webhook_event(
            delivery_id="test-delivery-datetime",
            repository="testorg/testrepo",
            event_type="pull_request",
            action="opened",
            sender="testuser",
            payload=payload,
            processing_time_ms=150,
            status="success",
        )

        # Verify datetime was converted to string
        call_args = mock_db_manager.execute.call_args[0]
        params = call_args[1:]
        payload_json = params[7]

        # Should not raise exception during JSON parsing
        deserialized = json.loads(payload_json)
        assert "timestamp" in deserialized
        assert deserialized["data"] == "test"
