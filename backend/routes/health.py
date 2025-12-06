"""Health check and utility routes."""

import base64
from typing import Any

from fastapi import APIRouter, Response

from backend.database import DatabaseManager

router = APIRouter()

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None

# Favicon bytes (1x1 transparent PNG)
FAVICON_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@router.get("/health", operation_id="health_check")
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


@router.get("/favicon.ico", include_in_schema=False, tags=["mcp_exclude"])
async def favicon() -> Response:
    """Serve favicon.ico."""
    return Response(content=FAVICON_BYTES, media_type="image/png")
