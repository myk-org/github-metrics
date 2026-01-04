"""Shared response formatting utilities for API endpoints.

Provides consistent response structures across all API routes.
"""

from typing import Any, TypedDict

from backend.utils.query_builders import calculate_total_pages


class PaginationMetadata(TypedDict):
    """Pagination metadata structure."""

    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


def format_pagination_metadata(
    total: int,
    page: int,
    page_size: int,
) -> PaginationMetadata:
    """Format pagination metadata for API responses.

    Args:
        total: Total number of items
        page: Current page (1-based)
        page_size: Items per page

    Returns:
        Dictionary with pagination metadata:
        {
            "total": 100,
            "page": 1,
            "page_size": 10,
            "total_pages": 10,
            "has_next": True,
            "has_prev": False
        }

    Raises:
        ValueError: If page_size <= 0 or page < 1
    """
    # Validate page_size to prevent ZeroDivisionError
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    # Validate page to be 1-based
    if page < 1:
        raise ValueError("page must be at least 1")

    total_pages = calculate_total_pages(total, page_size)

    # Ensure page doesn't exceed total_pages (clamp to valid range)
    # Note: We clamp instead of raising to handle edge cases where
    # data was deleted between count query and data fetch
    clamped_page = min(page, max(total_pages, 1))

    return {
        "total": total,
        "page": clamped_page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": clamped_page < total_pages,
        "has_prev": clamped_page > 1,
    }


def format_paginated_response(
    data: list[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Format a standard paginated API response.

    Args:
        data: List of items for current page
        total: Total number of items
        page: Current page
        page_size: Items per page

    Returns:
        Dictionary with data and pagination:
        {
            "data": [...],
            "pagination": {...}
        }
    """
    return {
        "data": data,
        "pagination": format_pagination_metadata(total, page, page_size),
    }
