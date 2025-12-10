"""Test NULL normalization in cross-team endpoint."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def cross_team_client() -> Generator[tuple[TestClient, MagicMock]]:
    """Fixture providing TestClient and mock db_manager for cross-team tests."""
    with patch("backend.routes.api.cross_team.db_manager") as mock_db:
        client = TestClient(app)
        yield client, mock_db


class TestCrossTeamNullNormalization:
    """Test NULL value normalization in cross-team reviews endpoint."""

    def test_null_teams_normalized_to_unknown(self, cross_team_client: tuple[TestClient, MagicMock]) -> None:
        """Test that NULL reviewer_team and pr_sig_label values are normalized to 'unknown'."""
        client, mock_db = cross_team_client

        # Mock data with NULL values
        mock_data_rows: list[dict[str, object]] = []

        mock_reviewer_team_summary = [
            {"reviewer_team": "sig-storage", "count": 5},
            {"reviewer_team": None, "count": 3},  # NULL team
            {"reviewer_team": "sig-network", "count": 2},
        ]

        mock_pr_team_summary = [
            {"pr_sig_label": "sig-compute", "count": 4},
            {"pr_sig_label": None, "count": 6},  # NULL label
        ]

        # Mock count query
        mock_db.fetchval = AsyncMock(return_value=10)
        # Mock all fetch queries (data, by_reviewer_team, by_pr_team)
        mock_db.fetch = AsyncMock(
            side_effect=[
                mock_data_rows,
                mock_reviewer_team_summary,
                mock_pr_team_summary,
            ]
        )

        response = client.get("/api/metrics/cross-team-reviews")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify NULL normalization in summary
        by_reviewer_team = data["summary"]["by_reviewer_team"]
        by_pr_team = data["summary"]["by_pr_team"]

        # Check that NULL values are normalized to 'unknown'
        assert "unknown" in by_reviewer_team, "NULL reviewer_team not normalized to unknown"
        assert by_reviewer_team["unknown"] == 3

        assert "unknown" in by_pr_team, "NULL pr_sig_label not normalized to unknown"
        assert by_pr_team["unknown"] == 6

        # Verify other teams are preserved correctly
        assert by_reviewer_team["sig-storage"] == 5
        assert by_reviewer_team["sig-network"] == 2
        assert by_pr_team["sig-compute"] == 4

    def test_all_null_teams(self, cross_team_client: tuple[TestClient, MagicMock]) -> None:
        """Test when all teams are NULL."""
        client, mock_db = cross_team_client

        mock_data_rows: list[dict[str, object]] = []

        mock_reviewer_team_summary = [
            {"reviewer_team": None, "count": 10},
        ]

        mock_pr_team_summary = [
            {"pr_sig_label": None, "count": 10},
        ]

        mock_db.fetchval = AsyncMock(return_value=10)
        mock_db.fetch = AsyncMock(
            side_effect=[
                mock_data_rows,
                mock_reviewer_team_summary,
                mock_pr_team_summary,
            ]
        )

        response = client.get("/api/metrics/cross-team-reviews")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All NULL values should be normalized to 'unknown'
        assert data["summary"]["by_reviewer_team"] == {"unknown": 10}
        assert data["summary"]["by_pr_team"] == {"unknown": 10}

    def test_no_null_teams(self, cross_team_client: tuple[TestClient, MagicMock]) -> None:
        """Test when no NULL teams exist (regression test)."""
        client, mock_db = cross_team_client

        mock_data_rows: list[dict[str, object]] = []

        mock_reviewer_team_summary = [
            {"reviewer_team": "sig-storage", "count": 5},
            {"reviewer_team": "sig-network", "count": 3},
        ]

        mock_pr_team_summary = [
            {"pr_sig_label": "sig-compute", "count": 4},
            {"pr_sig_label": "sig-network", "count": 4},
        ]

        mock_db.fetchval = AsyncMock(return_value=8)
        mock_db.fetch = AsyncMock(
            side_effect=[
                mock_data_rows,
                mock_reviewer_team_summary,
                mock_pr_team_summary,
            ]
        )

        response = client.get("/api/metrics/cross-team-reviews")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # No 'unknown' key should exist
        assert "unknown" not in data["summary"]["by_reviewer_team"]
        assert "unknown" not in data["summary"]["by_pr_team"]

        # All teams should be preserved
        assert data["summary"]["by_reviewer_team"]["sig-storage"] == 5
        assert data["summary"]["by_reviewer_team"]["sig-network"] == 3
        assert data["summary"]["by_pr_team"]["sig-compute"] == 4
        assert data["summary"]["by_pr_team"]["sig-network"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
