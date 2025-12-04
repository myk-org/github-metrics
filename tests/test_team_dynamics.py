"""Tests for team dynamics API endpoint."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from github_metrics.app import app
from github_metrics.routes.api.team_dynamics import calculate_gini_coefficient


class TestGiniCoefficient:
    """Tests for Gini coefficient calculation."""

    def test_gini_empty_list(self) -> None:
        """Test Gini coefficient with empty list."""
        assert calculate_gini_coefficient([]) == 0.0

    def test_gini_single_value(self) -> None:
        """Test Gini coefficient with single value."""
        assert calculate_gini_coefficient([10]) == 0.0

    def test_gini_perfect_equality(self) -> None:
        """Test Gini coefficient with perfect equality."""
        # All values equal = perfect equality = 0.0
        result = calculate_gini_coefficient([10, 10, 10, 10])
        assert result == 0.0

    def test_gini_perfect_inequality(self) -> None:
        """Test Gini coefficient with perfect inequality."""
        # One person does everything = perfect inequality = close to 1.0
        result = calculate_gini_coefficient([0, 0, 0, 100])
        assert result > 0.7  # Should be high inequality

    def test_gini_moderate_inequality(self) -> None:
        """Test Gini coefficient with moderate inequality."""
        # Some spread but not extreme
        result = calculate_gini_coefficient([1, 2, 3, 4, 5])
        assert 0.2 < result < 0.4  # Moderate inequality


class TestTeamDynamicsEndpoint:
    """Tests for /api/metrics/team-dynamics endpoint."""

    @pytest.fixture
    def mock_workload_rows(self) -> list[dict[str, Any]]:
        """Create mock workload data."""
        return [
            {"user": "alice", "prs_created": 45, "prs_reviewed": 120, "prs_approved": 85},
            {"user": "bob", "prs_created": 30, "prs_reviewed": 90, "prs_approved": 60},
            {"user": "charlie", "prs_created": 15, "prs_reviewed": 50, "prs_approved": 20},
        ]

    @pytest.fixture
    def mock_review_rows(self) -> list[dict[str, Any]]:
        """Create mock review efficiency data."""
        return [
            {
                "user": "bob",
                "avg_review_time_hours": 1.2,
                "median_review_time_hours": 0.8,
                "total_reviews": 150,
                "overall_median_hours": 1.5,
            },
            {
                "user": "alice",
                "avg_review_time_hours": 2.5,
                "median_review_time_hours": 1.5,
                "total_reviews": 120,
                "overall_median_hours": 1.5,
            },
            {
                "user": "charlie",
                "avg_review_time_hours": 12.5,
                "median_review_time_hours": 8.0,
                "total_reviews": 50,
                "overall_median_hours": 1.5,
            },
        ]

    @pytest.fixture
    def mock_approval_rows(self) -> list[dict[str, Any]]:
        """Create mock approval bottleneck data."""
        return [
            {"approver": "charlie", "avg_approval_hours": 48.5, "total_approvals": 25},
            {"approver": "alice", "avg_approval_hours": 8.3, "total_approvals": 85},
            {"approver": "bob", "avg_approval_hours": 4.5, "total_approvals": 60},
        ]

    @pytest.fixture
    def mock_pending_row(self) -> dict[str, Any]:
        """Create mock pending PRs data."""
        return {"pending_count": 5}

    def test_team_dynamics_success(
        self,
        mock_workload_rows: list[dict[str, Any]],
        mock_review_rows: list[dict[str, Any]],
        mock_approval_rows: list[dict[str, Any]],
        mock_pending_row: dict[str, Any],
    ) -> None:
        """Test successful team dynamics retrieval."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_workload_rows,
                    mock_review_rows,
                    mock_approval_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(return_value=mock_pending_row)

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 200
            data = response.json()

            # Verify workload section
            assert "workload" in data
            assert "summary" in data["workload"]
            assert "by_contributor" in data["workload"]

            workload_summary = data["workload"]["summary"]
            assert workload_summary["total_contributors"] == 3
            assert workload_summary["avg_prs_per_contributor"] == 30.0  # (45+30+15)/3
            assert workload_summary["top_contributor"]["user"] == "alice"
            assert workload_summary["top_contributor"]["total_prs"] == 45
            assert "workload_gini" in workload_summary
            assert 0.0 <= workload_summary["workload_gini"] <= 1.0

            # Verify review efficiency section
            assert "review_efficiency" in data
            assert "summary" in data["review_efficiency"]
            assert "by_reviewer" in data["review_efficiency"]

            review_summary = data["review_efficiency"]["summary"]
            assert "avg_review_time_hours" in review_summary
            assert "median_review_time_hours" in review_summary
            assert review_summary["fastest_reviewer"]["user"] == "bob"
            assert review_summary["slowest_reviewer"]["user"] == "charlie"

            # Verify bottlenecks section
            assert "bottlenecks" in data
            assert "alerts" in data["bottlenecks"]
            assert "by_approver" in data["bottlenecks"]

            # Verify alerts are generated for slow approvers
            alerts = data["bottlenecks"]["alerts"]
            assert len(alerts) > 0
            # charlie should have critical alert (48.5 hours)
            charlie_alert = next((a for a in alerts if a["approver"] == "charlie"), None)
            assert charlie_alert is not None
            assert charlie_alert["severity"] == "critical"
            assert charlie_alert["avg_approval_hours"] == 48.5
            assert charlie_alert["team_pending_count"] == 5

    def test_team_dynamics_with_time_filter(
        self,
        mock_workload_rows: list[dict[str, Any]],
        mock_review_rows: list[dict[str, Any]],
        mock_approval_rows: list[dict[str, Any]],
        mock_pending_row: dict[str, Any],
    ) -> None:
        """Test team dynamics with time range filter."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_workload_rows,
                    mock_review_rows,
                    mock_approval_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(return_value=mock_pending_row)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/team-dynamics",
                params={
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-31T23:59:59Z",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "workload" in data
            assert "review_efficiency" in data
            assert "bottlenecks" in data

    def test_team_dynamics_with_repository_filter(
        self,
        mock_workload_rows: list[dict[str, Any]],
        mock_review_rows: list[dict[str, Any]],
        mock_approval_rows: list[dict[str, Any]],
        mock_pending_row: dict[str, Any],
    ) -> None:
        """Test team dynamics with repository filter."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_workload_rows,
                    mock_review_rows,
                    mock_approval_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(return_value=mock_pending_row)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/team-dynamics",
                params={"repository": "testorg/testrepo"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "workload" in data

    def test_team_dynamics_empty_data(self) -> None:
        """Test team dynamics with no data."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[[], [], []])
            mock_db.fetchrow = AsyncMock(return_value={"pending_count": 0})

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 200
            data = response.json()

            # Verify empty results
            assert data["workload"]["summary"]["total_contributors"] == 0
            assert data["workload"]["summary"]["avg_prs_per_contributor"] == 0.0
            assert data["workload"]["summary"]["top_contributor"] is None
            assert data["workload"]["by_contributor"] == []

            assert data["review_efficiency"]["by_reviewer"] == []
            assert data["bottlenecks"]["alerts"] == []
            assert data["bottlenecks"]["by_approver"] == []

    def test_team_dynamics_warning_severity(self) -> None:
        """Test bottleneck alert with warning severity."""
        workload_rows = [{"user": "alice", "prs_created": 10, "prs_reviewed": 20, "prs_approved": 15}]
        review_rows = [
            {
                "user": "alice",
                "avg_review_time_hours": 2.0,
                "median_review_time_hours": 1.5,
                "total_reviews": 20,
                "overall_median_hours": 1.5,
            }
        ]
        approval_rows = [{"approver": "alice", "avg_approval_hours": 30.0, "total_approvals": 15}]
        pending_row = {"pending_count": 4}

        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[workload_rows, review_rows, approval_rows])
            mock_db.fetchrow = AsyncMock(return_value=pending_row)

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 200
            data = response.json()

            alerts = data["bottlenecks"]["alerts"]
            assert len(alerts) == 1
            assert alerts[0]["severity"] == "warning"  # 30 hours > 24 but < 48

    def test_team_dynamics_no_alerts(self) -> None:
        """Test bottleneck with no alerts (fast approval times)."""
        workload_rows = [{"user": "alice", "prs_created": 10, "prs_reviewed": 20, "prs_approved": 15}]
        review_rows = [
            {
                "user": "alice",
                "avg_review_time_hours": 2.0,
                "median_review_time_hours": 1.5,
                "total_reviews": 20,
                "overall_median_hours": 1.5,
            }
        ]
        approval_rows = [{"approver": "alice", "avg_approval_hours": 4.0, "total_approvals": 15}]
        pending_row = {"pending_count": 2}

        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[workload_rows, review_rows, approval_rows])
            mock_db.fetchrow = AsyncMock(return_value=pending_row)

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 200
            data = response.json()

            # No alerts should be generated
            assert len(data["bottlenecks"]["alerts"]) == 0

    def test_team_dynamics_invalid_time_format(self) -> None:
        """Test team dynamics with invalid time format."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            # Mock db_manager to ensure datetime parsing happens before database access
            mock_db.fetch = AsyncMock(return_value=[])
            mock_db.fetchrow = AsyncMock(return_value={"pending_count": 0})

            client = TestClient(app)
            response = client.get(
                "/api/metrics/team-dynamics",
                params={"start_time": "invalid-date"},
            )

            assert response.status_code == 400
            assert "Invalid datetime format" in response.json()["detail"]

    def test_team_dynamics_database_error(self) -> None:
        """Test team dynamics with database error."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=Exception("Database connection failed"))

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 500
            assert "Failed to fetch team dynamics metrics" in response.json()["detail"]

    def test_team_dynamics_without_db_manager(self) -> None:
        """Test team dynamics when db_manager is None."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 500
            assert "Database not available" in response.json()["detail"]

    def test_team_dynamics_response_structure(
        self,
        mock_workload_rows: list[dict[str, Any]],
        mock_review_rows: list[dict[str, Any]],
        mock_approval_rows: list[dict[str, Any]],
        mock_pending_row: dict[str, Any],
    ) -> None:
        """Test team dynamics response has correct structure."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_workload_rows,
                    mock_review_rows,
                    mock_approval_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(return_value=mock_pending_row)

            client = TestClient(app)
            response = client.get("/api/metrics/team-dynamics")

            assert response.status_code == 200
            data = response.json()

            # Verify top-level structure
            assert set(data.keys()) == {"workload", "review_efficiency", "bottlenecks"}

            # Verify workload structure
            assert set(data["workload"].keys()) == {"summary", "by_contributor"}
            assert set(data["workload"]["summary"].keys()) == {
                "total_contributors",
                "avg_prs_per_contributor",
                "top_contributor",
                "workload_gini",
            }

            # Verify contributor data structure
            for contributor in data["workload"]["by_contributor"]:
                assert set(contributor.keys()) == {"user", "prs_created", "prs_reviewed", "prs_approved"}

            # Verify review efficiency structure
            assert set(data["review_efficiency"].keys()) == {"summary", "by_reviewer"}
            assert set(data["review_efficiency"]["summary"].keys()) == {
                "avg_review_time_hours",
                "median_review_time_hours",
                "fastest_reviewer",
                "slowest_reviewer",
            }

            # Verify reviewer data structure
            for reviewer in data["review_efficiency"]["by_reviewer"]:
                assert set(reviewer.keys()) == {
                    "user",
                    "avg_review_time_hours",
                    "median_review_time_hours",
                    "total_reviews",
                }

            # Verify bottlenecks structure
            assert set(data["bottlenecks"].keys()) == {"alerts", "by_approver"}

            # Verify alert structure
            for alert in data["bottlenecks"]["alerts"]:
                assert set(alert.keys()) == {"approver", "avg_approval_hours", "team_pending_count", "severity"}
                assert alert["severity"] in {"critical", "warning"}

            # Verify approver data structure
            for approver in data["bottlenecks"]["by_approver"]:
                assert set(approver.keys()) == {"approver", "avg_approval_hours", "total_approvals"}

    def test_team_dynamics_with_user_filter(
        self,
        mock_workload_rows: list[dict[str, Any]],
        mock_review_rows: list[dict[str, Any]],
        mock_approval_rows: list[dict[str, Any]],
        mock_pending_row: dict[str, Any],
    ) -> None:
        """Test team dynamics with user filter."""
        with patch("github_metrics.routes.api.team_dynamics.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    mock_workload_rows,
                    mock_review_rows,
                    mock_approval_rows,
                ]
            )
            mock_db.fetchrow = AsyncMock(return_value=mock_pending_row)

            client = TestClient(app)
            response = client.get(
                "/api/metrics/team-dynamics",
                params={"user": "alice"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "workload" in data
            assert "review_efficiency" in data
            assert "bottlenecks" in data
