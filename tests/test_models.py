"""Tests for SQLAlchemy models and Alembic migrations.

Tests model definitions including:
- Table arguments and index definitions
- Migration revision chain integrity
- Migration upgrade/downgrade operations
"""

import importlib
import types
from unittest.mock import MagicMock, patch

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
        raise AssertionError(f"Index {name} not found in __table_args__")

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

    def test_webhook_has_three_composite_indexes(self) -> None:
        """Test that Webhook.__table_args__ has exactly three composite indexes."""
        indexes = [arg for arg in Webhook.__table_args__ if isinstance(arg, Index)]
        assert len(indexes) == 3

    def test_all_composite_index_names(self) -> None:
        """Test all composite index names in Webhook.__table_args__."""
        expected_names = {
            "ix_webhooks_repository_created_at",
            "ix_webhooks_repository_event_type",
            INDEX_NAME,
        }
        actual_names = {arg.name for arg in Webhook.__table_args__ if isinstance(arg, Index)}
        assert actual_names == expected_names


class TestPrCreatorsIndexMigration:
    """Tests for the 20260219_0001_add_pr_creators_index migration."""

    @staticmethod
    def _load_migration() -> types.ModuleType:
        """Load the migration module."""
        return importlib.import_module("backend.migrations.versions.20260219_0001_add_pr_creators_index")

    def test_revision_id(self) -> None:
        """Test that the migration has the expected revision ID."""
        migration = self._load_migration()
        assert migration.revision == "f5g6h7i8j9k0"

    def test_down_revision_matches_previous_migration(self) -> None:
        """Test that down_revision points to the previous migration."""
        migration = self._load_migration()
        assert migration.down_revision == "e4f5g6h7i8j9"

    def test_revision_chain_links_to_remove_cross_team_columns(self) -> None:
        """Test that the migration chains after the remove_cross_team_columns migration."""
        previous_migration = importlib.import_module(
            "backend.migrations.versions.20251210_0001_remove_cross_team_columns"
        )
        current_migration = self._load_migration()
        assert current_migration.down_revision == previous_migration.revision

    def test_branch_labels_is_none(self) -> None:
        """Test that branch_labels is None (linear migration chain)."""
        migration = self._load_migration()
        assert migration.branch_labels is None

    def test_depends_on_is_none(self) -> None:
        """Test that depends_on is None (no cross-branch dependencies)."""
        migration = self._load_migration()
        assert migration.depends_on is None

    def test_upgrade_creates_correct_index(self) -> None:
        """Test that upgrade creates the ix_webhooks_repo_pr_number_created_at index."""
        migration = self._load_migration()

        mock_bind = MagicMock()

        with patch.object(migration.op, "get_bind", return_value=mock_bind):
            migration.upgrade()

        mock_bind.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")
        executed_sql = mock_bind.execute.call_args[0][0]
        sql_text = str(executed_sql.text).strip()
        assert INDEX_NAME in sql_text
        assert "CONCURRENTLY" in sql_text
        assert "IF NOT EXISTS" in sql_text
        assert "pr_number IS NOT NULL" in sql_text

    def test_upgrade_targets_webhooks_table(self) -> None:
        """Test that upgrade creates the index on the webhooks table."""
        migration = self._load_migration()

        mock_bind = MagicMock()

        with patch.object(migration.op, "get_bind", return_value=mock_bind):
            migration.upgrade()

        executed_sql = str(mock_bind.execute.call_args[0][0].text).strip()
        assert "ON webhooks" in executed_sql

    def test_upgrade_index_column_order(self) -> None:
        """Test that the upgrade SQL specifies columns in the correct order."""
        migration = self._load_migration()

        mock_bind = MagicMock()

        with patch.object(migration.op, "get_bind", return_value=mock_bind):
            migration.upgrade()

        executed_sql = str(mock_bind.execute.call_args[0][0].text).strip()
        assert "repository, pr_number, created_at ASC" in executed_sql

    def test_downgrade_drops_correct_index(self) -> None:
        """Test that downgrade drops the ix_webhooks_repo_pr_number_created_at index."""
        migration = self._load_migration()

        mock_bind = MagicMock()

        with patch.object(migration.op, "get_bind", return_value=mock_bind):
            migration.downgrade()

        mock_bind.execution_options.assert_called_once_with(isolation_level="AUTOCOMMIT")
        executed_sql = str(mock_bind.execute.call_args[0][0].text).strip()
        assert "DROP INDEX CONCURRENTLY" in executed_sql
        assert INDEX_NAME in executed_sql
