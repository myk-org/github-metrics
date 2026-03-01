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
    CONCURRENTLY cannot run inside a transaction, so the active Alembic
    transaction is committed first.
    """
    conn = op.get_bind()
    # CONCURRENTLY cannot run inside a transaction — commit Alembic's active transaction
    conn.execute(text("COMMIT"))
    # Drop any existing invalid index left by a prior failed CONCURRENTLY build
    conn.execute(
        text(
            """
            DROP INDEX CONCURRENTLY IF EXISTS ix_webhooks_repo_pr_number_created_at
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_webhooks_repo_pr_number_created_at
            ON webhooks (repository, pr_number, created_at ASC)
            WHERE pr_number IS NOT NULL
            """
        )
    )
    # Re-open a transaction so Alembic can update alembic_version
    conn.execute(text("BEGIN"))


def downgrade() -> None:
    """Drop the composite index.

    Uses CONCURRENTLY to avoid locking the table during index removal.
    CONCURRENTLY cannot run inside a transaction, so the active Alembic
    transaction is committed first.
    """
    conn = op.get_bind()
    # CONCURRENTLY cannot run inside a transaction — commit Alembic's active transaction
    conn.execute(text("COMMIT"))
    conn.execute(
        text(
            """
            DROP INDEX CONCURRENTLY IF EXISTS ix_webhooks_repo_pr_number_created_at
            """
        )
    )
    # Re-open a transaction so Alembic can update alembic_version
    conn.execute(text("BEGIN"))
