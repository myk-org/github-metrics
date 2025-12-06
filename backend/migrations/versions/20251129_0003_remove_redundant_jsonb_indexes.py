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

Note: DROP INDEX without CONCURRENTLY is used here because:
1. Dropping indexes is fast (just metadata removal)
2. CONCURRENTLY requires running outside a transaction which complicates Alembic migrations
3. The brief lock during drop is acceptable for this operation

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

    Uses standard DROP INDEX (not CONCURRENTLY) because:
    - Index drops are fast operations (metadata removal only)
    - CONCURRENTLY cannot run inside Alembic's transaction wrapper
    - Brief ACCESS EXCLUSIVE lock is acceptable for index removal
    """
    # Drop JSONB functional indexes - these are now redundant
    # Using IF EXISTS for idempotency
    op.execute("DROP INDEX IF EXISTS ix_webhooks_pr_author_jsonb")
    op.execute("DROP INDEX IF EXISTS ix_webhooks_label_name_jsonb")


def downgrade() -> None:
    """Recreate JSONB functional indexes."""
    # Recreate PR author JSONB index
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhooks_pr_author_jsonb
        ON webhooks ((payload->'pull_request'->'user'->>'login'))
        WHERE payload->'pull_request' IS NOT NULL
        """
    )

    # Recreate label name JSONB index
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhooks_label_name_jsonb
        ON webhooks ((payload->'label'->>'name'))
        WHERE payload->'label' IS NOT NULL
        """
    )
