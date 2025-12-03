"""Dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from fastapi.responses import HTMLResponse

from github_metrics.web.dashboard import MetricsDashboardController

router = APIRouter()

# Global dashboard controller (set by app.py during lifespan)
dashboard_controller: MetricsDashboardController | None = None


@router.get("/dashboard", operation_id="get_dashboard", response_class=HTMLResponse, tags=["mcp_exclude"])
async def get_dashboard() -> HTMLResponse:
    """Serve the metrics dashboard HTML page."""
    if dashboard_controller is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard controller not initialized",
        )
    return dashboard_controller.get_dashboard_page()
