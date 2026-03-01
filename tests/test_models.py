"""Tests for the Webhook SQLAlchemy model.

Tests model definitions including:
- Table arguments and index definitions
"""

from sqlalchemy import Index

from backend.models import Webhook

INDEX_NAME = "ix_webhooks_repo_pr_number_created_at"


class TestWebhookCompositeIndex:
    """Tests for the composite index on the Webhook model."""

    @staticmethod
    def _find_index(name: str) -> Index:
        for arg in Webhook.__table_args__:
            if isinstance(arg, Index) and arg.name == name:
                return arg
        raise AssertionError(f"Index {name!r} not found")

    def test_table_args_contains_composite_index(self) -> None:
        """Test that Webhook.__table_args__ includes the composite index."""
        index_names = [arg.name for arg in Webhook.__table_args__ if isinstance(arg, Index)]
        assert INDEX_NAME in index_names

    def test_composite_index_columns(self) -> None:
        """Test that the composite index covers repository, pr_number, and created_at."""
        target_index = self._find_index(INDEX_NAME)

        column_names = [col.name for col in target_index.columns]
        assert column_names == ["repository", "pr_number", "created_at"]

    def test_composite_index_has_partial_where_clause(self) -> None:
        """Test that the composite index has a WHERE pr_number IS NOT NULL clause."""
        target_index = self._find_index(INDEX_NAME)

        dialect_options = target_index.dialect_options.get("postgresql", {})
        where_clause = dialect_options.get("where")
        assert where_clause is not None, "Index missing postgresql_where clause"
        assert "pr_number IS NOT NULL" in str(where_clause.text)

    def test_all_composite_index_names(self) -> None:
        """Test all composite index names in Webhook.__table_args__."""
        expected_names = {
            "ix_webhooks_repository_created_at",
            "ix_webhooks_repository_event_type",
            INDEX_NAME,
        }
        actual_names = {arg.name for arg in Webhook.__table_args__ if isinstance(arg, Index)}
        assert actual_names == expected_names
