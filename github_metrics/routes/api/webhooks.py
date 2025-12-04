"""API routes for webhook events."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string
from github_metrics.utils.query_builders import QueryParams, build_pagination_sql, build_time_filter
from github_metrics.utils.response_formatters import format_paginated_response

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.webhooks")

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
    page_size: int = Query(default=100, ge=1, description="Items per page"),
) -> dict[str, Any]:
    """Retrieve webhook events with filtering and pagination."""
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    start_datetime = parse_datetime_string(start_time, "start_time")
    end_datetime = parse_datetime_string(end_time, "end_time")

    # Build query with QueryParams
    params = QueryParams()

    query = """
        SELECT
            delivery_id, repository, event_type, action, pr_number, sender,
            status, created_at, processed_at, duration_ms,
            api_calls_count, token_spend, token_remaining, error_message
        FROM webhooks WHERE 1=1
    """

    if repository:
        query += f" AND repository = {params.add(repository)}"

    if event_type:
        query += f" AND event_type = {params.add(event_type)}"

    if status:
        query += f" AND status = {params.add(status)}"

    # Add time filters
    query += build_time_filter(params, start_datetime, end_datetime)

    # Build count query before adding pagination
    count_query = "SELECT COUNT(*) FROM (" + query + ") AS filtered"
    # Capture params snapshot before adding pagination (for count query)
    count_params = params.get_params()

    # Add pagination to main query (modifies params)
    pagination_sql = build_pagination_sql(params, page, page_size)
    query += " ORDER BY created_at DESC " + pagination_sql

    try:
        # Get all params for data query (includes pagination)
        all_params = params.get_params()

        total_count = await db_manager.fetchval(count_query, *count_params)
        rows = await db_manager.fetch(query, *all_params)

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

        return format_paginated_response(events, total_count, page, page_size)
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
