"""
FastAPI application for GitHub Metrics service.

Standalone metrics server for webhook event tracking and visualization.
All endpoints are async for optimal performance.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import logging
import math
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi import status as http_status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP
from fastapi_mcp.transport.http import FastApiHttpSessionManager
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from simple_logger.logger import get_logger

from github_metrics.config import get_config
from github_metrics.database import DatabaseManager, get_database_manager
from github_metrics.metrics_tracker import MetricsTracker
from github_metrics.pr_story import get_pr_story
from github_metrics.utils.security import (
    get_cloudflare_allowlist,
    get_github_allowlist,
    verify_ip_allowlist,
    verify_signature,
)
from github_metrics.web.dashboard import MetricsDashboardController


class MCPClosedResourceErrorFilter(logging.Filter):
    """Filter to suppress known ClosedResourceError from MCP library.

    This filter only suppresses ClosedResourceError messages while allowing all other
    log records through normally. The error occurs in the MCP library's message router
    but doesn't affect functionality.

    TODO: Remove this filter when upstream issue is fixed:
    https://github.com/modelcontextprotocol/python-sdk/issues/1219
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out ClosedResourceError log records.

        Args:
            record: The log record to evaluate.

        Returns:
            False to suppress the record, True to allow it through.
        """
        # Check if ClosedResourceError appears in the message or exception info
        if "ClosedResourceError" in str(record.msg):
            return False
        if record.exc_info and "ClosedResourceError" in str(record.exc_info):
            return False
        return True


# Add filter to MCP logger to suppress specific known errors while allowing other logs
_mcp_logger = logging.getLogger("mcp.server.streamable_http")
_mcp_logger.addFilter(MCPClosedResourceErrorFilter())

# Type alias for IP networks (avoiding private type)
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Module-level logger
LOGGER = get_logger(name="github_metrics.app")

# Global instances (initialized in lifespan)
db_manager: DatabaseManager | None = None
metrics_tracker: MetricsTracker | None = None
dashboard_controller: MetricsDashboardController | None = None
http_client: httpx.AsyncClient | None = None
allowed_ips: tuple[IPNetwork, ...] = ()

# MCP Globals - typed as concrete classes where possible
# Note: Using library types directly; http_transport requires manual setup for stateless mode
http_transport: FastApiHttpSessionManager | None = None
mcp_instance: FastApiMCP | None = None


def parse_datetime_string(value: str | None, param_name: str) -> datetime | None:
    """Parse ISO 8601 datetime string to datetime object."""
    if value is None:
        return None
    try:
        # Handle both 'Z' suffix and '+00:00' timezone
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError as ex:
        detail = f"Invalid datetime format for {param_name}: {value}. Use ISO 8601 format (e.g., 2024-01-15T00:00:00Z)"
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from ex


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - manage database connections and IP allowlists."""
    global db_manager, metrics_tracker, dashboard_controller, http_client, allowed_ips

    LOGGER.info("Starting GitHub Metrics service...")

    config = get_config()

    # Initialize HTTP client for IP allowlist fetching
    http_client = httpx.AsyncClient(timeout=10.0)

    # Load IP allowlists if verification is enabled
    ip_ranges: list[IPNetwork] = []

    if config.webhook.verify_github_ips:
        LOGGER.info("Loading GitHub IP allowlist...")
        try:
            github_ips = await get_github_allowlist(http_client)
            for ip_range in github_ips:
                try:
                    ip_ranges.append(ipaddress.ip_network(ip_range))
                except ValueError:
                    LOGGER.warning("Invalid IP range from GitHub allowlist, skipping", extra={"ip_range": ip_range})
            LOGGER.info(f"Loaded {len(github_ips)} GitHub IP ranges")
        except Exception:
            LOGGER.exception("Failed to load GitHub IP allowlist")
            raise

    if config.webhook.verify_cloudflare_ips:
        LOGGER.info("Loading Cloudflare IP allowlist...")
        try:
            cloudflare_ips = await get_cloudflare_allowlist(http_client)
            for ip_range in cloudflare_ips:
                try:
                    ip_ranges.append(ipaddress.ip_network(ip_range))
                except ValueError:
                    LOGGER.warning("Invalid IP range from Cloudflare allowlist, skipping", extra={"ip_range": ip_range})
            LOGGER.info(f"Loaded {len(cloudflare_ips)} Cloudflare IP ranges")
        except Exception:
            LOGGER.exception("Failed to load Cloudflare IP allowlist")
            raise

    allowed_ips = tuple(ip_ranges)
    LOGGER.info(
        "IP verification configured",
        extra={
            "verify_github_ips": config.webhook.verify_github_ips,
            "verify_cloudflare_ips": config.webhook.verify_cloudflare_ips,
        },
    )

    # Initialize database manager
    db_manager = get_database_manager()
    await db_manager.connect()
    LOGGER.info("Database connection established")

    # Database schema is managed by Alembic migrations
    LOGGER.info("Database schema managed by Alembic migrations")

    # Initialize metrics tracker
    metrics_logger = get_logger(name="github_metrics.tracker")
    metrics_tracker = MetricsTracker(db_manager, metrics_logger)
    LOGGER.info("Metrics tracker initialized")

    # Initialize dashboard controller
    dashboard_logger = get_logger(name="github_metrics.dashboard")
    dashboard_controller = MetricsDashboardController(dashboard_logger)
    LOGGER.info("Dashboard controller initialized")

    # Initialize MCP session manager if enabled
    # Note: We manually configure the session manager instead of using the library's
    # _ensure_session_manager_started() helper because:
    # 1. We require stateless=True to avoid session ID requirements for MCP clients
    # 2. The library's helper hardcodes stateless=False (as of fastapi-mcp 0.4.0)
    # 3. We need the session manager started during application startup, not lazily on first request
    #
    # This approach is acceptable per fastapi-mcp design - the library exposes
    # _session_manager, _manager_task, and _manager_started for manual management.
    # We use the library's shutdown() method for proper cleanup (see shutdown section below).
    if config.mcp.enabled and http_transport is not None and mcp_instance is not None:
        if http_transport._session_manager is None:
            http_transport._session_manager = StreamableHTTPSessionManager(
                app=mcp_instance.server,
                event_store=http_transport.event_store,
                json_response=True,
                stateless=True,  # Required: avoid session ID requirements
            )

            async def run_manager() -> None:
                if http_transport and http_transport._session_manager:
                    async with http_transport._session_manager.run():
                        await asyncio.Event().wait()

            http_transport._manager_task = asyncio.create_task(run_manager())
            http_transport._manager_started = True
            LOGGER.info("MCP session manager initialized with stateless mode")

    yield

    # Shutdown
    LOGGER.info("Shutting down GitHub Metrics service...")

    # Shutdown MCP session manager first (before other resources)
    # Use library-provided shutdown() method for proper cleanup
    if http_transport is not None:
        await http_transport.shutdown()
        LOGGER.debug("MCP session manager shutdown complete")

    if dashboard_controller is not None:
        await dashboard_controller.shutdown()
        LOGGER.debug("Dashboard controller shutdown complete")

    if http_client is not None:
        await http_client.aclose()
        LOGGER.debug("HTTP client closed")

    if db_manager is not None:
        await db_manager.disconnect()
        LOGGER.info("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="GitHub Metrics",
        description="Metrics service for GitHub webhook event tracking and visualization",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    static_path = Path(__file__).parent / "web" / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    return app


# Create the app
app = create_app()


# Health check endpoint
@app.get("/health", operation_id="health_check")
async def health_check() -> dict[str, Any]:
    """Check service health and database connectivity."""
    db_healthy = False
    if db_manager is not None:
        db_healthy = await db_manager.health_check()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": db_healthy,
        "version": "0.1.0",
    }


