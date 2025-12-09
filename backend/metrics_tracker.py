"""
Metrics tracking for GitHub webhook events and processing statistics.

Provides comprehensive metrics collection including:
- Webhook event storage with full payload
- Processing time and performance metrics
- API usage tracking
- Error tracking and status monitoring

Architecture:
- Async database operations using asyncpg connection pool
- No defensive checks on required parameters (fail-fast principle)
- Proper error handling with structured logging
- Integration with DatabaseManager
"""

import json
import logging
from typing import Any
from uuid import uuid4

from backend.database import DatabaseManager


class MetricsTracker:
    """
    Tracks webhook events and processing metrics in PostgreSQL database.

    Stores comprehensive metrics including:
    - Webhook event metadata and payloads
    - Processing duration and performance
    - API usage and rate limit consumption
    - Success/failure status with error details

    Architecture guarantees:
    - db_manager is ALWAYS provided (required parameter) - no defensive checks
    - logger is ALWAYS provided (required parameter) - no defensive checks

    Example:
        tracker = MetricsTracker(db_manager, logger)
        await tracker.track_webhook_event(
            delivery_id="abc123",
            repository="org/repo",
            event_type="pull_request",
            action="opened",
            pr_number=42,
            sender="user",
            payload={"key": "value"},
            processing_time_ms=150,
            status="success",
        )
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize metrics tracker.

        Args:
            db_manager: Database connection manager for metrics storage
            logger: Logger instance for metrics tracking events

        Note:
            No defensive checks - all parameters are required and ALWAYS provided.
            Architecture guarantees these are initialized before MetricsTracker.
        """
        self.db_manager = db_manager
        self.logger = logger

    async def track_webhook_event(
        self,
        delivery_id: str,
        repository: str,
        event_type: str,
        action: str,
        sender: str,
        payload: dict[str, Any],
        processing_time_ms: int,
        status: str,
        *,
        pr_number: int | None = None,
        error_message: str | None = None,
        api_calls_count: int = 0,
        token_spend: int = 0,
        token_remaining: int = 0,
        metrics_available: bool = True,
        is_cross_team: bool | None = None,
        reviewer_team: str | None = None,
        pr_sig_label: str | None = None,
    ) -> None:
        """
        Track webhook event with comprehensive metrics.

        Stores webhook event in database with processing metrics including:
        - Event metadata (delivery ID, repository, event type, action)
        - Processing metrics (duration, API calls, token usage)
        - Status tracking (success, error, partial)
        - Full payload for debugging and analytics
        - Extracted PR and label fields for query performance optimization

        Uses DatabaseManager.execute() for centralized pool management and
        precondition checking. All database operations go through DatabaseManager
        to avoid duplicated connection handling logic.

        Args:
            delivery_id: GitHub webhook delivery ID (X-GitHub-Delivery header)
            repository: Repository in org/repo format
            event_type: GitHub event type (pull_request, issue_comment, etc.)
            action: Event action (opened, synchronize, closed, etc.)
            sender: GitHub username who triggered the event
            payload: Full webhook payload from GitHub
            processing_time_ms: Processing duration in milliseconds
            status: Processing status (success, error, partial)
            pr_number: PR number if applicable (optional)
            error_message: Error message if processing failed (optional)
            api_calls_count: Number of GitHub API calls made (default: 0)
            token_spend: GitHub API calls consumed (default: 0)
            token_remaining: Rate limit remaining after processing (default: 0)
            metrics_available: Whether API metrics are available (default: True)
            is_cross_team: Whether the review is cross-team (optional)
            reviewer_team: Team name of the reviewer (optional)
            pr_sig_label: PR SIG label name (optional)

        Raises:
            asyncpg.PostgresError: If database insert fails
            ValueError: If database pool not initialized

        Example:
            await tracker.track_webhook_event(
                delivery_id="abc123",
                repository="myorg/myrepo",
                event_type="pull_request",
                action="opened",
                pr_number=42,
                sender="johndoe",
                payload=webhook_payload,
                processing_time_ms=150,
                status="success",
                api_calls_count=3,
                token_spend=3,
                token_remaining=4997,
                metrics_available=True,
            )
        """
        try:
            # Serialize payload to JSON string for JSONB storage
            # Use default=str for defensive handling of non-serializable types
            # (datetime, UUID, etc.) to prevent TypeError
            payload_json = json.dumps(payload, default=str)

            # Extract fields from payload for query performance columns
            pr_data = payload.get("pull_request", {})
            label_data = payload.get("label", {})

            # Extract PR fields (None if not a PR event)
            extracted_pr_author = pr_data.get("user", {}).get("login") if pr_data else None
            extracted_pr_title = pr_data.get("title") if pr_data else None
            extracted_pr_state = pr_data.get("state") if pr_data else None
            extracted_pr_merged = pr_data.get("merged") if pr_data else None
            extracted_pr_commits_count = pr_data.get("commits") if pr_data else None
            extracted_pr_html_url = pr_data.get("html_url") if pr_data else None

            # Extract label name (None if not a label event)
            extracted_label_name = label_data.get("name") if label_data else None

            # Insert webhook event into database using DatabaseManager.execute()
            # This centralizes pool management and precondition checks
            # Note: processed_at is auto-populated by database via server_default=func.now()
            await self.db_manager.execute(
                """
                INSERT INTO webhooks (
                    id, delivery_id, repository, event_type, action,
                    pr_number, sender, payload, duration_ms,
                    status, error_message, api_calls_count, token_spend, token_remaining,
                    metrics_available,
                    pr_author, pr_title, pr_state, pr_merged, pr_commits_count, pr_html_url, label_name,
                    is_cross_team, reviewer_team, pr_sig_label
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,
                    $23, $24, $25
                )
                """,
                uuid4(),
                delivery_id,
                repository,
                event_type,
                action,
                pr_number,
                sender,
                payload_json,
                processing_time_ms,
                status,
                error_message,
                api_calls_count,
                token_spend,
                token_remaining,
                metrics_available,
                extracted_pr_author,
                extracted_pr_title,
                extracted_pr_state,
                extracted_pr_merged,
                extracted_pr_commits_count,
                extracted_pr_html_url,
                extracted_label_name,
                is_cross_team,
                reviewer_team,
                pr_sig_label,
            )

            self.logger.info(
                "Webhook event tracked successfully: delivery_id=%s, repository=%s, event_type=%s, "
                "action=%s, status=%s, processing_time_ms=%s",
                delivery_id,
                repository,
                event_type,
                action,
                status,
                processing_time_ms,
            )

        except Exception:
            self.logger.exception(
                "Failed to track webhook event: delivery_id=%s, repository=%s, event_type=%s",
                delivery_id,
                repository,
                event_type,
            )
            raise
