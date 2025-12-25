"""Tests for comment resolution time API endpoint.

Tests the /api/metrics/comment-resolution-time endpoint including:
- Success cases with mock data
- Response structure validation
- Filter testing (time range, repositories)
- Edge cases (empty results, NULL values)
- Error handling (database errors, invalid datetime)
- Pagination
- Per-thread granular metrics
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
        """Test successful comment resolution time retrieval with mock thread data."""
        # Mock threads query rows
        mock_threads_rows = [
            {
                "thread_node_id": "PRRT_abc123",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": "src/main.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "time_to_first_response_hours": 0.5,
                "resolved_at": datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": 2.5,
                "comment_count": 4,
                "participants": ["user1", "user2", "user3"],
                "can_be_merged_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "time_from_can_be_merged_hours": 1.5,
                "total_count": 3,
            },
            {
                "thread_node_id": "PRRT_def456",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": "src/utils.py",
                "first_comment_at": datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC),
                "second_comment_at": datetime(2024, 1, 15, 9, 15, 0, tzinfo=UTC),
                "time_to_first_response_hours": 0.25,
                "resolved_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "resolver": "user2",
                "resolution_time_hours": 1.5,
                "comment_count": 3,
                "participants": ["user2", "user3"],
                "can_be_merged_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "time_from_can_be_merged_hours": 0.5,
                "total_count": 3,
            },
            {
                "thread_node_id": "PRRT_ghi789",
                "repository": "org/repo2",
                "pr_number": 456,
                "file_path": "tests/test_api.py",
                "first_comment_at": datetime(2024, 1, 16, 8, 0, 0, tzinfo=UTC),
                "second_comment_at": None,
                "time_to_first_response_hours": None,
                "resolved_at": None,
                "resolver": None,
                "resolution_time_hours": None,
                "comment_count": 1,
                "participants": ["user1"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 3,
            },
        ]

        # Mock repository stats query rows
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 2,
                "resolved_threads": 2,
                "avg_resolution_time_hours": 2.0,
            },
            {
                "repository": "org/repo2",
                "total_threads": 1,
                "resolved_threads": 0,
                "avg_resolution_time_hours": 0.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            # Mock fetch for both queries (asyncio.gather)
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            assert "summary" in data
            assert "by_repository" in data
            assert "threads" in data
            assert "pagination" in data

            # Verify summary calculations
            summary = data["summary"]
            assert summary["total_threads_analyzed"] == 3
            # avg resolution: (2.5 + 1.5) / 2 = 2.0 (only resolved threads)
            assert summary["avg_resolution_time_hours"] == 2.0
            # median of [1.5, 2.5] = 2.0
            assert summary["median_resolution_time_hours"] == 2.0
            # avg response time: (0.5 + 0.25) / 2 = 0.375 -> 0.4
            assert summary["avg_time_to_first_response_hours"] == 0.4
            # avg comments: (4 + 3 + 1) / 3 = 2.67 -> 2.7
            assert summary["avg_comments_per_thread"] == 2.7
            # resolution rate: 2 / 3 * 100 = 66.7
            assert summary["resolution_rate"] == 66.7

            # Verify by_repository
            assert len(data["by_repository"]) == 2
            repo1 = next((r for r in data["by_repository"] if r["repository"] == "org/repo1"), None)
            assert repo1 is not None
            assert repo1["total_threads"] == 2
            assert repo1["resolved_threads"] == 2
            assert repo1["avg_resolution_time_hours"] == 2.0

            # Verify threads list
            assert len(data["threads"]) == 3
            thread1 = data["threads"][0]
            assert thread1["thread_node_id"] == "PRRT_abc123"
            assert thread1["repository"] == "org/repo1"
            assert thread1["pr_number"] == 123
            assert thread1["resolution_time_hours"] == 2.5
            assert thread1["comment_count"] == 4
            assert thread1["participants"] == ["user1", "user2", "user3"]

            # Verify pagination
            pagination = data["pagination"]
            assert pagination["total"] == 3
            assert pagination["page"] == 1
            assert pagination["page_size"] == 25
            assert pagination["total_pages"] == 1
            assert pagination["has_next"] is False
            assert pagination["has_prev"] is False

    def test_get_comment_resolution_time_with_filters(self) -> None:
        """Test comment resolution time with time range and repository filters."""
        mock_threads_rows = [
            {
                "thread_node_id": "PRRT_xyz",
                "repository": "org/specific-repo",
                "pr_number": 100,
                "file_path": "README.md",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "time_to_first_response_hours": 0.5,
                "resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": 2.0,
                "comment_count": 2,
                "participants": ["user1", "user2"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 1,
            },
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/specific-repo",
                "total_threads": 1,
                "resolved_threads": 1,
                "avg_resolution_time_hours": 2.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

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
            assert data["summary"]["total_threads_analyzed"] == 1
            assert len(data["by_repository"]) == 1
            assert data["by_repository"][0]["repository"] == "org/specific-repo"

    def test_get_comment_resolution_time_pagination(self) -> None:
        """Test comment resolution time pagination."""
        # Create 50 threads, but only return first 25
        mock_threads_rows = [
            {
                "thread_node_id": f"PRRT_{i}",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": f"file{i}.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": None,
                "time_to_first_response_hours": None,
                "resolved_at": None,
                "resolver": None,
                "resolution_time_hours": None,
                "comment_count": 1,
                "participants": ["user1"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 50,
            }
            for i in range(25)
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 50,
                "resolved_threads": 0,
                "avg_resolution_time_hours": 0.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"page": 1, "page_size": 25},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pagination metadata
            pagination = data["pagination"]
            assert pagination["total"] == 50
            assert pagination["page"] == 1
            assert pagination["page_size"] == 25
            assert pagination["total_pages"] == 2
            assert pagination["has_next"] is True
            assert pagination["has_prev"] is False

            # Verify only 25 threads returned
            assert len(data["threads"]) == 25

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
            assert data["summary"]["avg_time_to_first_response_hours"] == 0.0
            assert data["summary"]["avg_comments_per_thread"] == 0.0
            assert data["summary"]["total_threads_analyzed"] == 0
            assert data["summary"]["resolution_rate"] == 0.0
            assert len(data["by_repository"]) == 0
            assert len(data["threads"]) == 0

    def test_get_comment_resolution_time_handles_null_values(self) -> None:
        """Test comment resolution time handles NULL values gracefully."""
        mock_threads_rows = [
            {
                "thread_node_id": "PRRT_1",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": "file1.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "time_to_first_response_hours": 0.5,
                "resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": 2.0,
                "comment_count": 3,
                "participants": ["user1", "user2"],
                "can_be_merged_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "time_from_can_be_merged_hours": 1.0,
                "total_count": 2,
            },
            {
                "thread_node_id": "PRRT_2",
                "repository": "org/repo1",
                "pr_number": 456,
                "file_path": None,  # NULL file path
                "first_comment_at": datetime(2024, 1, 16, 9, 0, 0, tzinfo=UTC),
                "second_comment_at": None,  # Only 1 comment
                "time_to_first_response_hours": None,
                "resolved_at": None,  # Unresolved
                "resolver": None,
                "resolution_time_hours": None,
                "comment_count": 1,
                "participants": [],  # Empty participants
                "can_be_merged_at": None,  # No can-be-merged
                "time_from_can_be_merged_hours": None,
                "total_count": 2,
            },
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 2,
                "resolved_threads": 1,
                "avg_resolution_time_hours": 2.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Only 1 resolved thread
            assert data["summary"]["total_threads_analyzed"] == 2
            assert data["summary"]["avg_resolution_time_hours"] == 2.0
            assert data["summary"]["resolution_rate"] == 50.0

            # Verify NULL values handled correctly
            thread2 = data["threads"][1]
            assert thread2["file_path"] is None
            assert thread2["time_to_first_response_hours"] is None
            assert thread2["resolved_at"] is None
            assert thread2["resolution_time_hours"] is None
            assert thread2["participants"] == []

    def test_get_comment_resolution_time_median_calculation_odd(self) -> None:
        """Test median calculation with odd number of values."""
        mock_threads_rows = [
            {
                "thread_node_id": f"PRRT_{i}",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": f"file{i}.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": None,
                "time_to_first_response_hours": None,
                "resolved_at": datetime(2024, 1, 15, 10 + i, 0, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": float(i),
                "comment_count": 2,
                "participants": ["user1"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 3,
            }
            for i in [1, 3, 5]
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 3,
                "resolved_threads": 3,
                "avg_resolution_time_hours": 3.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Median of [1.0, 3.0, 5.0] = 3.0
            assert data["summary"]["median_resolution_time_hours"] == 3.0

    def test_get_comment_resolution_time_median_calculation_even(self) -> None:
        """Test median calculation with even number of values."""
        mock_threads_rows = [
            {
                "thread_node_id": f"PRRT_{i}",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": f"file{i}.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": None,
                "time_to_first_response_hours": None,
                "resolved_at": datetime(2024, 1, 15, 10 + i, 0, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": float(i),
                "comment_count": 2,
                "participants": ["user1"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 4,
            }
            for i in [1, 2, 3, 4]
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 4,
                "resolved_threads": 4,
                "avg_resolution_time_hours": 2.5,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Median of [1.0, 2.0, 3.0, 4.0] = (2.0 + 3.0) / 2 = 2.5
            assert data["summary"]["median_resolution_time_hours"] == 2.5

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
        mock_threads_rows = [
            {
                "thread_node_id": "PRRT_abc",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": "file.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                "time_to_first_response_hours": 0.5,
                "resolved_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "resolver": "user1",
                "resolution_time_hours": 2.0,
                "comment_count": 3,
                "participants": ["user1", "user2"],
                "can_be_merged_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "time_from_can_be_merged_hours": 1.0,
                "total_count": 1,
            },
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 1,
                "resolved_threads": 1,
                "avg_resolution_time_hours": 2.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify top-level structure
            assert set(data.keys()) == {"summary", "by_repository", "threads", "pagination"}

            # Verify summary structure
            assert set(data["summary"].keys()) == {
                "avg_resolution_time_hours",
                "median_resolution_time_hours",
                "avg_time_to_first_response_hours",
                "avg_comments_per_thread",
                "total_threads_analyzed",
                "resolution_rate",
            }

            # Verify by_repository structure
            assert isinstance(data["by_repository"], list)
            for repo in data["by_repository"]:
                assert set(repo.keys()) == {
                    "repository",
                    "avg_resolution_time_hours",
                    "total_threads",
                    "resolved_threads",
                }

            # Verify threads structure
            assert isinstance(data["threads"], list)
            for thread in data["threads"]:
                assert set(thread.keys()) == {
                    "thread_node_id",
                    "repository",
                    "pr_number",
                    "first_comment_at",
                    "resolved_at",
                    "resolution_time_hours",
                    "time_to_first_response_hours",
                    "comment_count",
                    "resolver",
                    "participants",
                    "file_path",
                    "can_be_merged_at",
                    "time_from_can_be_merged_hours",
                }

            # Verify pagination structure
            assert set(data["pagination"].keys()) == {
                "total",
                "page",
                "page_size",
                "total_pages",
                "has_next",
                "has_prev",
            }

    def test_get_comment_resolution_time_no_webhook_events_configured(self) -> None:
        """Test no webhook events scenario (no pull_request_review_thread events).

        This tests the edge case where repositories don't have:
        - pull_request_review_thread webhook events configured

        The endpoint should return a valid response with all zeros/empty lists,
        not errors or exceptions.
        """
        # Both queries return empty results (no webhook events exist)
        mock_threads_rows: list[dict[str, Any]] = []
        mock_repo_stats_rows: list[dict[str, Any]] = []

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            # Simulate both SQL queries returning empty results
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get("/api/metrics/comment-resolution-time")

            # Should return 200 OK with valid response structure
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure is complete
            assert "summary" in data
            assert "by_repository" in data
            assert "threads" in data
            assert "pagination" in data

            # Verify summary has zeros (not errors or None)
            assert data["summary"]["avg_resolution_time_hours"] == 0.0
            assert data["summary"]["median_resolution_time_hours"] == 0.0
            assert data["summary"]["avg_time_to_first_response_hours"] == 0.0
            assert data["summary"]["avg_comments_per_thread"] == 0.0
            assert data["summary"]["total_threads_analyzed"] == 0
            assert data["summary"]["resolution_rate"] == 0.0

            # Verify empty lists (not None or missing)
            assert isinstance(data["by_repository"], list)
            assert len(data["by_repository"]) == 0

            assert isinstance(data["threads"], list)
            assert len(data["threads"]) == 0

            # Verify pagination for empty results
            assert data["pagination"]["total"] == 0
            assert data["pagination"]["total_pages"] == 0

            # Verify database was queried correctly (both queries executed)
            assert mock_db.fetch.call_count == 2

    def test_get_comment_resolution_time_page_2(self) -> None:
        """Test fetching page 2 of results."""
        # Simulate page 2 with offset 25
        mock_threads_rows = [
            {
                "thread_node_id": f"PRRT_{i}",
                "repository": "org/repo1",
                "pr_number": 123,
                "file_path": f"file{i}.py",
                "first_comment_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "second_comment_at": None,
                "time_to_first_response_hours": None,
                "resolved_at": None,
                "resolver": None,
                "resolution_time_hours": None,
                "comment_count": 1,
                "participants": ["user1"],
                "can_be_merged_at": None,
                "time_from_can_be_merged_hours": None,
                "total_count": 50,
            }
            for i in range(25, 50)
        ]
        mock_repo_stats_rows = [
            {
                "repository": "org/repo1",
                "total_threads": 50,
                "resolved_threads": 0,
                "avg_resolution_time_hours": 0.0,
            },
        ]

        with patch("backend.routes.api.comment_resolution.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_threads_rows, mock_repo_stats_rows])

            client = TestClient(app)
            response = client.get(
                "/api/metrics/comment-resolution-time",
                params={"page": 2, "page_size": 25},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify pagination for page 2
            pagination = data["pagination"]
            assert pagination["total"] == 50
            assert pagination["page"] == 2
            assert pagination["page_size"] == 25
            assert pagination["total_pages"] == 2
            assert pagination["has_next"] is False
            assert pagination["has_prev"] is True

            # Verify threads from page 2
            assert len(data["threads"]) == 25
            assert data["threads"][0]["thread_node_id"] == "PRRT_25"
