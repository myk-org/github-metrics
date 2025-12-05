"""Tests for response_formatters module."""

import pytest

from backend.utils.response_formatters import (
    format_paginated_response,
    format_pagination_metadata,
)


class TestFormatPaginationMetadata:
    """Tests for format_pagination_metadata function."""

    def test_format_pagination_metadata_first_page(self) -> None:
        """Test pagination metadata for first page."""
        result = format_pagination_metadata(total=100, page=1, page_size=10)

        assert result == {
            "total": 100,
            "page": 1,
            "page_size": 10,
            "total_pages": 10,
            "has_next": True,
            "has_prev": False,
        }

    def test_format_pagination_metadata_middle_page(self) -> None:
        """Test pagination metadata for middle page."""
        result = format_pagination_metadata(total=100, page=5, page_size=10)

        assert result == {
            "total": 100,
            "page": 5,
            "page_size": 10,
            "total_pages": 10,
            "has_next": True,
            "has_prev": True,
        }

    def test_format_pagination_metadata_last_page(self) -> None:
        """Test pagination metadata for last page."""
        result = format_pagination_metadata(total=100, page=10, page_size=10)

        assert result == {
            "total": 100,
            "page": 10,
            "page_size": 10,
            "total_pages": 10,
            "has_next": False,
            "has_prev": True,
        }

    def test_format_pagination_metadata_single_page(self) -> None:
        """Test pagination metadata when all items fit on one page."""
        result = format_pagination_metadata(total=5, page=1, page_size=10)

        assert result == {
            "total": 5,
            "page": 1,
            "page_size": 10,
            "total_pages": 1,
            "has_next": False,
            "has_prev": False,
        }

    def test_format_pagination_metadata_empty_results(self) -> None:
        """Test pagination metadata with no results."""
        result = format_pagination_metadata(total=0, page=1, page_size=10)

        assert result == {
            "total": 0,
            "page": 1,
            "page_size": 10,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False,
        }

    def test_format_pagination_metadata_negative_total(self) -> None:
        """Test pagination metadata with negative total (edge case).

        Negative total is passed through unchanged, but navigation metadata
        (total_pages, has_next, has_prev) is normalized to prevent invalid navigation.
        """
        result = format_pagination_metadata(total=-5, page=1, page_size=10)

        # Negative total is passed through, but navigation metadata is normalized
        assert result == {
            "total": -5,
            "page": 1,
            "page_size": 10,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False,
        }

    def test_format_pagination_metadata_partial_last_page(self) -> None:
        """Test pagination metadata when last page is partial."""
        result = format_pagination_metadata(total=95, page=10, page_size=10)

        assert result == {
            "total": 95,
            "page": 10,
            "page_size": 10,
            "total_pages": 10,
            "has_next": False,
            "has_prev": True,
        }

    def test_format_pagination_metadata_page_exceeds_total_pages(self) -> None:
        """Test pagination metadata when page exceeds total_pages (edge case)."""
        # This can happen if data is deleted between count and fetch
        result = format_pagination_metadata(total=10, page=5, page_size=10)

        # Should clamp to valid page (1 since total_pages=1)
        assert result == {
            "total": 10,
            "page": 1,
            "page_size": 10,
            "total_pages": 1,
            "has_next": False,
            "has_prev": False,
        }

    def test_format_pagination_metadata_zero_page_size_raises_error(self) -> None:
        """Test that page_size of 0 raises ValueError."""
        with pytest.raises(ValueError, match="page_size must be positive"):
            format_pagination_metadata(total=100, page=1, page_size=0)

    def test_format_pagination_metadata_negative_page_size_raises_error(self) -> None:
        """Test that negative page_size raises ValueError."""
        with pytest.raises(ValueError, match="page_size must be positive"):
            format_pagination_metadata(total=100, page=1, page_size=-10)

    def test_format_pagination_metadata_zero_page_raises_error(self) -> None:
        """Test that page of 0 raises ValueError."""
        with pytest.raises(ValueError, match="page must be at least 1"):
            format_pagination_metadata(total=100, page=0, page_size=10)

    def test_format_pagination_metadata_negative_page_raises_error(self) -> None:
        """Test that negative page raises ValueError."""
        with pytest.raises(ValueError, match="page must be at least 1"):
            format_pagination_metadata(total=100, page=-5, page_size=10)


class TestFormatPaginatedResponse:
    """Tests for format_paginated_response function."""

    def test_format_paginated_response_with_data(self) -> None:
        """Test formatting paginated response with data."""
        data = [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]
        result = format_paginated_response(
            data=data,
            total=100,
            page=1,
            page_size=10,
        )

        assert result == {
            "data": data,
            "pagination": {
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "has_next": True,
                "has_prev": False,
            },
        }

    def test_format_paginated_response_empty_data(self) -> None:
        """Test formatting paginated response with empty data."""
        result = format_paginated_response(
            data=[],
            total=0,
            page=1,
            page_size=10,
        )

        assert result == {
            "data": [],
            "pagination": {
                "total": 0,
                "page": 1,
                "page_size": 10,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            },
        }

    def test_format_paginated_response_last_page(self) -> None:
        """Test formatting paginated response for last page."""
        data = [{"id": 10, "name": "item10"}]
        result = format_paginated_response(
            data=data,
            total=10,
            page=10,
            page_size=1,
        )

        assert result == {
            "data": data,
            "pagination": {
                "total": 10,
                "page": 10,
                "page_size": 1,
                "total_pages": 10,
                "has_next": False,
                "has_prev": True,
            },
        }

    def test_format_paginated_response_invalid_page_size(self) -> None:
        """Test that invalid page_size in format_paginated_response raises error."""
        with pytest.raises(ValueError, match="page_size must be positive"):
            format_paginated_response(
                data=[],
                total=100,
                page=1,
                page_size=0,
            )

    def test_format_paginated_response_invalid_page(self) -> None:
        """Test that invalid page in format_paginated_response raises error."""
        with pytest.raises(ValueError, match="page must be at least 1"):
            format_paginated_response(
                data=[],
                total=100,
                page=0,
                page_size=10,
            )
