"""Remove cross-team review columns from webhooks table.

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2025-12-10 00:01:00.000000

Removes cross-team review tracking columns that were added but never fully integrated:
- is_cross_team: Boolean flag for cross-team reviews
- reviewer_team: Team affiliation of the reviewer
- pr_sig_label: SIG label on the PR

These columns are being removed because:
1. Cross-team detection is now handled dynamically via SigTeamsConfig
2. Storing these values creates data duplication and sync issues
3. Dynamic calculation from sig_teams.yaml is more flexible and maintainable

Migration uses IF EXISTS for safety in case columns don't exist.

Related: Feature removed in favor of runtime calculation
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e4f5g6h7i8j9"  # pragma: allowlist secret
down_revision = "d3e4f5g6h7i8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove cross-team review columns from webhooks table.

    Uses IF EXISTS for idempotency in case columns were never created.
    Drops are executed in reverse dependency order (indexes first, then columns).
    """
    # Drop any indexes on these columns first (if they exist)
    op.execute("DROP INDEX IF EXISTS ix_webhooks_is_cross_team")
    op.execute("DROP INDEX IF EXISTS ix_webhooks_reviewer_team")
    op.execute("DROP INDEX IF EXISTS ix_webhooks_pr_sig_label")

    # Drop the columns (if they exist)
    op.execute("ALTER TABLE webhooks DROP COLUMN IF EXISTS is_cross_team")
    op.execute("ALTER TABLE webhooks DROP COLUMN IF EXISTS reviewer_team")
    op.execute("ALTER TABLE webhooks DROP COLUMN IF EXISTS pr_sig_label")


def downgrade() -> None:
    """Recreate cross-team review columns.

    This is provided for rollback capability, but note that:
    1. Data will not be automatically populated
    2. The feature is no longer supported
    3. Downgrade should only be used if absolutely necessary
    """
    # Recreate columns
    op.execute(
        """
        ALTER TABLE webhooks
        ADD COLUMN IF NOT EXISTS is_cross_team BOOLEAN
        """
    )
    op.execute(
        """
        ALTER TABLE webhooks
        ADD COLUMN IF NOT EXISTS reviewer_team VARCHAR(255)
        """
    )
    op.execute(
        """
        ALTER TABLE webhooks
        ADD COLUMN IF NOT EXISTS pr_sig_label VARCHAR(255)
        """
    )

    # Recreate indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhooks_is_cross_team
        ON webhooks (is_cross_team)
        WHERE is_cross_team IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhooks_reviewer_team
        ON webhooks (reviewer_team)
        WHERE reviewer_team IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhooks_pr_sig_label
        ON webhooks (pr_sig_label)
        WHERE pr_sig_label IS NOT NULL
        """
    )
