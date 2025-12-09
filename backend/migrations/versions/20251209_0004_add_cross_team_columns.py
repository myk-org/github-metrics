"""Add cross-team review tracking columns to webhooks table.

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2025-12-09 00:04:00.000000

Adds columns for tracking cross-team reviews and team affiliations:

1. Cross-team review tracking columns:
   - is_cross_team: Boolean flag indicating cross-team review (nullable)
     * True: reviewer from different team than PR's sig-* label
     * False: reviewer from same team as PR's sig-* label
     * NULL: team affiliation unknown or not applicable

   - reviewer_team: The team name the reviewer belongs to (VARCHAR 100, nullable)
     * Populated from reviewer's team membership data
     * NULL if team affiliation unknown

   - pr_sig_label: The sig-* label on the PR at review time (VARCHAR 100, nullable)
     * Captures the PR's team assignment at time of review
     * NULL if PR has no sig-* label or label unknown

2. Composite partial index for efficient cross-team queries:
   - ix_webhooks_cross_team: Index on (is_cross_team, reviewer_team, pr_sig_label)
   - Only indexes rows WHERE is_cross_team IS NOT NULL
   - Optimizes queries filtering by cross-team status and team affiliations

Benefits:
- Enables analysis of cross-team collaboration patterns
- Fast queries for team-specific review metrics
- Tracks team boundaries and collaboration trends
- Minimal storage overhead (partial index only on populated rows)

Use cases:
- "Which teams provide the most cross-team reviews?"
- "What percentage of reviews for sig-x are cross-team?"
- "Which reviewers frequently review outside their team?"
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4f5g6h7i8j9"  # pragma: allowlist secret
down_revision = "d3e4f5g6h7i8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add cross-team tracking columns and index."""
    # 1. Add new columns (all nullable since existing rows won't have them)

    # Cross-team review flag
    op.add_column("webhooks", sa.Column("is_cross_team", sa.Boolean(), nullable=True))

    # Reviewer's team affiliation
    op.add_column("webhooks", sa.Column("reviewer_team", sa.String(length=100), nullable=True))

    # PR's sig-* label at review time
    op.add_column("webhooks", sa.Column("pr_sig_label", sa.String(length=100), nullable=True))

    # 2. Create partial composite index for efficient cross-team queries
    # Only index rows where is_cross_team is known (not NULL)
    op.execute(
        """
        CREATE INDEX ix_webhooks_cross_team
        ON webhooks (is_cross_team, reviewer_team, pr_sig_label)
        WHERE is_cross_team IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop all columns and indexes created in upgrade()."""
    # Drop index first
    op.drop_index("ix_webhooks_cross_team", table_name="webhooks")

    # Drop columns (in reverse order of addition)
    op.drop_column("webhooks", "pr_sig_label")
    op.drop_column("webhooks", "reviewer_team")
    op.drop_column("webhooks", "is_cross_team")
