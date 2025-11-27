"""Tests for MetricsDashboardController class.

Tests dashboard functionality including:
- HTML page serving
- Dashboard rendering
- Error handling
- Graceful shutdown
"""

from __future__ import annotations

from unittest.mock import Mock, mock_open, patch

import pytest
from fastapi import HTTPException

from github_metrics.web.dashboard import MetricsDashboardController


class TestMetricsDashboardController:
    """Tests for MetricsDashboardController class."""

    @pytest.fixture
    def dashboard_controller(
        self,
        mock_logger: Mock,
    ) -> MetricsDashboardController:
        """Create MetricsDashboardController instance."""
        return MetricsDashboardController(logger=mock_logger)

    async def test_shutdown_completes_successfully(
        self,
        dashboard_controller: MetricsDashboardController,
        mock_logger: Mock,
    ) -> None:
        """Test shutdown completes successfully."""
        await dashboard_controller.shutdown()

        # Verify logging
        mock_logger.info.assert_called()

    def test_get_dashboard_page_success(
        self,
        dashboard_controller: MetricsDashboardController,
    ) -> None:
        """Test get_dashboard_page returns HTML response."""
        with patch.object(
            dashboard_controller,
            "_get_dashboard_html",
            return_value="<html>Dashboard</html>",
        ):
            response = dashboard_controller.get_dashboard_page()

            assert response.body == b"<html>Dashboard</html>"
            assert response.status_code == 200

    def test_get_dashboard_page_template_error(
        self,
        dashboard_controller: MetricsDashboardController,
        mock_logger: Mock,
    ) -> None:
        """Test get_dashboard_page raises HTTPException on template error."""
        with patch.object(
            dashboard_controller,
            "_get_dashboard_html",
            side_effect=Exception("Template error"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                dashboard_controller.get_dashboard_page()

            assert exc_info.value.status_code == 500
            mock_logger.exception.assert_called_once()

    def test_get_dashboard_html_success(
        self,
        dashboard_controller: MetricsDashboardController,
    ) -> None:
        """Test _get_dashboard_html returns template content."""
        mock_template_content = "<html><body>Test Dashboard</body></html>"

        with patch("builtins.open", mock_open(read_data=mock_template_content)):
            result = dashboard_controller._get_dashboard_html()

            assert result == mock_template_content

    def test_get_dashboard_html_file_not_found(
        self,
        dashboard_controller: MetricsDashboardController,
        mock_logger: Mock,
    ) -> None:
        """Test _get_dashboard_html returns fallback on FileNotFoundError."""
        with patch("builtins.open", side_effect=FileNotFoundError("Template not found")):
            result = dashboard_controller._get_dashboard_html()

            assert "Metrics Dashboard Template Error" in result
            assert "<!DOCTYPE html>" in result
            mock_logger.exception.assert_called_once()

    def test_get_dashboard_html_os_error(
        self,
        dashboard_controller: MetricsDashboardController,
        mock_logger: Mock,
    ) -> None:
        """Test _get_dashboard_html returns fallback on OSError."""
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = dashboard_controller._get_dashboard_html()

            assert "Metrics Dashboard Template Error" in result
            mock_logger.exception.assert_called()

    def test_get_fallback_html(
        self,
        dashboard_controller: MetricsDashboardController,
    ) -> None:
        """Test _get_fallback_html returns valid HTML."""
        result = dashboard_controller._get_fallback_html()

        assert "<!DOCTYPE html>" in result
        assert "Metrics Dashboard Template Error" in result
        assert "<html lang=" in result
        assert "window.location.reload()" in result
