"""Add composite index for pr_creators DISTINCT ON query.

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-02-19 00:01:00.000000

Adds a partial composite index to optimize the pr_creators CTE query pattern:
  DISTINCT ON (repository, pr_number) ... ORDER BY repository, pr_number, created_at ASC

This query was timing out (>60s) on the contributors endpoint due to full table sort.
The index enables PostgreSQL to satisfy DISTINCT ON via index scan instead of sort.
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "f5g6h7i8j9k0"  # pragma: allowlist secret
down_revision = "e4f5g6h7i8j9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create composite index for DISTINCT ON (repository, pr_number) queries.

    Uses CONCURRENTLY to avoid locking the table during index creation.
    Must run outside a transaction (autocommit mode).
    """
    conn = op.get_bind()
    # CONCURRENTLY requires autocommit (no transaction)
    with conn.execution_options(isolation_level="AUTOCOMMIT"):
        conn.execute(
            text(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_webhooks_repo_pr_number_created_at
                ON webhooks (repository, pr_number, created_at ASC)
                WHERE pr_number IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    """Drop the composite index."""
    op.drop_index("ix_webhooks_repo_pr_number_created_at", table_name="webhooks")
