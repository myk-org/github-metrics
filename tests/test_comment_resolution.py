"""Tests for comment resolution time API endpoint.

Tests the /api/metrics/comment-resolution-time endpoint including:
- Success cases with mock data
- Response structure validation
- Filter testing (time range, repositories)
- Edge cases (empty results, NULL values)
- Error handling (database errors, invalid datetime)
"""

import asyncio
import concurrent.futures
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app


class TestCommentResolutionTimeEndpoint:
    """Tests for /api/metrics/comment-resolution-time endpoint."""

    def test_get_comment_resolution_time_success(self) -> None:
        """Test successful comment resolution time retrieval with mock data."""
        # Mock resolution query rows
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 123,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC),
                "resolution_hours": 2.5,
            },
            {
                "repository": "org/repo1",
                "pr_number": 456,
                "can_be_merged_at": datetime(2024, 1, 16, 9, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 16, 10, 30, 0, tzinfo=UTC),
                "resolution_hours": 1.5,
            },
            {
                "repository": "org/repo2",
                "pr_number": 789,
                "can_be_merged_at": datetime(2024, 1, 17, 8, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 17, 14, 0, 0, tzinfo=UTC),
                "resolution_hours": 6.0,
            },
        ]

        # Mock pending resolution query rows
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 999,
                "can_be_merged_at": datetime(2024, 1, 18, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": 5.2,
            },
            {
                "repository": "org/repo2",
                "pr_number": 888,
                "can_be_merged_at": datetime(2024, 1, 18, 8, 0, 0, tzinfo=UTC),
                "hours_waiting": 8.5,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            # Mock fetch for both queries (asyncio.gather)
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            assert "summary" in data
            assert "by_repository" in data
            assert "prs_pending_resolution" in data

            # Verify summary calculations
            summary = data["summary"]
            assert summary["total_prs_analyzed"] == 3
            # avg: (2.5 + 1.5 + 6.0) / 3 = 3.33
            assert summary["avg_resolution_time_hours"] == 3.3
            # median of [1.5, 2.5, 6.0] = 2.5
            assert summary["median_resolution_time_hours"] == 2.5
            # max: 6.0
            assert summary["max_resolution_time_hours"] == 6.0

            # Verify by_repository
            assert len(data["by_repository"]) == 2
            repo1 = next((r for r in data["by_repository"] if r["repository"] == "org/repo1"), None)
            assert repo1 is not None
            assert repo1["total_prs"] == 2
            # avg: (2.5 + 1.5) / 2 = 2.0
            assert repo1["avg_resolution_time_hours"] == 2.0

            repo2 = next((r for r in data["by_repository"] if r["repository"] == "org/repo2"), None)
            assert repo2 is not None
            assert repo2["total_prs"] == 1
            assert repo2["avg_resolution_time_hours"] == 6.0

            # Verify pending PRs
            assert len(data["prs_pending_resolution"]) == 2
            pending1 = data["prs_pending_resolution"][0]
            assert pending1["repository"] == "org/repo1"
            assert pending1["pr_number"] == 999
            assert pending1["hours_waiting"] == 5.2
            assert "can_be_merged_at" in pending1

    def test_get_comment_resolution_time_with_filters(self) -> None:
        """Test comment resolution time with time range and repository filters."""
        mock_resolution_rows = [
            {
                "repository": "org/specific-repo",
                "pr_number": 100,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolution_hours": 2.0,
            },
        ]
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                    "repositories": ["org/specific-repo"],
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["summary"]["total_prs_analyzed"] == 1
            assert len(data["by_repository"]) == 1
            assert data["by_repository"][0]["repository"] == "org/specific-repo"

    def test_get_comment_resolution_time_empty_results(self) -> None:
        """Test comment resolution time with no matching data."""
        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            # Empty results for both queries
            mock_db.fetch = AsyncMock(side_effect=[[], []])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify empty results
            assert data["summary"]["avg_resolution_time_hours"] == 0.0
            assert data["summary"]["median_resolution_time_hours"] == 0.0
            assert data["summary"]["max_resolution_time_hours"] == 0.0
            assert data["summary"]["total_prs_analyzed"] == 0
            assert len(data["by_repository"]) == 0
            assert len(data["prs_pending_resolution"]) == 0

    def test_get_comment_resolution_time_handles_null_values(self) -> None:
        """Test comment resolution time handles NULL values gracefully."""
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 123,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolution_hours": 2.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 456,
                "can_be_merged_at": datetime(2024, 1, 16, 9, 0, 0, tzinfo=UTC),
                "last_resolved_at": None,  # NULL resolved time
                "resolution_hours": None,  # NULL hours
            },
            {
                "repository": "org/repo2",
                "pr_number": 789,
                "can_be_merged_at": datetime(2024, 1, 17, 8, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 17, 8, 0, 0, tzinfo=UTC),
                "resolution_hours": 0.0,  # Zero hours (same time)
            },
        ]
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Only row with resolution_hours > 0 should be counted (2.0 hours)
            assert data["summary"]["total_prs_analyzed"] == 1
            assert data["summary"]["avg_resolution_time_hours"] == 2.0
            assert data["summary"]["median_resolution_time_hours"] == 2.0
            assert data["summary"]["max_resolution_time_hours"] == 2.0

    def test_get_comment_resolution_time_median_calculation_odd(self) -> None:
        """Test median calculation with odd number of values."""
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 1,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 2,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC),
                "resolution_hours": 3.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 3,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC),
                "resolution_hours": 5.0,
            },
        ]
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Median of [1.0, 3.0, 5.0] = 3.0
            assert data["summary"]["median_resolution_time_hours"] == 3.0

    def test_get_comment_resolution_time_median_calculation_even(self) -> None:
        """Test median calculation with even number of values."""
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 1,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 2,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolution_hours": 2.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 3,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC),
                "resolution_hours": 3.0,
            },
            {
                "repository": "org/repo1",
                "pr_number": 4,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 14, 0, 0, tzinfo=UTC),
                "resolution_hours": 4.0,
            },
        ]
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Median of [1.0, 2.0, 3.0, 4.0] = (2.0 + 3.0) / 2 = 2.5
            assert data["summary"]["median_resolution_time_hours"] == 2.5

    def test_get_comment_resolution_time_prs_without_threads_excluded(self) -> None:
        """Test that PRs with can-be-merged but no thread resolution are excluded."""
        # This is enforced by the SQL query (INNER JOIN on last_thread_resolved)
        # PRs without pull_request_review_thread events won't appear in results
        mock_resolution_rows: list[dict[str, Any]] = []  # No PRs have matching thread resolution
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 100,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": 10.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # No resolution metrics (PRs without thread events excluded)
            assert data["summary"]["total_prs_analyzed"] == 0

            # But pending PRs may exist (have can-be-merged but unresolved threads)
            assert len(data["prs_pending_resolution"]) == 1
            assert data["prs_pending_resolution"][0]["pr_number"] == 100

    def test_get_comment_resolution_time_pending_prs_with_unresolved_threads(self) -> None:
        """Test PRs pending resolution have can-be-merged but unresolved threads."""
        mock_resolution_rows: list[dict[str, Any]] = []
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 200,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": 24.5,
            },
            {
                "repository": "org/repo2",
                "pr_number": 300,
                "can_be_merged_at": datetime(2024, 1, 16, 8, 0, 0, tzinfo=UTC),
                "hours_waiting": 48.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pending PRs
            assert len(data["prs_pending_resolution"]) == 2
            assert data["prs_pending_resolution"][0]["pr_number"] == 200
            assert data["prs_pending_resolution"][0]["hours_waiting"] == 24.5
            assert data["prs_pending_resolution"][1]["pr_number"] == 300
            assert data["prs_pending_resolution"][1]["hours_waiting"] == 48.0

    def test_get_comment_resolution_time_pending_null_can_be_merged_at(self) -> None:
        """Test pending PRs handles NULL can_be_merged_at gracefully."""
        mock_resolution_rows: list[dict[str, Any]] = []
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 400,
                "can_be_merged_at": None,  # NULL timestamp
                "hours_waiting": 10.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pending PR with NULL can_be_merged_at returns None
            assert len(data["prs_pending_resolution"]) == 1
            assert data["prs_pending_resolution"][0]["can_be_merged_at"] is None
            assert data["prs_pending_resolution"][0]["hours_waiting"] == 10.0

    def test_get_comment_resolution_time_pending_null_hours_waiting(self) -> None:
        """Test pending PRs handles NULL hours_waiting gracefully."""
        mock_resolution_rows: list[dict[str, Any]] = []
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 500,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": None,  # NULL hours
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pending PR with NULL hours_waiting returns 0.0
            assert len(data["prs_pending_resolution"]) == 1
            assert data["prs_pending_resolution"][0]["hours_waiting"] == 0.0

    def test_get_comment_resolution_time_invalid_datetime_format(self) -> None:
        """Test comment resolution time with invalid datetime format."""
        with patch("backend.routes.api.comment_resolution.db_manager"):
            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"start_time": "invalid-date"},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid datetime format" in response.json()["detail"]

    def test_get_comment_resolution_time_database_unavailable(self) -> None:
        """Test comment resolution time when database is unavailable."""
        with patch("backend.routes.api.comment_resolution.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database not available" in response.json()["detail"]

    def test_get_comment_resolution_time_database_error(self) -> None:
        """Test comment resolution time handles database errors."""
        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=asyncpg.PostgresError("Database connection failed"))

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to fetch comment resolution time metrics" in response.json()["detail"]

    def test_get_comment_resolution_time_cancelled_error(self) -> None:
        """Test comment resolution time handles asyncio.CancelledError."""
        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=asyncio.CancelledError)

            client = TestClient(app)
            # CancelledError is re-raised and handled by FastAPI/ASGI server
            # TestClient may wrap it in concurrent.futures.CancelledError (detect cancellation, not specific type)
            with pytest.raises((asyncio.CancelledError, concurrent.futures.CancelledError)):
                client.get("/api/metrics/comment-resolution-time")

    def test_get_comment_resolution_time_http_exception_reraise(self) -> None:
        """Test comment resolution time re-raises HTTPException from parse_datetime_string."""
        with patch("backend.routes.api.comment_resolution.db_manager"):
            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"end_time": "invalid-format"},
            )

            # Should get the HTTPException from parse_datetime_string
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid datetime format" in response.json()["detail"]

    def test_get_comment_resolution_time_response_structure(self) -> None:
        """Test comment resolution time response has correct structure."""
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 123,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolution_hours": 2.0,
            },
        ]
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 999,
                "can_be_merged_at": datetime(2024, 1, 18, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": 5.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify top-level structure
            assert set(data.keys()) == {"summary", "by_repository", "prs_pending_resolution"}

            # Verify summary structure
            assert set(data["summary"].keys()) == {
                "avg_resolution_time_hours",
                "median_resolution_time_hours",
                "max_resolution_time_hours",
                "total_prs_analyzed",
            }

            # Verify by_repository structure
            assert isinstance(data["by_repository"], list)
            for repo in data["by_repository"]:
                assert set(repo.keys()) == {"repository", "avg_resolution_time_hours", "total_prs"}

            # Verify prs_pending_resolution structure
            assert isinstance(data["prs_pending_resolution"], list)
            for pending in data["prs_pending_resolution"]:
                assert set(pending.keys()) == {"repository", "pr_number", "can_be_merged_at", "hours_waiting"}

    def test_get_comment_resolution_time_by_repository_sorting(self) -> None:
        """Test by_repository is sorted by PR count (descending)."""
        mock_resolution_rows = [
            {
                "repository": "org/repo1",
                "pr_number": 1,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
            {
                "repository": "org/repo2",
                "pr_number": 2,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
            {
                "repository": "org/repo2",
                "pr_number": 3,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
            {
                "repository": "org/repo2",
                "pr_number": 4,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "last_resolved_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "resolution_hours": 1.0,
            },
        ]
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify repos sorted by count (repo2: 3 PRs, repo1: 1 PR)
            assert len(data["by_repository"]) == 2
            assert data["by_repository"][0]["repository"] == "org/repo2"
            assert data["by_repository"][0]["total_prs"] == 3
            assert data["by_repository"][1]["repository"] == "org/repo1"
            assert data["by_repository"][1]["total_prs"] == 1

    def test_get_comment_resolution_time_pending_limit_parameter(self) -> None:
        """Test pending_limit parameter controls number of pending PRs returned."""
        mock_resolution_rows: list[dict[str, Any]] = []
        # Create 100 pending PRs
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": i,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": float(i),
            }
            for i in range(1, 101)
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows[:10]])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"pending_limit": 10},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify only 10 pending PRs returned (as specified by pending_limit)
            assert len(data["prs_pending_resolution"]) == 10

            # Verify the PRs are the first 10 (ordered by hours_waiting DESC in query)
            for i, pending_pr in enumerate(data["prs_pending_resolution"], start=1):
                assert pending_pr["pr_number"] == i

    def test_get_comment_resolution_time_pending_limit_no_upper_bound(self) -> None:
        """Test pending_limit has no upper bound (CLAUDE.md requirement)."""
        mock_resolution_rows: list[dict[str, Any]] = []
        # Create 1000 pending PRs to test large limit
        mock_pending_rows = [
            {
                "repository": "org/repo1",
                "pr_number": i,
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "hours_waiting": float(i),
            }
            for i in range(1, 1001)
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            # Request all 1000 pending PRs
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"pending_limit": 1000},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify all 1000 pending PRs returned (no artificial upper limit)
            assert len(data["prs_pending_resolution"]) == 1000

    def test_get_comment_resolution_time_no_webhook_events_configured(self) -> None:
        """Test no webhook events scenario (no pull_request_review_thread or check_run events).

        This tests the edge case where repositories don't have:
        - pull_request_review_thread webhook events configured
        - can-be-merged check runs

        The endpoint should return a valid response with all zeros/empty lists,
        not errors or exceptions.
        """
        # Both queries return empty results (no webhook events exist)
        mock_resolution_rows: list[dict[str, Any]] = []
        mock_pending_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            # Simulate both SQL queries returning empty results
            mock_db.fetch = AsyncMock(side_effect=[mock_resolution_rows, mock_pending_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            # Should return 200 OK with valid response structure
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure is complete
            assert "summary" in data
            assert "by_repository" in data
            assert "prs_pending_resolution" in data

            # Verify summary has zeros (not errors or None)
            assert data["summary"]["avg_resolution_time_hours"] == 0.0
            assert data["summary"]["median_resolution_time_hours"] == 0.0
            assert data["summary"]["max_resolution_time_hours"] == 0.0
            assert data["summary"]["total_prs_analyzed"] == 0

            # Verify empty lists (not None or missing)
            assert isinstance(data["by_repository"], list)
            assert len(data["by_repository"]) == 0

            assert isinstance(data["prs_pending_resolution"], list)
            assert len(data["prs_pending_resolution"]) == 0

            # Verify database was queried correctly (both queries executed)
            assert mock_db.fetch.call_count == 2
