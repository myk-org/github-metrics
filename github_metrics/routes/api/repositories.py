"""API routes for repository statistics."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager
from github_metrics.utils.datetime_utils import parse_datetime_string

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.api.repositories")

# Maximum pagination offset to prevent expensive deep queries
MAX_OFFSET = 10000

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/repositories", operation_id="get_repository_statistics")
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

    try:
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
