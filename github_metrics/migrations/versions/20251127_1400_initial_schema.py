"""Initial schema for GitHub metrics database.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-11-27 14:00:00.000000

Creates all core tables for tracking GitHub webhook events and metrics:
- webhooks: Main webhook event store with full payload
- pull_requests: PR master records with size metrics
- pr_events: PR timeline events for analytics
- pr_reviews: Review data for approval tracking
- pr_labels: Label history for workflow tracking
- check_runs: Check run results for CI/CD metrics
- api_usage: GitHub API usage tracking for rate limit monitoring
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all initial tables with indexes and constraints."""
    # Create webhooks table
    op.create_table(
        "webhooks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "delivery_id",
            sa.String(length=255),
            nullable=False,
            comment="X-GitHub-Delivery header - unique webhook ID",
        ),
        sa.Column(
            "repository",
            sa.String(length=255),
            nullable=False,
            comment="Repository in org/repo format",
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
            comment="GitHub event type: pull_request, issue_comment, check_run, etc.",
        ),
        sa.Column(
            "action",
            sa.String(length=50),
            nullable=True,
            comment="Event action: opened, synchronize, closed, etc. (null for events without actions like push)",
        ),
        sa.Column(
            "pr_number",
            sa.Integer(),
            nullable=True,
            comment="PR number if applicable to this event",
        ),
        sa.Column(
            "sender",
            sa.String(length=255),
            nullable=False,
            comment="GitHub username who triggered the event",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Full webhook payload from GitHub",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When webhook was received",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When webhook processing completed",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
            comment="Processing duration in milliseconds",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Processing status: success, error, partial",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error message if processing failed",
        ),
        sa.Column(
            "api_calls_count",
            sa.Integer(),
            nullable=False,
            comment="Number of GitHub API calls made during processing",
        ),
        sa.Column(
            "token_spend",
            sa.Integer(),
            nullable=False,
            comment="GitHub API calls consumed (rate limit tokens spent)",
        ),
        sa.Column(
            "token_remaining",
            sa.Integer(),
            nullable=False,
            comment="Rate limit remaining after processing",
        ),
        sa.Column(
            "metrics_available",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
            comment="Whether API metrics are available (False = no tracking, True = metrics tracked)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id"),
    )

    # Create indexes for webhooks table
    # Note: delivery_id unique index is already created by UniqueConstraint above
    op.create_index("ix_webhooks_repository", "webhooks", ["repository"], unique=False)
    op.create_index("ix_webhooks_event_type", "webhooks", ["event_type"], unique=False)
    op.create_index("ix_webhooks_pr_number", "webhooks", ["pr_number"], unique=False)
    op.create_index("ix_webhooks_created_at", "webhooks", ["created_at"], unique=False)
    op.create_index("ix_webhooks_repository_created_at", "webhooks", ["repository", "created_at"], unique=False)
    op.create_index("ix_webhooks_repository_event_type", "webhooks", ["repository", "event_type"], unique=False)

    # Create pull_requests table
    op.create_table(
        "pull_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "repository",
            sa.String(length=255),
            nullable=False,
            comment="Repository in org/repo format",
        ),
        sa.Column(
            "pr_number",
            sa.Integer(),
            nullable=False,
            comment="PR number within repository",
        ),
        sa.Column(
            "title",
            sa.String(length=500),
            nullable=False,
            comment="PR title",
        ),
        sa.Column(
            "author",
            sa.String(length=255),
            nullable=False,
            comment="GitHub username of PR author",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When PR was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When PR was last updated",
        ),
        sa.Column(
            "merged_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When PR was merged (null if not merged)",
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When PR was closed (null if still open)",
        ),
        sa.Column(
            "state",
            sa.String(length=20),
            nullable=False,
            comment="PR state: open, merged, closed",
        ),
        sa.Column(
            "draft",
            sa.Boolean(),
            nullable=False,
            comment="Whether PR is in draft state",
        ),
        sa.Column(
            "additions",
            sa.Integer(),
            nullable=False,
            comment="Lines of code added",
        ),
        sa.Column(
            "deletions",
            sa.Integer(),
            nullable=False,
            comment="Lines of code deleted",
        ),
        sa.Column(
            "changed_files",
            sa.Integer(),
            nullable=False,
            comment="Number of files changed",
        ),
        sa.Column(
            "size_label",
            sa.String(length=10),
            nullable=True,
            comment="PR size classification: XS, S, M, L, XL, XXL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository", "pr_number", name="uq_pull_requests_repository_pr_number"),
    )

    # Create indexes for pull_requests table
    op.create_index("ix_pull_requests_repository", "pull_requests", ["repository"], unique=False)
    op.create_index("ix_pull_requests_pr_number", "pull_requests", ["pr_number"], unique=False)
    op.create_index("ix_pull_requests_author", "pull_requests", ["author"], unique=False)
    op.create_index("ix_pull_requests_created_at", "pull_requests", ["created_at"], unique=False)
    op.create_index("ix_pull_requests_updated_at", "pull_requests", ["updated_at"], unique=False)
    op.create_index("ix_pull_requests_repository_state", "pull_requests", ["repository", "state"], unique=False)
    op.create_index(
        "ix_pull_requests_repository_created_at", "pull_requests", ["repository", "created_at"], unique=False
    )
    op.create_index("ix_pull_requests_author_created_at", "pull_requests", ["author", "created_at"], unique=False)

    # Create pr_events table
    op.create_table(
        "pr_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "pr_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to pull_requests table",
        ),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to webhooks table",
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
            comment="Event type: opened, synchronize, review, check_run, etc.",
        ),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Event-specific data from webhook payload",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When event occurred",
        ),
        sa.ForeignKeyConstraint(["pr_id"], ["pull_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for pr_events table
    op.create_index("ix_pr_events_pr_id", "pr_events", ["pr_id"], unique=False)
    op.create_index("ix_pr_events_event_type", "pr_events", ["event_type"], unique=False)
    op.create_index("ix_pr_events_created_at", "pr_events", ["created_at"], unique=False)

    # Create pr_reviews table
    op.create_table(
        "pr_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "pr_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to pull_requests table",
        ),
        sa.Column(
            "reviewer",
            sa.String(length=255),
            nullable=False,
            comment="GitHub username of reviewer",
        ),
        sa.Column(
            "review_type",
            sa.String(length=30),
            nullable=False,
            comment="Review type: approved, changes_requested, commented",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When review was submitted",
        ),
        sa.ForeignKeyConstraint(["pr_id"], ["pull_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for pr_reviews table
    op.create_index("ix_pr_reviews_pr_id", "pr_reviews", ["pr_id"], unique=False)
    op.create_index("ix_pr_reviews_reviewer", "pr_reviews", ["reviewer"], unique=False)
    op.create_index("ix_pr_reviews_created_at", "pr_reviews", ["created_at"], unique=False)

    # Create pr_labels table
    op.create_table(
        "pr_labels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "pr_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to pull_requests table",
        ),
        sa.Column(
            "label",
            sa.String(length=100),
            nullable=False,
            comment="Label name",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When label was added",
        ),
        sa.Column(
            "removed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When label was removed (null if still present)",
        ),
        sa.ForeignKeyConstraint(["pr_id"], ["pull_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for pr_labels table
    op.create_index("ix_pr_labels_pr_id", "pr_labels", ["pr_id"], unique=False)
    op.create_index("ix_pr_labels_label", "pr_labels", ["label"], unique=False)
    op.create_index("ix_pr_labels_added_at", "pr_labels", ["added_at"], unique=False)

    # Create check_runs table
    op.create_table(
        "check_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "pr_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to pull_requests table",
        ),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to webhooks table",
        ),
        sa.Column(
            "check_name",
            sa.String(length=255),
            nullable=False,
            comment="Check name: tox, pre-commit, container-build, etc.",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Status: queued, in_progress, completed",
        ),
        sa.Column(
            "conclusion",
            sa.String(length=20),
            nullable=True,
            comment="Conclusion: success, failure, cancelled, etc. (null if not completed)",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When check run started",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When check run completed (null if not completed)",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Check run duration in milliseconds (null if not completed)",
        ),
        sa.Column(
            "output_title",
            sa.String(length=500),
            nullable=True,
            comment="Check run output title",
        ),
        sa.Column(
            "output_summary",
            sa.Text(),
            nullable=True,
            comment="Check run output summary (especially for failures)",
        ),
        sa.ForeignKeyConstraint(["pr_id"], ["pull_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for check_runs table
    op.create_index("ix_check_runs_pr_id", "check_runs", ["pr_id"], unique=False)
    op.create_index("ix_check_runs_check_name", "check_runs", ["check_name"], unique=False)
    op.create_index("ix_check_runs_started_at", "check_runs", ["started_at"], unique=False)
    op.create_index("ix_check_runs_pr_id_check_name", "check_runs", ["pr_id", "check_name"], unique=False)
    op.create_index("ix_check_runs_pr_id_started_at", "check_runs", ["pr_id", "started_at"], unique=False)

    # Create api_usage table
    op.create_table(
        "api_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Primary key UUID",
        ),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to webhooks table",
        ),
        sa.Column(
            "repository",
            sa.String(length=255),
            nullable=False,
            comment="Repository in org/repo format",
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
            comment="Event type: pull_request, issue_comment, etc.",
        ),
        sa.Column(
            "api_calls_count",
            sa.Integer(),
            nullable=False,
            comment="Number of GitHub API calls made",
        ),
        sa.Column(
            "initial_rate_limit",
            sa.Integer(),
            nullable=False,
            comment="Rate limit remaining before processing",
        ),
        sa.Column(
            "final_rate_limit",
            sa.Integer(),
            nullable=False,
            comment="Rate limit remaining after processing",
        ),
        sa.Column(
            "token_spend",
            sa.Integer(),
            nullable=False,
            comment="GitHub API calls consumed (rate limit tokens spent)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When API usage was recorded",
        ),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for api_usage table
    op.create_index("ix_api_usage_webhook_id", "api_usage", ["webhook_id"], unique=False)
    op.create_index("ix_api_usage_repository", "api_usage", ["repository"], unique=False)
    op.create_index("ix_api_usage_event_type", "api_usage", ["event_type"], unique=False)
    op.create_index("ix_api_usage_created_at", "api_usage", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse order to respect foreign key constraints."""
    # Drop tables in reverse order (dependent tables first)
    op.drop_table("api_usage")
    op.drop_table("check_runs")
    op.drop_table("pr_labels")
    op.drop_table("pr_reviews")
    op.drop_table("pr_events")
    op.drop_table("pull_requests")
    op.drop_table("webhooks")