# Favicon endpoint
@app.get("/favicon.ico", include_in_schema=False, tags=["mcp_exclude"])
async def favicon() -> Response:
    """Serve favicon.ico."""
    transparent_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return Response(content=transparent_png, media_type="image/png")


# Webhook endpoint - receives GitHub webhook events
@app.post("/metrics", operation_id="receive_webhook", tags=["mcp_exclude"])
async def receive_webhook(request: Request) -> dict[str, str]:
    """Receive and process GitHub webhook events.

    Verifies IP allowlist (if configured) and webhook signature,
    then stores the event metrics in the database.
    """
    start_time = time.time()
    config = get_config()

    # Verify IP allowlist
    await verify_ip_allowlist(request, allowed_ips)

    # Get request body
    payload_body = await request.body()

    # Verify webhook signature if secret is configured
    if config.webhook.secret:
        signature_header = request.headers.get("x-hub-signature-256")
        verify_signature(payload_body, config.webhook.secret, signature_header)

    # Parse webhook payload
    try:
        payload: dict[str, Any] = await request.json()
    except Exception as ex:
        LOGGER.exception("Failed to parse webhook payload")
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from ex

    # Extract event metadata
    delivery_id = request.headers.get("x-github-delivery", "unknown")
    event_type = request.headers.get("x-github-event", "unknown")
    action = payload.get("action", "")

    # Extract repository info
    repository_data = payload.get("repository", {})
    repository = repository_data.get("full_name", "unknown")

    # Extract sender info
    sender_data = payload.get("sender", {})
    sender = sender_data.get("login", "unknown")

    # Extract PR number if applicable
    pr_number: int | None = None
    if "pull_request" in payload:
        pr_number = payload["pull_request"].get("number")
    elif "issue" in payload and "pull_request" in payload.get("issue", {}):
        pr_number = payload["issue"].get("number")

    # Calculate processing time
    processing_time_ms = int((time.time() - start_time) * 1000)

    # Store the webhook event
    if metrics_tracker is not None:
        try:
            await metrics_tracker.track_webhook_event(
                delivery_id=delivery_id,
                repository=repository,
                event_type=event_type,
                action=action,
                sender=sender,
                payload=payload,
                processing_time_ms=processing_time_ms,
                status="success",
                pr_number=pr_number,
            )
        except Exception:
            LOGGER.exception(
                "Failed to track webhook event",
                extra={
                    "delivery_id": delivery_id,
                    "repository": repository,
                    "event_type": event_type,
                    "action": action,
                },
            )
            # Don't fail the webhook - just log the error

    LOGGER.info(
        "Webhook received",
        extra={
            "delivery_id": delivery_id,
            "repository": repository,
            "event_type": event_type,
            "action": action,
        },
    )

    return {"status": "ok", "delivery_id": delivery_id}


# Dashboard endpoints
@app.get("/dashboard", operation_id="get_dashboard", response_class=HTMLResponse, tags=["mcp_exclude"])
async def get_dashboard() -> HTMLResponse:
    """Serve the metrics dashboard HTML page."""
    if dashboard_controller is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard controller not initialized",
        )
    return dashboard_controller.get_dashboard_page()


