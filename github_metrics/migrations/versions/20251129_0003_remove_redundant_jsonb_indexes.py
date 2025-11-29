"""Remove redundant JSONB functional indexes.

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2025-11-29 00:03:00.000000

Removes JSONB functional indexes that are now redundant after extracted columns
were added in migration c2d3e4f5g6h7.

Redundant indexes being removed:
- ix_webhooks_pr_author_jsonb: Replaced by ix_webhooks_pr_author (on pr_author column)
- ix_webhooks_label_name_jsonb: Replaced by ix_webhooks_label_name (on label_name column)

Benefits of removal:
- Reduces storage overhead (duplicate index data)
- Reduces write amplification (fewer indexes to update on INSERT/UPDATE)
- Simplifies index maintenance
- The extracted column indexes are more efficient (standard B-tree vs functional)

Note: The composite and PR story indexes are retained as they serve different purposes:
- ix_webhooks_created_at_desc_repository: Time-based queries
- ix_webhooks_repository_event_type_created_at: Event type filtering
- ix_webhooks_check_run_head_sha: PR story check_run lookups
- ix_webhooks_status_sha: PR story status lookups

Note: Uses CONCURRENTLY for non-blocking index operations in production.
This requires running outside a transaction block.

Related: https://github.com/myk-org/github-metrics/issues/23
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3e4f5g6h7i8"  # pragma: allowlist secret
down_revision = "c2d3e4f5g6h7"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove redundant JSONB functional indexes.

    Uses DROP INDEX CONCURRENTLY to avoid ACCESS EXCLUSIVE locks in production.
    """
    # Drop JSONB functional indexes concurrently to avoid blocking reads/writes
    # CONCURRENTLY cannot run inside a transaction, so we use raw SQL
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_webhooks_pr_author_jsonb")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_webhooks_label_name_jsonb")


def downgrade() -> None:
    """Recreate JSONB functional indexes.

    Uses CREATE INDEX CONCURRENTLY to avoid ACCESS EXCLUSIVE locks in production.
    """
    # Recreate PR author JSONB index concurrently
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_webhooks_pr_author_jsonb
        ON webhooks ((payload->'pull_request'->'user'->>'login'))
        WHERE payload->'pull_request' IS NOT NULL
        """
    )

    # Recreate label name JSONB index concurrently
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_webhooks_label_name_jsonb
        ON webhooks ((payload->'label'->>'name'))
        WHERE payload->'label' IS NOT NULL
        """
    )
