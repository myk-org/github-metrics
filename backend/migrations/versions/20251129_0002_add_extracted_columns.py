"""Add extracted columns to webhooks table for performance optimization.

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2025-11-29 00:02:00.000000

Adds materialized columns extracted from JSONB payload for performance optimization:

1. Pull Request columns (extracted from payload->'pull_request'):
   - pr_author: PR author login (VARCHAR 255)
   - pr_title: PR title (TEXT)
   - pr_state: PR state (open/closed) (VARCHAR 50)
   - pr_merged: Whether PR is merged (BOOLEAN)
   - pr_commits_count: Number of commits (INTEGER)
   - pr_html_url: PR HTML URL (TEXT)

2. Label column (extracted from payload->'label'):
   - label_name: Label name (VARCHAR 255)

3. Partial indexes on extracted columns (WHERE column IS NOT NULL):
   - ix_webhooks_pr_author: Fast PR author queries
   - ix_webhooks_pr_state: Fast PR state filtering
   - ix_webhooks_label_name: Fast label filtering

4. Data backfill: Populates columns from existing JSONB payload data

Benefits:
- Eliminates repeated JSONB extraction overhead
- Enables standard B-tree indexes (faster than functional JSONB indexes)
- Improves query planner statistics and query optimization
- Reduces query complexity and execution time
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d3e4f5g6h7"  # pragma: allowlist secret
down_revision = "b1c2d3e4f5g6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add extracted columns and backfill from JSONB payload."""
    # 1. Add new columns (all nullable since existing rows won't have them)

    # Pull Request columns
    op.add_column("webhooks", sa.Column("pr_author", sa.String(length=255), nullable=True))
    op.add_column("webhooks", sa.Column("pr_title", sa.Text(), nullable=True))
    op.add_column("webhooks", sa.Column("pr_state", sa.String(length=50), nullable=True))
    op.add_column("webhooks", sa.Column("pr_merged", sa.Boolean(), nullable=True))
    op.add_column("webhooks", sa.Column("pr_commits_count", sa.Integer(), nullable=True))
    op.add_column("webhooks", sa.Column("pr_html_url", sa.Text(), nullable=True))

    # Label column
    op.add_column("webhooks", sa.Column("label_name", sa.String(length=255), nullable=True))

    # 2. Backfill data from existing JSONB payload
    # Update PR-related columns where pull_request exists in payload
    op.execute(
        """
        UPDATE webhooks SET
            pr_author = payload->'pull_request'->'user'->>'login',
            pr_title = payload->'pull_request'->>'title',
            pr_state = payload->'pull_request'->>'state',
            pr_merged = (payload->'pull_request'->>'merged')::boolean,
            pr_commits_count = (payload->'pull_request'->>'commits')::int,
            pr_html_url = payload->'pull_request'->>'html_url'
        WHERE payload->'pull_request' IS NOT NULL AND pr_author IS NULL
        """
    )

    # Update label column where label exists in payload
    op.execute(
        """
        UPDATE webhooks SET
            label_name = payload->'label'->>'name'
        WHERE payload->'label' IS NOT NULL AND label_name IS NULL
        """
    )

    # 3. Create partial indexes on extracted columns (WHERE column IS NOT NULL)
    # These are more efficient than functional JSONB indexes

    # PR author index (for contributor queries)
    op.execute(
        """
        CREATE INDEX ix_webhooks_pr_author
        ON webhooks (pr_author)
        WHERE pr_author IS NOT NULL
        """
    )

    # PR state index (for filtering open/closed PRs)
    op.execute(
        """
        CREATE INDEX ix_webhooks_pr_state
        ON webhooks (pr_state)
        WHERE pr_state IS NOT NULL
        """
    )

    # Label name index (for label-based filtering)
    op.execute(
        """
        CREATE INDEX ix_webhooks_label_name
        ON webhooks (label_name)
        WHERE label_name IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop all indexes and columns created in upgrade()."""
    # Drop indexes first (in reverse order of creation)
    op.drop_index("ix_webhooks_label_name", table_name="webhooks")
    op.drop_index("ix_webhooks_pr_state", table_name="webhooks")
    op.drop_index("ix_webhooks_pr_author", table_name="webhooks")

    # Drop columns (in reverse order of addition)
    op.drop_column("webhooks", "label_name")
    op.drop_column("webhooks", "pr_html_url")
    op.drop_column("webhooks", "pr_commits_count")
    op.drop_column("webhooks", "pr_merged")
    op.drop_column("webhooks", "pr_state")
    op.drop_column("webhooks", "pr_title")
    op.drop_column("webhooks", "pr_author")
