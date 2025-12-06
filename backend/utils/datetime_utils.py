"""Datetime parsing utilities for API endpoints."""

from datetime import datetime

from fastapi import HTTPException
from fastapi import status as http_status


def parse_datetime_string(value: str | None, param_name: str) -> datetime | None:
    """Parse ISO 8601 datetime string to datetime object.

    Args:
        value: ISO 8601 datetime string (e.g., "2024-01-15T00:00:00Z") or None
        param_name: Parameter name for error messages

    Returns:
        Parsed datetime object or None if value is None

    Raises:
        HTTPException: If datetime format is invalid (400 Bad Request)
    """
    if value is None:
        return None
    try:
        # Handle both 'Z' suffix and '+00:00' timezone
        normalized = value
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    except ValueError as ex:
        detail = f"Invalid datetime format for {param_name}: {value}. Use ISO 8601 format (e.g., 2024-01-15T00:00:00Z)"
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from ex