# API endpoints
@app.get("/api/metrics/webhooks", operation_id="get_webhook_events")
async def get_webhook_events(
    repository: str | None = Query(default=None, description="Filter by repository (org/repo format)"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    status: str | None = Query(default=None, description="Filter by status (success, error, partial)"),
    start_time: str | None = Query(default=None, description="Start time in ISO 8601 format"),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=100, ge=1, le=1000, description="Items per page"),
) -> dict[str, Any]:
    """Retrieve webhook events with filtering and pagination."""
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build query
    query = """
        SELECT
            delivery_id, repository, event_type, action, pr_number, sender,
            status, created_at, processed_at, duration_ms,
            api_calls_count, token_spend, token_remaining, error_message
        FROM webhooks WHERE 1=1
    """
    params: list[Any] = []
    param_idx = 1

    if repository:
        query += " AND repository = $" + str(param_idx)
        params.append(repository)
        param_idx += 1

    if event_type:
        query += " AND event_type = $" + str(param_idx)
        params.append(event_type)
        param_idx += 1

    if status:
        query += " AND status = $" + str(param_idx)
        params.append(status)
        param_idx += 1

    if start_datetime:
        query += " AND created_at >= $" + str(param_idx)
        params.append(start_datetime)
        param_idx += 1

    if end_datetime:
        query += " AND created_at <= $" + str(param_idx)
        params.append(end_datetime)
        param_idx += 1

    offset = (page - 1) * page_size
    MAX_OFFSET = 10000  # Prevent expensive deep pagination
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )
    count_query = "SELECT COUNT(*) FROM (" + query + ") AS filtered"
    query += " ORDER BY created_at DESC LIMIT $" + str(param_idx) + " OFFSET $" + str(param_idx + 1)
    params.extend([page_size, offset])

    try:
        total_count = await db_manager.fetchval(count_query, *params[:-2])
        rows = await db_manager.fetch(query, *params)

        events = [
            {
                "delivery_id": row["delivery_id"],
                "repository": row["repository"],
                "event_type": row["event_type"],
                "action": row["action"],
                "pr_number": row["pr_number"],
                "sender": row["sender"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
                "duration_ms": row["duration_ms"],
                "api_calls_count": row["api_calls_count"],
                "token_spend": row["token_spend"],
                "token_remaining": row["token_remaining"],
                "error_message": row["error_message"],
            }
            for row in rows
        ]

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return {
            "data": events,
            "pagination": {
                "total": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch webhook events")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch webhook events",
        ) from ex


@app.get("/api/metrics/webhooks/{delivery_id}", operation_id="get_webhook_event_by_id")
async def get_webhook_event_by_id(delivery_id: str) -> dict[str, Any]:
    """Get specific webhook event details including full payload."""
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    query = """
        SELECT
            delivery_id, repository, event_type, action, pr_number, sender,
            payload, status, created_at, processed_at, duration_ms,
            api_calls_count, token_spend, token_remaining, error_message
        FROM webhooks WHERE delivery_id = $1
    """

    try:
        row = await db_manager.fetchrow(query, delivery_id)
        if not row:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Webhook event not found: {delivery_id}",
            )

        return {
            "delivery_id": row["delivery_id"],
            "repository": row["repository"],
            "event_type": row["event_type"],
            "action": row["action"],
            "pr_number": row["pr_number"],
            "sender": row["sender"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
            "duration_ms": row["duration_ms"],
            "api_calls_count": row["api_calls_count"],
            "token_spend": row["token_spend"],
            "token_remaining": row["token_remaining"],
            "error_message": row["error_message"],
            "payload": row["payload"],
        }
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch webhook event", extra={"delivery_id": delivery_id})
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch webhook event",
        ) from ex


@app.get("/api/metrics/repositories", operation_id="get_repository_statistics")
async def get_repository_statistics(
    start_time: str | None = Query(default=None, description="Start time in ISO 8601 format"),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """Get aggregated statistics per repository."""
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    where_clause = "WHERE 1=1"
    params: list[Any] = []
    param_idx = 1

    if start_datetime:
        where_clause += " AND created_at >= $" + str(param_idx)
        params.append(start_datetime)
        param_idx += 1

    if end_datetime:
        where_clause += " AND created_at <= $" + str(param_idx)
        params.append(end_datetime)
        param_idx += 1

    offset = (page - 1) * page_size
    MAX_OFFSET = 10000  # Prevent expensive deep pagination
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )

    count_query = (
        """
        SELECT COUNT(DISTINCT repository) as total FROM webhooks """
        + where_clause
    )

    query = (
        """
        SELECT
            repository,
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric /
                 NULLIF(COUNT(*)::numeric, 0) * 100)::numeric, 2
            ) as success_rate,
            ROUND(AVG(duration_ms)) as avg_processing_time_ms,
            SUM(api_calls_count) as total_api_calls,
            SUM(token_spend) as total_token_spend
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY repository
        ORDER BY total_events DESC
        LIMIT $"""
        + str(param_idx)
        + " OFFSET $"
        + str(param_idx + 1)
    )
    params.extend([page_size, offset])

    try:
        total_count = await db_manager.fetchval(count_query, *params[:-2])
        rows = await db_manager.fetch(query, *params)

        repositories = [
            {
                "repository": row["repository"],
                "total_events": row["total_events"],
                "successful_events": row["successful_events"],
                "failed_events": row["failed_events"],
                "success_rate": float(row["success_rate"]) if row["success_rate"] else 0.0,
                "avg_processing_time_ms": int(row["avg_processing_time_ms"]) if row["avg_processing_time_ms"] else 0,
                "total_api_calls": row["total_api_calls"] or 0,
                "total_token_spend": row["total_token_spend"] or 0,
            }
            for row in rows
        ]

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "repositories": repositories,
            "pagination": {
                "total": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch repository statistics")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch repository statistics",
        ) from ex


@app.get("/api/metrics/summary", operation_id="get_metrics_summary")
async def get_metrics_summary(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
) -> dict[str, Any]:
    """Get overall metrics summary for webhook processing.

    Provides high-level overview of webhook processing metrics including total events,
    performance statistics, success rates, and top repositories. Essential for operational
    dashboards, executive reporting, and system health monitoring.

    **Primary Use Cases:**
    - Generate executive dashboards and summary reports
    - Monitor overall system health and performance
    - Track webhook processing trends over time
    - Identify system-wide performance issues
    - Analyze API usage patterns across all repositories
    - Quick health check for webhook processing system

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format.
      Example: "2024-01-01T00:00:00Z"
      Default: No time filter (all-time stats)
    - `end_time` (str, optional): End of time range in ISO 8601 format.
      Example: "2024-01-31T23:59:59Z"
      Default: No time filter (up to current time)

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-31T23:59:59Z"
      },
      "summary": {
        "total_events": 8745,
        "successful_events": 8423,
        "failed_events": 322,
        "success_rate": 96.32,
        "avg_processing_time_ms": 5834,
        "median_processing_time_ms": 4521,
        "p95_processing_time_ms": 14234,
        "max_processing_time_ms": 52134,
        "total_api_calls": 104940,
        "avg_api_calls_per_event": 12.0,
        "total_token_spend": 104940,
        "total_events_trend": 15.3,
        "success_rate_trend": 2.1,
        "failed_events_trend": -8.5,
        "avg_duration_trend": -12.4
      },
      "top_repositories": [
        {
          "repository": "myakove/high-traffic-repo",
          "total_events": 3456,
          "success_rate": 98.5
        },
        {
          "repository": "myakove/medium-traffic-repo",
          "total_events": 2134,
          "success_rate": 95.2
        },
        {
          "repository": "myakove/low-traffic-repo",
          "total_events": 856,
          "success_rate": 97.8
        }
      ],
      "event_type_distribution": {
        "pull_request": 4523,
        "issue_comment": 2134,
        "check_run": 1234,
        "push": 854
      },
      "hourly_event_rate": 12.3,
      "daily_event_rate": 295.4
    }
    ```

    **Metrics Explained:**
    - `total_events`: Total webhook events processed in time range
    - `successful_events`: Events that completed successfully
    - `failed_events`: Events that failed or partially failed
    - `success_rate`: Overall success percentage (0-100)
    - `avg_processing_time_ms`: Average processing duration across all events
    - `median_processing_time_ms`: Median processing duration (50th percentile)
    - `p95_processing_time_ms`: 95th percentile processing time (SLA metric)
    - `max_processing_time_ms`: Maximum processing time (worst case scenario)
    - `total_api_calls`: Total GitHub API calls made across all events
    - `avg_api_calls_per_event`: Average API calls per webhook event
    - `total_token_spend`: Total rate limit tokens consumed
    - `total_events_trend`: Percentage change in total events vs previous period (e.g., 15.3 = 15.3% increase)
    - `success_rate_trend`: Percentage change in success rate vs previous period
    - `failed_events_trend`: Percentage change in failed events vs previous period (negative = improvement)
    - `avg_duration_trend`: Percentage change in avg processing time vs previous period (negative = faster)
    - `top_repositories`: Top 10 repositories by event volume
    - `event_type_distribution`: Event count breakdown by type
    - `hourly_event_rate`: Average events per hour in time range
    - `daily_event_rate`: Average events per day in time range

    **Trend Calculation:**
    - Trends compare current period to previous period of equal duration
    - Example: If querying last 24 hours, trends compare to 24 hours before that
    - Trend = ((current - previous) / previous) * 100
    - Returns 0.0 if no previous data or both periods have no events
    - Returns 100.0 if previous period had 0 but current period has data
    - Negative trends for duration metrics indicate performance improvement

    **Common Analysis Scenarios:**
    - Daily summary: `start_time=<today>&end_time=<now>`
    - Weekly trends: `start_time=<week_start>&end_time=<week_end>`
    - Monthly reporting: `start_time=2024-01-01&end_time=2024-01-31`
    - System health check: No time filters (all-time stats)

    **Error Conditions:**
    - 400: Invalid datetime format in start_time/end_time parameters
    - 500: Database connection errors or query failures

    **AI Agent Usage Examples:**
    - "Show overall metrics summary for last month for executive report"
    - "Get webhook processing health metrics to check system status"
    - "Analyze event type distribution to understand webhook traffic patterns"
    - "Review top repositories by event volume to identify high-traffic sources"

    **Performance Notes:**
    - Summary computed in real-time from webhooks table
    - Optimized queries using indexed columns (created_at, repository, event_type)
    - Large date ranges may increase query time
    - Consider caching for frequently accessed time ranges
    """

    # Helper function to calculate percentage change trends
    def calculate_trend(current: float, previous: float) -> float:
        """Calculate percentage change from previous to current.

        Args:
            current: Current period value
            previous: Previous period value

        Returns:
            Percentage change rounded to 1 decimal place
            - Returns 0.0 if both values are 0
            - Returns 100.0 if previous is 0 but current is not
        """
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / previous) * 100, 1)

    # Validate database manager is available
    if db_manager is None:
        LOGGER.error("Database manager not initialized - metrics server may not be properly configured")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    # Parse datetime strings
    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Calculate previous period for trend comparison
    prev_start_datetime = None
    prev_end_datetime = None
    if start_datetime and end_datetime:
        # Previous period has same duration as current period
        period_duration = end_datetime - start_datetime
        prev_start_datetime = start_datetime - period_duration
        prev_end_datetime = end_datetime - period_duration

    # Build query with time filters for current period
    where_clause = "WHERE 1=1"
    params: list[Any] = []
    param_idx = 1

    if start_datetime:
        where_clause += " AND created_at >= $" + str(param_idx)
        params.append(start_datetime)
        param_idx += 1

    if end_datetime:
        where_clause += " AND created_at <= $" + str(param_idx)
        params.append(end_datetime)
        param_idx += 1

    # Build query with time filters for previous period
    prev_where_clause = "WHERE 1=1"
    prev_params: list[Any] = []
    prev_param_idx = 1

    if prev_start_datetime:
        prev_where_clause += " AND created_at >= $" + str(prev_param_idx)
        prev_params.append(prev_start_datetime)
        prev_param_idx += 1

    if prev_end_datetime:
        prev_where_clause += " AND created_at <= $" + str(prev_param_idx)
        prev_params.append(prev_end_datetime)
        prev_param_idx += 1

    # Main summary query
    summary_query = (
        """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / NULLIF(COUNT(*), 0)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(AVG(duration_ms)) as avg_processing_time_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as median_processing_time_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_processing_time_ms,
            MAX(duration_ms) as max_processing_time_ms,
            SUM(api_calls_count) as total_api_calls,
            ROUND(AVG(api_calls_count), 2) as avg_api_calls_per_event,
            SUM(token_spend) as total_token_spend
        FROM webhooks
        """
        + where_clause
    )

    # Top repositories query
    top_repos_query = (
        """
        WITH total AS (
            SELECT COUNT(*) as total_count
            FROM webhooks
            """
        + where_clause
        + """
        )
        SELECT
            repository,
            COUNT(*) as total_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / COUNT(*)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(
                (COUNT(*)::numeric / (SELECT total_count FROM total) * 100)::numeric,
                2
            ) as percentage
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY repository
        ORDER BY total_events DESC
        LIMIT 10
    """
    )

    # Event type distribution query
    event_type_query = (
        """
        SELECT
            event_type,
            COUNT(*) as event_count
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY event_type
        ORDER BY event_count DESC
    """
    )

    # Time range for rate calculations
    time_range_query = (
        """
        SELECT
            MIN(created_at) as first_event_time,
            MAX(created_at) as last_event_time
        FROM webhooks
        """
        + where_clause
    )

    # Previous period summary query for trend calculation
    prev_summary_query = (
        """
        SELECT
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'success')::numeric / NULLIF(COUNT(*), 0)::numeric * 100)::numeric,
                2
            ) as success_rate,
            ROUND(AVG(duration_ms)) as avg_processing_time_ms
        FROM webhooks
        """
        + prev_where_clause
    )

    try:
        # Execute queries using DatabaseManager helpers
        summary_row = await db_manager.fetchrow(summary_query, *params)
        top_repos_rows = await db_manager.fetch(top_repos_query, *params)
        event_type_rows = await db_manager.fetch(event_type_query, *params)
        time_range_row = await db_manager.fetchrow(time_range_query, *params)

        # Execute previous period query if time range is specified
        prev_summary_row = None
        if prev_start_datetime and prev_end_datetime:
            prev_summary_row = await db_manager.fetchrow(prev_summary_query, *prev_params)

        # Ensure summary_row is not None before processing
        if summary_row is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Summary query returned no results",
            )

        # Process summary metrics
        total_events = summary_row["total_events"] or 0
        current_success_rate = float(summary_row["success_rate"]) if summary_row["success_rate"] is not None else 0.0
        current_failed_events = summary_row["failed_events"] or 0
        current_avg_duration = (
            int(summary_row["avg_processing_time_ms"]) if summary_row["avg_processing_time_ms"] is not None else 0
        )

        summary = {
            "total_events": total_events,
            "successful_events": summary_row["successful_events"] or 0,
            "failed_events": current_failed_events,
            "success_rate": current_success_rate,
            "avg_processing_time_ms": current_avg_duration,
            "median_processing_time_ms": int(summary_row["median_processing_time_ms"])
            if summary_row["median_processing_time_ms"] is not None
            else 0,
            "p95_processing_time_ms": int(summary_row["p95_processing_time_ms"])
            if summary_row["p95_processing_time_ms"] is not None
            else 0,
            "max_processing_time_ms": summary_row["max_processing_time_ms"] or 0,
            "total_api_calls": summary_row["total_api_calls"] or 0,
            "avg_api_calls_per_event": float(summary_row["avg_api_calls_per_event"])
            if summary_row["avg_api_calls_per_event"] is not None
            else 0.0,
            "total_token_spend": summary_row["total_token_spend"] or 0,
        }

        # Calculate and add trend fields if previous period data is available
        if prev_summary_row is not None:
            prev_total_events = prev_summary_row["total_events"] or 0
            prev_success_rate = (
                float(prev_summary_row["success_rate"]) if prev_summary_row["success_rate"] is not None else 0.0
            )
            prev_failed_events = prev_summary_row["failed_events"] or 0
            prev_avg_duration = (
                int(prev_summary_row["avg_processing_time_ms"])
                if prev_summary_row["avg_processing_time_ms"] is not None
                else 0
            )

            summary["total_events_trend"] = calculate_trend(float(total_events), float(prev_total_events))
            summary["success_rate_trend"] = calculate_trend(current_success_rate, prev_success_rate)
            summary["failed_events_trend"] = calculate_trend(float(current_failed_events), float(prev_failed_events))
            summary["avg_duration_trend"] = calculate_trend(float(current_avg_duration), float(prev_avg_duration))
        else:
            # No previous period data - set trends to 0.0
            summary["total_events_trend"] = 0.0
            summary["success_rate_trend"] = 0.0
            summary["failed_events_trend"] = 0.0
            summary["avg_duration_trend"] = 0.0

        # Process top repositories
        top_repositories = [
            {
                "repository": row["repository"],
                "total_events": row["total_events"],
                "percentage": float(row["percentage"]) if row["percentage"] is not None else 0.0,
                "success_rate": float(row["success_rate"]) if row["success_rate"] is not None else 0.0,
            }
            for row in top_repos_rows
        ]

        # Process event type distribution
        event_type_distribution = {row["event_type"]: row["event_count"] for row in event_type_rows}

        # Calculate event rates
        hourly_event_rate = 0.0
        daily_event_rate = 0.0
        if time_range_row and time_range_row["first_event_time"] and time_range_row["last_event_time"]:
            time_diff = time_range_row["last_event_time"] - time_range_row["first_event_time"]
            total_hours = max(time_diff.total_seconds() / 3600, 1)  # Avoid division by zero
            total_days = max(time_diff.total_seconds() / 86400, 1)  # Avoid division by zero
            hourly_event_rate = round(total_events / total_hours, 2)
            daily_event_rate = round(total_events / total_days, 2)

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "summary": summary,
            "top_repositories": top_repositories,
            "event_type_distribution": event_type_distribution,
            "hourly_event_rate": hourly_event_rate,
            "daily_event_rate": daily_event_rate,
        }
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch metrics summary from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics summary",
        ) from ex


