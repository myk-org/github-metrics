"""Shared query builder utilities for API endpoints.

This module provides a unified interface for building SQL query components:
- Time range filtering
- Pagination
- Repository filtering
- Parameter index tracking

All API routes should use these utilities to ensure consistency.
"""

from dataclasses import dataclass, field
from datetime import datetime

# Allowed parameter types for SQL query parameters
ParamValue = str | int | float | datetime | list[str] | None

# Allowed column names for time filtering (prevents SQL injection)
ALLOWED_TIME_COLUMNS = frozenset({"created_at", "updated_at", "pushed_at"})

# Allowed column names for repository filtering (prevents SQL injection)
ALLOWED_REPOSITORY_COLUMNS = frozenset({"repository"})


@dataclass
class QueryParams:
    """Tracks query parameters and their indices for SQL parameterization.

    Usage:
        params = QueryParams()

        # Add a time filter
        time_filter = build_time_filter(params, start_dt, end_dt)

        # Add pagination
        pagination_sql = build_pagination_sql(params, page, page_size)

        # Get all params for query execution
        query_params = params.get_params()

        # Get params excluding pagination (for count queries)
        count_params = params.get_params_excluding_pagination()
    """

    _params: list[ParamValue] = field(default_factory=list)
    _count: int = 0
    _pagination_start_index: int | None = None

    def next_index(self) -> int:
        """Get next parameter index (1-based for PostgreSQL)."""
        self._count += 1
        return self._count

    def add(self, value: ParamValue) -> str:
        """Add a parameter and return its placeholder.

        Args:
            value: Parameter value (str, int, float, datetime, list[str], or None)

        Returns:
            PostgreSQL parameter placeholder (e.g., "$1", "$2")
        """
        idx = self.next_index()
        self._params.append(value)
        return f"${idx}"

    def mark_pagination_start(self) -> None:
        """Mark the current position as the start of pagination parameters.

        This should be called by build_pagination_sql() before adding
        pagination parameters (LIMIT/OFFSET).
        """
        self._pagination_start_index = len(self._params)

    def get_params(self) -> list[ParamValue]:
        """Get all parameters for query execution.

        Returns a defensive copy to prevent accidental mutation
        of internal state after retrieval.
        """
        return self._params.copy()

    def get_params_excluding_pagination(self) -> list[ParamValue]:
        """Get parameters excluding pagination (LIMIT/OFFSET).

        Returns all parameters added before mark_pagination_start() was called.
        If mark_pagination_start() was never called, returns all parameters.

        This is useful for count queries that need the same filters but no pagination.
        """
        if self._pagination_start_index is None:
            return self._params.copy()
        return self._params[: self._pagination_start_index].copy()

    def get_count(self) -> int:
        """Get current parameter count."""
        return self._count

    def clone(self) -> "QueryParams":
        """Create a copy of this QueryParams with same parameters and count.

        Returns:
            New QueryParams instance with copied parameters and count.
        """
        new_params = QueryParams()
        new_params._params = self._params.copy()
        new_params._count = self._count
        new_params._pagination_start_index = self._pagination_start_index
        return new_params


def build_time_filter(
    params: QueryParams,
    start_time: datetime | None,
    end_time: datetime | None,
    column: str = "created_at",
) -> str:
    """Build time range filter SQL.

    Args:
        params: QueryParams tracker to add parameters to
        start_time: Start of time range (inclusive)
        end_time: End of time range (inclusive)
        column: Column name to filter on (default: created_at)

    Returns:
        SQL WHERE clause fragment (e.g., " AND created_at >= $1 AND created_at <= $2")
        Returns empty string if both times are None

    Raises:
        ValueError: If column name is not in the allowed list (SQL injection prevention)
    """
    # Validate column name to prevent SQL injection
    if column not in ALLOWED_TIME_COLUMNS:
        raise ValueError(f"Invalid column name '{column}'. Allowed columns: {', '.join(sorted(ALLOWED_TIME_COLUMNS))}")

    filter_parts = []

    if start_time:
        placeholder = params.add(start_time)
        filter_parts.append(f"{column} >= {placeholder}")

    if end_time:
        placeholder = params.add(end_time)
        filter_parts.append(f"{column} <= {placeholder}")

    if not filter_parts:
        return ""

    return " AND " + " AND ".join(filter_parts)


def build_repository_filter(
    params: QueryParams,
    repositories: str | list[str] | None,
    column: str = "repository",
) -> str:
    """Build repository filter SQL.

    Supports both single repository (string) and multiple repositories (list).
    For backward compatibility, accepts both formats.

    Args:
        params: QueryParams tracker
        repositories: Repository name(s) to filter (org/repo format)
                     Can be a single string or list of strings
        column: Column name (default: repository)

    Returns:
        SQL WHERE clause fragment or empty string
        - Single repository: " AND repository = $1"
        - Multiple repositories: " AND repository = ANY($1)"

    Raises:
        ValueError: If column name is not in the allowed list (SQL injection prevention)
    """
    # Validate column name to prevent SQL injection
    if column not in ALLOWED_REPOSITORY_COLUMNS:
        raise ValueError(
            f"Invalid column name '{column}'. Allowed columns: {', '.join(sorted(ALLOWED_REPOSITORY_COLUMNS))}"
        )

    if not repositories:
        return ""

    # Convert single string to list for uniform handling
    if isinstance(repositories, str):
        repositories = [repositories]

    # Use PostgreSQL's ANY operator for array matching
    placeholder = params.add(repositories)
    return f" AND {column} = ANY({placeholder})"


def build_pagination_sql(
    params: QueryParams,
    page: int,
    page_size: int,
) -> str:
    """Build pagination SQL (LIMIT/OFFSET).

    Args:
        params: QueryParams tracker
        page: Page number (1-based)
        page_size: Items per page

    Returns:
        SQL fragment like "LIMIT $3 OFFSET $4"
    """
    params.mark_pagination_start()
    offset = (page - 1) * page_size
    limit_placeholder = params.add(page_size)
    offset_placeholder = params.add(offset)
    return f"LIMIT {limit_placeholder} OFFSET {offset_placeholder}"


def calculate_total_pages(total: int, page_size: int) -> int:
    """Calculate total pages from total items and page size."""
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size
