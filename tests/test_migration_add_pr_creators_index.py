"""Tests for the 20260219_0001_add_pr_creators_index migration.

Tests migration revision chain integrity and upgrade/downgrade operations
for the pr_creators DISTINCT ON composite index.
"""

import importlib
import types
from typing import Literal
from unittest.mock import MagicMock, patch

INDEX_NAME = "ix_webhooks_repo_pr_number_created_at"


class TestPrCreatorsIndexMigration:
    """Tests for the 20260219_0001_add_pr_creators_index migration."""

    @staticmethod
    def _load_migration() -> types.ModuleType:
        """Load the migration module."""
        return importlib.import_module("backend.migrations.versions.20260219_0001_add_pr_creators_index")

    def _run_migration_and_get_sql(
        self, action: Literal["upgrade", "downgrade"], expected_call_count: int, sql_index: int
    ) -> str:
        """Run a migration action and return the DDL SQL string.

        Args:
            action: Migration action to run ("upgrade" or "downgrade").
            expected_call_count: Expected number of execute calls.
            sql_index: Index of the DDL SQL call in the call args list.

        Returns:
            The DDL SQL string at the specified index.
        """
        migration = self._load_migration()
        mock_bind = MagicMock()

        with patch("alembic.op.get_bind", return_value=mock_bind):
            getattr(migration, action)()

        assert mock_bind.execute.call_count == expected_call_count
        commit_sql = str(mock_bind.execute.call_args_list[0][0][0].text).strip()
        assert commit_sql == "COMMIT"
        begin_sql = str(mock_bind.execute.call_args_list[-1][0][0].text).strip()
        assert begin_sql == "BEGIN"
        return str(mock_bind.execute.call_args_list[sql_index][0][0].text).strip()

    def _run_upgrade_and_get_sql(self) -> str:
        """Run the upgrade migration and return the DDL SQL string."""
        return self._run_migration_and_get_sql("upgrade", expected_call_count=4, sql_index=2)

    def _run_downgrade_and_get_sql(self) -> str:
        """Run the downgrade migration and return the DDL SQL string."""
        return self._run_migration_and_get_sql("downgrade", expected_call_count=3, sql_index=1)

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
        executed_sql = self._run_upgrade_and_get_sql()
        assert INDEX_NAME in executed_sql
        assert "CONCURRENTLY" in executed_sql
        assert "IF NOT EXISTS" in executed_sql
        assert "pr_number IS NOT NULL" in executed_sql

    def test_upgrade_targets_webhooks_table(self) -> None:
        """Test that upgrade creates the index on the webhooks table."""
        executed_sql = self._run_upgrade_and_get_sql()
        assert "ON webhooks" in executed_sql

    def test_upgrade_index_column_order(self) -> None:
        """Test that the upgrade SQL specifies columns in the correct order."""
        executed_sql = self._run_upgrade_and_get_sql()
        assert "repository, pr_number, created_at ASC" in executed_sql

    def test_upgrade_drops_invalid_index_before_create(self) -> None:
        """Test that upgrade drops any existing invalid index before creating."""
        drop_sql = self._run_migration_and_get_sql("upgrade", expected_call_count=4, sql_index=1)
        assert "DROP INDEX CONCURRENTLY" in drop_sql
        assert "IF EXISTS" in drop_sql
        assert INDEX_NAME in drop_sql

    def test_downgrade_drops_correct_index(self) -> None:
        """Test that downgrade drops the ix_webhooks_repo_pr_number_created_at index."""
        executed_sql = self._run_downgrade_and_get_sql()
        assert "DROP INDEX CONCURRENTLY" in executed_sql
        assert INDEX_NAME in executed_sql
        assert "IF EXISTS" in executed_sql
