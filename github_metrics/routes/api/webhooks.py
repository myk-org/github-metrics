"""API routes for webhook events."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.webhooks")

# Maximum pagination offset to prevent expensive deep queries
MAX_OFFSET = 10000

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/webhooks", operation_id="get_webhook_events")
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
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch webhook events")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch webhook events",
        ) from ex


@router.get("/webhooks/{delivery_id}", operation_id="get_webhook_event_by_id")
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
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch webhook event", extra={"delivery_id": delivery_id})
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch webhook event",
        ) from ex
