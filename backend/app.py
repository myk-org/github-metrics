"""
FastAPI application for GitHub Metrics service.

Standalone metrics server for webhook event tracking and visualization.
All endpoints are async for optimal performance.
"""

import asyncio
import ipaddress
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi import status as http_status
from fastapi_mcp import FastApiMCP
from fastapi_mcp.transport.http import FastApiHttpSessionManager
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from simple_logger.logger import get_logger
from starlette.responses import FileResponse

from backend.config import get_config
from backend.database import DatabaseManager, get_database_manager
from backend.metrics_tracker import MetricsTracker
from backend.routes import health, webhooks
from backend.routes.api import (
    comment_resolution,
    contributors,
    cross_team,
    maintainers,
    pr_story,
    repositories,
    summary,
    team_dynamics,
    trends,
    turnaround,
    user_prs,
)
from backend.routes.api import webhooks as api_webhooks
from backend.sig_teams import SigTeamsConfig, get_sig_teams_config
from backend.utils.security import (
    get_cloudflare_allowlist,
    get_github_allowlist,
)


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
LOGGER = get_logger(name="backend.app")

# Global instances (initialized in lifespan)
db_manager: DatabaseManager | None = None
metrics_tracker: MetricsTracker | None = None
http_client: httpx.AsyncClient | None = None
allowed_ips: tuple[IPNetwork, ...] = ()

# MCP Globals - typed as concrete classes where possible
# Note: Using library types directly; http_transport requires manual setup for stateless mode
http_transport: FastApiHttpSessionManager | None = None
mcp_instance: FastApiMCP | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - manage database connections and IP allowlists."""
    global db_manager, metrics_tracker, http_client, allowed_ips

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
            LOGGER.info("Loaded %d GitHub IP ranges", len(github_ips))
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
            LOGGER.info("Loaded %d Cloudflare IP ranges", len(cloudflare_ips))
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
    metrics_logger = get_logger(name="backend.tracker")
    metrics_tracker = MetricsTracker(db_manager, metrics_logger)
    LOGGER.info("Metrics tracker initialized")

    # Initialize SIG teams config if configured
    sig_teams_config: SigTeamsConfig | None = None
    if config.sig_teams_config_path:
        if config.sig_teams_config_path.exists():
            sig_teams_config = get_sig_teams_config()
            sig_teams_config.load_from_file(config.sig_teams_config_path)
            LOGGER.info("Loaded SIG teams config from %s", config.sig_teams_config_path)
        else:
            LOGGER.warning(
                "SIG teams config file not found: %s, cross-team tracking disabled", config.sig_teams_config_path
            )

    # Set module-level variables for route modules
    # Set database manager for all API routes
    health.db_manager = db_manager
    api_webhooks.db_manager = db_manager
    repositories.db_manager = db_manager
    summary.db_manager = db_manager
    contributors.db_manager = db_manager
    user_prs.db_manager = db_manager
    trends.db_manager = db_manager
    pr_story.db_manager = db_manager
    turnaround.db_manager = db_manager
    team_dynamics.db_manager = db_manager
    cross_team.db_manager = db_manager
    comment_resolution.db_manager = db_manager

    # Set webhook-specific globals
    webhooks.metrics_tracker = metrics_tracker
    webhooks.allowed_ips = allowed_ips
    cross_team.sig_teams_config = sig_teams_config
    contributors.sig_teams_config = sig_teams_config

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

    # Include route modules
    app.include_router(health.router)
    app.include_router(webhooks.router)
    app.include_router(api_webhooks.router)
    app.include_router(repositories.router)
    app.include_router(summary.router)
    app.include_router(contributors.router)
    app.include_router(user_prs.router)
    app.include_router(trends.router)
    app.include_router(pr_story.router)
    app.include_router(turnaround.router)
    app.include_router(team_dynamics.router)
    app.include_router(cross_team.router)
    app.include_router(maintainers.router)
    app.include_router(comment_resolution.router)

    return app


# Create the app
app = create_app()

# Allow tests to patch these via backend.app.*
__all__ = [
    "allowed_ips",
    "app",
    "create_app",
    "db_manager",
    "metrics_tracker",
]


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


# Serve React frontend static files in production
# Only mount if static directory exists (built frontend in container)
_static_path = Path(__file__).parent.parent / "static"
if _static_path.exists() and _static_path.is_dir():
    _index_path = _static_path / "index.html"

    # Catch-all route for SPA - must be registered BEFORE static mount
    # This handles client-side routes like /contributors, /team-dynamics, etc.
    # API routes are already registered above, so they take precedence
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve index.html for all non-API routes (SPA routing).

        Args:
            full_path: The requested path (e.g., 'contributors', 'team-dynamics', 'assets/main.js')

        Returns:
            FileResponse: Either the requested static file or index.html for React Router
        """
        # Check if it's a static file request (has file extension in last path segment)
        path_parts = full_path.split("/")
        if path_parts and "." in path_parts[-1]:
            # Try to serve as static file
            file_path = _static_path / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
        # For all other routes (no extension or file not found), serve index.html
        # React Router will handle the routing client-side
        return FileResponse(_index_path)

    LOGGER.info("Static files and SPA routing configured from %s", _static_path)