@app.get("/api/metrics/contributors", operation_id="get_metrics_contributors")
async def get_metrics_contributors(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    user: str | None = Query(default=None, description="Filter by username"),
    repository: str | None = Query(default=None, description="Filter by repository (org/repo format)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
) -> dict[str, Any]:
    """Get PR contributors statistics (creators, reviewers, approvers, LGTM).

    Analyzes webhook payloads to extract contributor activity including PR creation,
    code review, approval, and LGTM metrics. Essential for understanding team contributions
    and identifying active contributors.

    **Primary Use Cases:**
    - Track who is creating PRs and how many
    - Monitor code review participation
    - Identify approval patterns and bottlenecks
    - Track LGTM activity separate from approvals
    - Measure team collaboration and engagement
    - Generate contributor leaderboards

    **Parameters:**
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `user` (str, optional): Filter by username
    - `repository` (str, optional): Filter by repository (org/repo format)
    - `page` (int, default=1): Page number (1-indexed)
    - `page_size` (int, default=10): Items per page (1-100)

    **Pagination:**
    - Each category (pr_creators, pr_reviewers, pr_approvers, pr_lgtm) includes pagination metadata
    - `total`: Total number of contributors in this category
    - `total_pages`: Total number of pages
    - `has_next`: Whether there's a next page
    - `has_prev`: Whether there's a previous page

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-31T23:59:59Z"
      },
      "pr_creators": {
        "data": [
          {
            "user": "john-doe",
            "total_prs": 45,
            "merged_prs": 42,
            "closed_prs": 3,
            "avg_commits_per_pr": 3.0
          }
        ],
        "pagination": {
          "total": 150,
          "page": 1,
          "page_size": 10,
          "total_pages": 15,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_reviewers": {
        "data": [
          {
            "user": "jane-smith",
            "total_reviews": 78,
            "prs_reviewed": 65,
            "avg_reviews_per_pr": 1.2
          }
        ],
        "pagination": {
          "total": 120,
          "page": 1,
          "page_size": 10,
          "total_pages": 12,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_approvers": {
        "data": [
          {
            "user": "bob-wilson",
            "total_approvals": 56,
            "prs_approved": 54
          }
        ],
        "pagination": {
          "total": 95,
          "page": 1,
          "page_size": 10,
          "total_pages": 10,
          "has_next": true,
          "has_prev": false
        }
      },
      "pr_lgtm": {
        "data": [
          {
            "user": "alice-jones",
            "total_lgtm": 42,
            "prs_lgtm": 40
          }
        ],
        "pagination": {
          "total": 78,
          "page": 1,
          "page_size": 10,
          "total_pages": 8,
          "has_next": true,
          "has_prev": false
        }
      }
    }
    ```

    **Notes:**
    - PR Approvers: Tracks /approve commands (approved-<username> labels)
    - PR LGTM: Tracks /lgtm commands (lgtm-<username> labels)
    - LGTM is separate from approvals in this workflow

    **Errors:**
    - 500: Database connection error or metrics server disabled
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build filter clause with time, user, and repository filters
    time_filter = ""
    params: list[Any] = []
    param_count = 0

    if start_datetime:
        param_count += 1
        time_filter += " AND created_at >= $" + str(param_count)
        params.append(start_datetime)

    if end_datetime:
        param_count += 1
        time_filter += " AND created_at <= $" + str(param_count)
        params.append(end_datetime)

    # Add repository filter if provided
    repository_filter = ""
    if repository:
        param_count += 1
        repository_filter = " AND repository = $" + str(param_count)
        params.append(repository)

    # Build category-specific user filters to align with per-category "user" semantics
    # PR Creators: user = COALESCE(CASE event_type WHEN 'pull_request'/'pull_request_review'/'issue_comment'..., sender)
    # PR Reviewers: user = sender
    # PR Approvers: user = SUBSTRING(payload->'label'->>'name' FROM 10)
    # PR LGTM: user = SUBSTRING(payload->'label'->>'name' FROM 6)
    user_filter_reviewers = ""
    user_filter_approvers = ""
    user_filter_lgtm = ""

    if user:
        param_count += 1
        user_param_idx = param_count
        params.append(user)

        # PR Reviewers: filter on sender (correct as-is)
        user_filter_reviewers = " AND sender = $" + str(user_param_idx)
        # PR Approvers: filter on extracted username from 'approved-<username>' label
        user_filter_approvers = " AND SUBSTRING(payload->'label'->>'name' FROM 10) = $" + str(user_param_idx)
        # PR LGTM: filter on extracted username from 'lgtm-<username>' label
        user_filter_lgtm = " AND SUBSTRING(payload->'label'->>'name' FROM 6) = $" + str(user_param_idx)

    # Calculate offset for pagination
    offset = (page - 1) * page_size
    MAX_OFFSET = 10000  # Prevent expensive deep pagination
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )

    # Add page_size and offset to params
    param_count += 1
    page_size_param = param_count
    param_count += 1
    offset_param = param_count
    params.extend([page_size, offset])

    # Count query for PR Creators
    pr_creators_count_query = (
        """
        WITH pr_creators AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                CASE event_type
                    WHEN 'pull_request' THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'pull_request_review' THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'pull_request_review_comment'
                        THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'issue_comment' THEN COALESCE(
                        payload->'pull_request'->'user'->>'login',
                        payload->'issue'->'user'->>'login'
                    )
                END as pr_creator
            FROM webhooks
            WHERE pr_number IS NOT NULL
              AND event_type IN (
                  'pull_request',
                  'pull_request_review',
                  'pull_request_review_comment',
                  'issue_comment'
              )
              """
        + time_filter
        + repository_filter
        + """
            ORDER BY repository, pr_number, created_at ASC
        )
        SELECT COUNT(DISTINCT pr_creator) as total
        FROM pr_creators
        WHERE pr_creator IS NOT NULL"""
        + (" AND pr_creator = $" + str(user_param_idx) if user else "")
    )

    # Query PR Creators (from any event with pr_number)
    pr_creators_query = (
        """
        WITH pr_creators AS (
            SELECT DISTINCT ON (repository, pr_number)
                repository,
                pr_number,
                CASE event_type
                    WHEN 'pull_request' THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'pull_request_review' THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'pull_request_review_comment'
                        THEN payload->'pull_request'->'user'->>'login'
                    WHEN 'issue_comment' THEN COALESCE(
                        payload->'pull_request'->'user'->>'login',
                        payload->'issue'->'user'->>'login'
                    )
                END as pr_creator
            FROM webhooks
            WHERE pr_number IS NOT NULL
              AND event_type IN (
                  'pull_request',
                  'pull_request_review',
                  'pull_request_review_comment',
                  'issue_comment'
              )
              """
        + time_filter
        + repository_filter
        + """
            ORDER BY repository, pr_number, created_at ASC
        ),
        user_prs AS (
            SELECT
                pc.pr_creator,
                w.pr_number,
                COALESCE((w.payload->'pull_request'->>'commits')::int, 0) as commits,
                (w.payload->'pull_request'->>'merged' = 'true') as is_merged,
                (
                    w.payload->'pull_request'->>'state' = 'closed'
                    AND w.payload->'pull_request'->>'merged' = 'false'
                ) as is_closed
            FROM webhooks w
            INNER JOIN pr_creators pc ON w.repository = pc.repository AND w.pr_number = pc.pr_number
            WHERE w.pr_number IS NOT NULL
              """
        + time_filter
        + repository_filter
        + """
        )
        SELECT
            pr_creator as user,
            COUNT(DISTINCT pr_number) as total_prs,
            COUNT(DISTINCT pr_number) FILTER (WHERE is_merged) as merged_prs,
            COUNT(DISTINCT pr_number) FILTER (WHERE is_closed) as closed_prs,
            ROUND(AVG(max_commits), 1) as avg_commits
        FROM (
            SELECT
                pr_creator,
                pr_number,
                MAX(commits) as max_commits,
                BOOL_OR(is_merged) as is_merged,
                BOOL_OR(is_closed) as is_closed
            FROM user_prs
            WHERE pr_creator IS NOT NULL
            GROUP BY pr_creator, pr_number
        ) pr_stats
        WHERE 1=1"""
        + (" AND pr_creator = $" + str(user_param_idx) if user else "")
        + """
        GROUP BY pr_creator
        ORDER BY total_prs DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
    )

    # Count query for PR Reviewers
    pr_reviewers_count_query = (
        """
        SELECT COUNT(DISTINCT sender) as total
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND action = 'submitted'
          AND sender != payload->'pull_request'->'user'->>'login'
          """
        + time_filter
        + user_filter_reviewers
        + repository_filter
    )

    # Query PR Reviewers (from pull_request_review events)
    pr_reviewers_query = (
        """
        SELECT
            sender as user,
            COUNT(*) as total_reviews,
            COUNT(DISTINCT pr_number) as prs_reviewed
        FROM webhooks
        WHERE event_type = 'pull_request_review'
          AND action = 'submitted'
          AND sender != payload->'pull_request'->'user'->>'login'
          """
        + time_filter
        + user_filter_reviewers
        + repository_filter
        + """
        GROUP BY sender
        ORDER BY total_reviews DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
    )

    # Count query for PR Approvers
    pr_approvers_count_query = (
        """
        SELECT COUNT(DISTINCT SUBSTRING(payload->'label'->>'name' FROM 10)) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND payload->'label'->>'name' LIKE 'approved-%'
          """
        + time_filter
        + user_filter_approvers
        + repository_filter
    )

    # Query PR Approvers (from pull_request labeled events with 'approved-' prefix only)
    # Custom approval workflow: /approve comment triggers 'approved-<username>' label
    # Note: LGTM is separate from approval - tracked separately
    pr_approvers_query = (
        """
        SELECT
            SUBSTRING(payload->'label'->>'name' FROM 10) as user,
            COUNT(*) as total_approvals,
            COUNT(DISTINCT pr_number) as prs_approved
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND payload->'label'->>'name' LIKE 'approved-%'
          """
        + time_filter
        + user_filter_approvers
        + repository_filter
        + """
        GROUP BY SUBSTRING(payload->'label'->>'name' FROM 10)
        ORDER BY total_approvals DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
    )

    # Count query for LGTM
    pr_lgtm_count_query = (
        """
        SELECT COUNT(DISTINCT SUBSTRING(payload->'label'->>'name' FROM 6)) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND payload->'label'->>'name' LIKE 'lgtm-%'
          """
        + time_filter
        + user_filter_lgtm
        + repository_filter
    )

    # Query LGTM (from pull_request labeled events with 'lgtm-' prefix)
    # Custom LGTM workflow: /lgtm comment triggers 'lgtm-<username>' label
    pr_lgtm_query = (
        """
        SELECT
            SUBSTRING(payload->'label'->>'name' FROM 6) as user,
            COUNT(*) as total_lgtm,
            COUNT(DISTINCT pr_number) as prs_lgtm
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND action = 'labeled'
          AND payload->'label'->>'name' LIKE 'lgtm-%'
          """
        + time_filter
        + user_filter_lgtm
        + repository_filter
        + """
        GROUP BY SUBSTRING(payload->'label'->>'name' FROM 6)
        ORDER BY total_lgtm DESC
        LIMIT $"""
        + str(page_size_param)
        + " OFFSET $"
        + str(offset_param)
    )

    try:
        # Execute all count queries in parallel (params without LIMIT/OFFSET)
        params_without_pagination = params[:-2]
        (
            pr_creators_total,
            pr_reviewers_total,
            pr_approvers_total,
            pr_lgtm_total,
        ) = await asyncio.gather(
            db_manager.fetchval(pr_creators_count_query, *params_without_pagination),
            db_manager.fetchval(pr_reviewers_count_query, *params_without_pagination),
            db_manager.fetchval(pr_approvers_count_query, *params_without_pagination),
            db_manager.fetchval(pr_lgtm_count_query, *params_without_pagination),
        )

        # Execute all data queries in parallel for better performance
        pr_creators_rows, pr_reviewers_rows, pr_approvers_rows, pr_lgtm_rows = await asyncio.gather(
            db_manager.fetch(pr_creators_query, *params),
            db_manager.fetch(pr_reviewers_query, *params),
            db_manager.fetch(pr_approvers_query, *params),
            db_manager.fetch(pr_lgtm_query, *params),
        )

        # Format PR creators
        pr_creators = [
            {
                "user": row["user"],
                "total_prs": row["total_prs"],
                "merged_prs": row["merged_prs"] or 0,
                "closed_prs": row["closed_prs"] or 0,
                "avg_commits_per_pr": round(row["avg_commits"] or 0, 1),
            }
            for row in pr_creators_rows
        ]

        # Format PR reviewers
        pr_reviewers = [
            {
                "user": row["user"],
                "total_reviews": row["total_reviews"],
                "prs_reviewed": row["prs_reviewed"],
                "avg_reviews_per_pr": round(row["total_reviews"] / max(row["prs_reviewed"], 1), 2),
            }
            for row in pr_reviewers_rows
        ]

        # Format PR approvers
        pr_approvers = [
            {
                "user": row["user"],
                "total_approvals": row["total_approvals"],
                "prs_approved": row["prs_approved"],
            }
            for row in pr_approvers_rows
        ]

        # Format LGTM
        pr_lgtm = [
            {
                "user": row["user"],
                "total_lgtm": row["total_lgtm"],
                "prs_lgtm": row["prs_lgtm"],
            }
            for row in pr_lgtm_rows
        ]

        # Calculate pagination metadata for each category
        total_pages_creators = math.ceil(pr_creators_total / page_size) if pr_creators_total > 0 else 0
        total_pages_reviewers = math.ceil(pr_reviewers_total / page_size) if pr_reviewers_total > 0 else 0
        total_pages_approvers = math.ceil(pr_approvers_total / page_size) if pr_approvers_total > 0 else 0
        total_pages_lgtm = math.ceil(pr_lgtm_total / page_size) if pr_lgtm_total > 0 else 0

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "pr_creators": {
                "data": pr_creators,
                "pagination": {
                    "total": pr_creators_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_creators,
                    "has_next": page < total_pages_creators,
                    "has_prev": page > 1,
                },
            },
            "pr_reviewers": {
                "data": pr_reviewers,
                "pagination": {
                    "total": pr_reviewers_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_reviewers,
                    "has_next": page < total_pages_reviewers,
                    "has_prev": page > 1,
                },
            },
            "pr_approvers": {
                "data": pr_approvers,
                "pagination": {
                    "total": pr_approvers_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_approvers,
                    "has_next": page < total_pages_approvers,
                    "has_prev": page > 1,
                },
            },
            "pr_lgtm": {
                "data": pr_lgtm,
                "pagination": {
                    "total": pr_lgtm_total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages_lgtm,
                    "has_next": page < total_pages_lgtm,
                    "has_prev": page > 1,
                },
            },
        }
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch contributor metrics from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contributor metrics",
        ) from ex


