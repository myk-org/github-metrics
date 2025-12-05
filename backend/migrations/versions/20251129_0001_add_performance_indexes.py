"""Add performance indexes for common query patterns.

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2025-11-29 00:01:00.000000

Adds performance-optimized indexes for frequently executed queries:

1. Composite indexes for webhook queries:
   - ix_webhooks_created_at_desc_repository: Time-based queries with repository filter
   - ix_webhooks_repository_event_type_created_at: Event type filtering with time ordering

2. Functional JSONB indexes for contributor/user queries:
   - ix_webhooks_pr_author_jsonb: Fast PR author lookups from payload
   - ix_webhooks_label_name_jsonb: Fast label name lookups from payload

3. PR story query optimization (webhooks table - check_run and status events):
   - ix_webhooks_check_run_head_sha: For check_run events filtered by head_sha
   - ix_webhooks_status_sha: For status events filtered by sha

These indexes significantly improve dashboard query performance, especially for:
- Contributor metrics and PR listings
- Time-range filtered queries (last 30 days, etc.)
- PR timeline/story reconstruction
- Label-based filtering and analytics
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5g6"  # pragma: allowlist secret
down_revision = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create performance indexes for common query patterns."""
    # 1. Composite indexes for webhook queries (using raw SQL for DESC ordering)

    # Time-based queries with repository filter (created_at DESC for recent events first)
    op.execute(
        """
        CREATE INDEX ix_webhooks_created_at_desc_repository
        ON webhooks (created_at DESC, repository)
        """
    )

    # Event type filtering with time ordering (for event type dashboards)
    op.execute(
        """
        CREATE INDEX ix_webhooks_repository_event_type_created_at
        ON webhooks (repository, event_type, created_at DESC)
        """
    )

    # 2. Functional JSONB indexes for contributor/user queries

    # Fast PR author lookups from webhook payload
    # Query pattern: WHERE payload->'pull_request'->'user'->>'login' = 'username'
    op.execute(
        """
        CREATE INDEX ix_webhooks_pr_author_jsonb
        ON webhooks ((payload->'pull_request'->'user'->>'login'))
        WHERE payload->'pull_request' IS NOT NULL
        """
    )

    # Fast label name lookups from webhook payload
    # Query pattern: WHERE payload->'label'->>'name' = 'label_name'
    op.execute(
        """
        CREATE INDEX ix_webhooks_label_name_jsonb
        ON webhooks ((payload->'label'->>'name'))
        WHERE payload->'label' IS NOT NULL
        """
    )

    # 3. PR story query optimization indexes
    # These queries run on webhooks table, not check_runs table!

    # For check_run events filtered by head_sha
    # Query: WHERE event_type = 'check_run' AND repository = $1 AND payload->'check_run'->>'head_sha' = ANY($2)
    op.execute(
        """
        CREATE INDEX ix_webhooks_check_run_head_sha
        ON webhooks (repository, (payload->'check_run'->>'head_sha'))
        WHERE event_type = 'check_run'
        """
    )

    # For status events filtered by sha
    # Query: WHERE event_type = 'status' AND repository = $1 AND payload->>'sha' = ANY($2)
    op.execute(
        """
        CREATE INDEX ix_webhooks_status_sha
        ON webhooks (repository, (payload->>'sha'))
        WHERE event_type = 'status'
        """
    )


def downgrade() -> None:
    """Drop all performance indexes created in upgrade()."""
    # Drop in reverse order of creation

    # PR story query optimization indexes
    op.drop_index("ix_webhooks_status_sha", table_name="webhooks")
    op.drop_index("ix_webhooks_check_run_head_sha", table_name="webhooks")

    # Functional JSONB indexes
    op.drop_index("ix_webhooks_label_name_jsonb", table_name="webhooks")
    op.drop_index("ix_webhooks_pr_author_jsonb", table_name="webhooks")

    # Composite webhook indexes
    op.drop_index("ix_webhooks_repository_event_type_created_at", table_name="webhooks")
    op.drop_index("ix_webhooks_created_at_desc_repository", table_name="webhooks")
