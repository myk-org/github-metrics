"""Metrics dashboard controller for real-time webhook metrics streaming and visualization."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse


class MetricsDashboardController:
    """
    Controller for metrics dashboard functionality.

    Provides serving of the metrics dashboard HTML page.

    Example:
        controller = MetricsDashboardController(logger)
        html_response = controller.get_dashboard_page()
    """

    def __init__(self, logger: logging.Logger) -> None:
        """
        Initialize the metrics dashboard controller.

        Args:
            logger: Logger instance for this controller

        Architecture guarantees:
        - logger is ALWAYS provided (required parameter) - no defensive checks needed
        """
        self.logger = logger

    async def shutdown(self) -> None:
        """
        Perform cleanup during shutdown.

        This method should be called during application shutdown.
        """
        self.logger.info("Shutting down MetricsDashboardController")
        self.logger.info("MetricsDashboardController shutdown completed")

    def get_dashboard_page(self) -> HTMLResponse:
        """
        Serve the metrics dashboard HTML page.

        Returns:
            HTML response with metrics dashboard interface

        Raises:
            HTTPException: 500 for template loading errors
        """
        try:
            html_content = self._get_dashboard_html()
            return HTMLResponse(content=html_content)
        except Exception as e:
            self.logger.exception("Error serving metrics dashboard page")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    def _get_dashboard_html(self) -> str:
        """
        Load and return the metrics dashboard HTML template.

        Returns:
            HTML content for metrics dashboard interface

        Raises:
            FileNotFoundError: If template file cannot be found
            IOError: If template file cannot be read
        """
        template_path = Path(__file__).parent / "templates" / "metrics_dashboard.html"

        try:
            with open(template_path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            self.logger.exception(f"Metrics dashboard template not found at {template_path}")
            return self._get_fallback_html()
        except OSError:
            self.logger.exception("Failed to read metrics dashboard template")
            return self._get_fallback_html()

    def _get_fallback_html(self) -> str:
        """
        Provide a minimal fallback HTML when template loading fails.

        Returns:
            Basic HTML page with error message
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Metrics Dashboard (Error)</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .error-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .error-icon {
            font-size: 48px;
            color: #dc3545;
            margin-bottom: 20px;
        }
        .retry-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-icon">⚠️</div>
        <h1>Metrics Dashboard Template Error</h1>
        <p>The metrics dashboard template could not be loaded. Please check the server logs for details.</p>
        <button class="retry-btn" onclick="window.location.reload()">Refresh Page</button>
    </div>
</body>
</html>"""