@app.get("/api/metrics/user-prs", operation_id="get_user_pull_requests")
async def get_user_pull_requests(
    user: str | None = Query(None, description="GitHub username (optional - shows all PRs if not specified)"),
    repository: str | None = Query(None, description="Filter by repository (org/repo)"),
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """Get pull requests with optional user filtering and commit details.

    Retrieves pull requests with pagination. Can show all PRs or filter by user.
    Includes detailed commit information for each PR. Supports filtering by repository
    and time range.

    **Primary Use Cases:**
    - View all PRs across repositories with pagination
    - Filter PRs by specific user to track contributions
    - Analyze commit patterns per PR
    - Monitor PR lifecycle (created, merged, closed)
    - Filter PR activity by repository or time period

    **Parameters:**
    - `user` (str, optional): GitHub username to filter by (shows all PRs if not specified)
    - `repository` (str, optional): Filter by specific repository (format: org/repo)
    - `start_time` (str, optional): Start of time range in ISO 8601 format
    - `end_time` (str, optional): End of time range in ISO 8601 format
    - `page` (int, optional): Page number for pagination (default: 1)
    - `page_size` (int, optional): Items per page, 1-100 (default: 10)

    **Return Structure:**
    ```json
    {
      "data": [
        {
          "number": 123,
          "title": "Add feature X",
          "owner": "username",
          "repository": "org/repo1",
          "state": "closed",
          "merged": true,
          "url": "https://github.com/org/repo1/pull/123",
          "created_at": "2024-11-20T10:00:00Z",
          "updated_at": "2024-11-21T15:30:00Z",
          "commits_count": 5,
          "head_sha": "abc123def456"  # pragma: allowlist secret
        }
      ],
      "pagination": {
        "total": 45,
        "page": 1,
        "page_size": 10,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false
      }
    }
    ```

    **Errors:**
    - 500: Database connection error or metrics server disabled
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    # Parse datetime strings
    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build filter clauses
    filters = []
    params: list[Any] = []
    param_count = 0

    # Add user filter if provided
    if user and user.strip():
        param_count += 1
        user_filter = "(payload->'pull_request'->'user'->>'login' = $" + str(param_count)
        user_filter += " OR sender = $" + str(param_count) + ")"
        filters.append(user_filter)
        params.append(user.strip())

    if start_datetime:
        param_count += 1
        filters.append("created_at >= $" + str(param_count))
        params.append(start_datetime)

    if end_datetime:
        param_count += 1
        filters.append("created_at <= $" + str(param_count))
        params.append(end_datetime)

    if repository:
        param_count += 1
        filters.append("repository = $" + str(param_count))
        params.append(repository)

    where_clause = " AND ".join(filters) if filters else "1=1"

    # Count total matching PRs
    count_query = (
        """
        SELECT COUNT(DISTINCT (payload->'pull_request'->>'number')::int) as total
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND """
        + where_clause
    )

    # Calculate pagination
    offset = (page - 1) * page_size
    MAX_OFFSET = 10000  # Prevent expensive deep pagination
    if offset > MAX_OFFSET:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pagination offset exceeds maximum ({MAX_OFFSET}). Use time filters to narrow results.",
        )
    param_count += 1
    limit_param_idx = param_count
    param_count += 1
    offset_param_idx = param_count

    # Query for PR data with pagination
    data_query = (
        """
        SELECT DISTINCT ON (repository, (payload->'pull_request'->>'number')::int)
            (payload->'pull_request'->>'number')::int as pr_number,
            payload->'pull_request'->>'title' as title,
            payload->'pull_request'->'user'->>'login' as owner,
            repository,
            payload->'pull_request'->>'state' as state,
            (payload->'pull_request'->>'merged')::boolean as merged,
            payload->'pull_request'->>'html_url' as url,
            payload->'pull_request'->>'created_at' as created_at,
            payload->'pull_request'->>'updated_at' as updated_at,
            (payload->'pull_request'->>'commits')::int as commits_count,
            payload->'pull_request'->'head'->>'sha' as head_sha
        FROM webhooks
        WHERE event_type = 'pull_request'
          AND """
        + where_clause
        + """
        ORDER BY repository, (payload->'pull_request'->>'number')::int DESC, created_at DESC
        LIMIT $"""
        + str(limit_param_idx)
        + " OFFSET $"
        + str(offset_param_idx)
    )

    try:
        # Execute count and data queries in parallel
        count_result, pr_rows = await asyncio.gather(
            db_manager.fetchrow(count_query, *params),
            db_manager.fetch(data_query, *params, page_size, offset),
        )

        total = count_result["total"] if count_result else 0
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        # Format PR data
        prs = [
            {
                "number": row["pr_number"],
                "title": row["title"],
                "owner": row["owner"],
                "repository": row["repository"],
                "state": row["state"],
                "merged": row["merged"] or False,
                "url": row["url"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "commits_count": row["commits_count"] or 0,
                "head_sha": row["head_sha"],
            }
            for row in pr_rows
        ]

        return {
            "data": prs,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    except HTTPException:
        raise
    except asyncio.CancelledError:
        LOGGER.debug("User pull requests request was cancelled")
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch user pull requests from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user pull requests",
        ) from ex


@app.get("/api/metrics/trends", operation_id="get_metrics_trends")
async def get_metrics_trends(
    start_time: str | None = Query(
        default=None, description="Start time in ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
    ),
    end_time: str | None = Query(default=None, description="End time in ISO 8601 format (e.g., 2024-01-31T23:59:59Z)"),
    bucket: str = Query(default="hour", pattern="^(hour|day)$", description="Time bucket ('hour', 'day')"),
) -> dict[str, Any]:
    """Get aggregated event trends over time.

    Returns aggregated event counts (total, success, error) grouped by time bucket.
    Essential for visualizing event volume and success rates over time on charts.

    **Parameters:**
    - `start_time`: Start of time range in ISO format.
    - `end_time`: End of time range in ISO format.
    - `bucket`: Time aggregation bucket ('hour' or 'day').

    **Return Structure:**
    ```json
    {
      "time_range": {
        "start_time": "...",
        "end_time": "..."
      },
      "trends": [
        {
          "bucket": "2024-01-15T14:00:00Z",
          "total_events": 120,
          "successful_events": 115,
          "failed_events": 5
        },
        ...
      ]
    }
    ```
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    where_clause = "WHERE 1=1"
    params: list[Any] = []
    param_idx = 1

    if start_datetime:
        where_clause += " AND created_at >= $" + str(param_idx)
        params.append(start_datetime)
        param_idx += 1

    if end_datetime:
        where_clause += " AND created_at <= $" + str(param_idx)
        params.append(end_datetime)
        param_idx += 1

    # Add bucket parameter
    params.append(bucket)
    bucket_param_idx = param_idx

    query = (
        """
        SELECT
            date_trunc($"""
        + str(bucket_param_idx)
        + """, created_at) as bucket,
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'success') as successful_events,
            COUNT(*) FILTER (WHERE status IN ('error', 'partial')) as failed_events
        FROM webhooks
        """
        + where_clause
        + """
        GROUP BY bucket
        ORDER BY bucket
    """
    )

    try:
        rows = await db_manager.fetch(query, *params)

        trends = [
            {
                "bucket": row["bucket"].isoformat() if row["bucket"] else None,
                "total_events": row["total_events"],
                "successful_events": row["successful_events"],
                "failed_events": row["failed_events"],
            }
            for row in rows
        ]

        return {
            "time_range": {
                "start_time": start_datetime.isoformat() if start_datetime else None,
                "end_time": end_datetime.isoformat() if end_datetime else None,
            },
            "trends": trends,
        }
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch metrics trends from database")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch metrics trends",
        ) from ex


@app.get("/api/metrics/pr-story/{repository:path}/{pr_number}", operation_id="get_pr_story")
async def get_pr_story_endpoint(
    repository: str,
    pr_number: int,
) -> dict[str, Any]:
    """Get complete PR story timeline with all events.

    Aggregates all webhook events for a PR into a comprehensive timeline showing
    the complete story from creation to current state or merge/close.

    **Primary Use Cases:**
    - Visualize complete PR lifecycle and history
    - Track when specific events occurred (reviews, approvals, check runs)
    - Debug CI/CD issues by seeing check run history
    - Understand PR review and approval flow
    - Monitor time from creation to merge

    **Parameters:**
    - `repository` (str): Repository in org/repo format (e.g., "myorg/myrepo")
    - `pr_number` (int): Pull request number within the repository

    **Return Structure:**
    See the complete response structure in the module docstring.

    **Events Included:**
    - PR lifecycle (opened, closed, merged, reopened)
    - Code changes (commits/synchronize events)
    - Reviews (approved, changes requested, comments)
    - Labels (added, removed, verified, approved, lgtm)
    - Check runs (CI/CD pipeline status - matched via head_sha)
    - Comments and review requests

    **Event Grouping:**
    - Events within 60 seconds are grouped as parallel
    - Multiple same-type events are collapsed (e.g., "15 check runs")

    **Check Run Matching:**
    Since check_run webhooks don't include PR number, they are matched via
    the PR's head_sha. This ensures all CI/CD events are included.

    **Errors:**
    - 404: PR not found (no webhooks exist for this PR)
    - 500: Database connection error
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    if pr_number <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="PR number must be positive",
        )

    try:
        story = await get_pr_story(db_manager, repository, pr_number)
        if story is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"PR #{pr_number} not found in {repository}",
            )
        return story
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception(f"Failed to fetch PR story for {repository} #{pr_number}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch PR story",
        ) from ex


# MCP Integration - Setup AFTER all routes are registered
# Note: We use manual HTTP transport setup because fastapi-mcp 0.4.0's mount_http()
# doesn't support stateless mode configuration, which is required for our use case
#
# STARTUP-ONLY CONFIGURATION:
# - METRICS_MCP_ENABLED is evaluated at import time (module load)
# - This is a startup-only switch - changing the environment variable at runtime has NO effect
# - The application process MUST be restarted for METRICS_MCP_ENABLED changes to take effect
# - This block executes during module import, creating routes and handlers immediately
#
# FUTURE CONSIDERATION:
# - If dynamic enable/disable of MCP is ever required, this block should be:
#   1. Moved into the lifespan context manager, OR
#   2. Wrapped in a factory function called conditionally at startup
# - Current design prioritizes simplicity: MCP is either on or off at startup
_mcp_config = get_config()
if _mcp_config.mcp.enabled:
    # Create MCP instance with the main app
    mcp_instance = FastApiMCP(app, exclude_tags=["mcp_exclude"])

    # Create HTTP transport manually to enable stateless mode
    http_transport = FastApiHttpSessionManager(
        mcp_server=mcp_instance.server,
        event_store=None,  # No event store needed for stateless mode
        json_response=True,
    )
    # Clear session manager so lifespan can create it with stateless=True
    http_transport._session_manager = None

    # Register the HTTP endpoint manually (OPTIONS needed for CORS preflight)
    @app.api_route(
        "/mcp", methods=["GET", "POST", "DELETE", "OPTIONS"], include_in_schema=False, operation_id="mcp_http"
    )
    async def handle_mcp_streamable_http(request: Request) -> Response:
        """Handle MCP HTTP requests via stateless transport."""
        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization",
                },
            )

        if http_transport is None or http_transport._session_manager is None:
            LOGGER.error("MCP session manager not initialized")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MCP server not initialized",
            )
        return await http_transport.handle_fastapi_request(request)

    LOGGER.info("MCP server mounted at /mcp (stateless mode)")
