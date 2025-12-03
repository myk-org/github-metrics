"""Webhook receiver routes."""

from __future__ import annotations

import ipaddress
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status
from simple_logger.logger import get_logger

from github_metrics.config import get_config
from github_metrics.metrics_tracker import MetricsTracker
from github_metrics.utils.security import verify_ip_allowlist, verify_signature

# Module-level logger
LOGGER = get_logger(name="github_metrics.routes.webhooks")

router = APIRouter()

# Type alias for IP networks (avoiding private type)
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Global instances (set by app.py during lifespan)
metrics_tracker: MetricsTracker | None = None
allowed_ips: tuple[IPNetwork, ...] = ()


@router.post("/metrics", operation_id="receive_webhook", tags=["mcp_exclude"])
async def receive_webhook(request: Request) -> dict[str, str]:
    """Receive and process GitHub webhook events.

    Verifies IP allowlist (if configured) and webhook signature,
    then stores the event metrics in the database.
    """
    start_time = time.time()
    config = get_config()

    # Verify IP allowlist
    await verify_ip_allowlist(request, allowed_ips)

    # Get request body
    payload_body = await request.body()

    # Verify webhook signature if secret is configured
    if config.webhook.secret:
        signature_header = request.headers.get("x-hub-signature-256")
        verify_signature(payload_body, config.webhook.secret, signature_header)

    # Parse webhook payload
    try:
        payload: dict[str, Any] = await request.json()
    except json.JSONDecodeError as ex:
        LOGGER.warning("Failed to parse webhook payload: invalid JSON")
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from ex

    # Extract event metadata
    delivery_id = request.headers.get("x-github-delivery", "unknown")
    event_type = request.headers.get("x-github-event", "unknown")
    action = payload.get("action", "")

    # Extract repository info
    repository_data = payload.get("repository", {})
    repository = repository_data.get("full_name", "unknown")

    # Extract sender info
    sender_data = payload.get("sender", {})
    sender = sender_data.get("login", "unknown")

    # Extract PR number if applicable
    pr_number: int | None = None
    if "pull_request" in payload:
        pr_number = payload["pull_request"].get("number")
    elif "issue" in payload and "pull_request" in payload.get("issue", {}):
        pr_number = payload["issue"].get("number")

    # Calculate processing time
    processing_time_ms = int((time.time() - start_time) * 1000)

    # Store the webhook event
    if metrics_tracker is not None:
        try:
            await metrics_tracker.track_webhook_event(
                delivery_id=delivery_id,
                repository=repository,
                event_type=event_type,
                action=action,
                sender=sender,
                payload=payload,
                processing_time_ms=processing_time_ms,
                status="success",
                pr_number=pr_number,
            )
        except Exception:
            # CRITICAL: Metrics tracking failure indicates potential data loss
            # This should trigger operational alerts for immediate investigation
            LOGGER.critical(
                "METRICS_TRACKING_FAILURE: Webhook event not persisted - potential data loss",
                extra={
                    "alert": "metrics_tracking_failure",
                    "severity": "critical",
                    "delivery_id": delivery_id,
                    "repository": repository,
                    "event_type": event_type,
                    "action": action,
                    "sender": sender,
                    "pr_number": pr_number,
                    "processing_time_ms": processing_time_ms,
                    "impact": "data_loss",
                },
            )
            # Also log full exception details for debugging
            LOGGER.exception(
                "Failed to track webhook event - exception details",
                extra={
                    "delivery_id": delivery_id,
                    "repository": repository,
                    "event_type": event_type,
                    "action": action,
                },
            )
            # Don't fail the webhook - just log the error

    LOGGER.info(
        "Webhook received",
        extra={
            "delivery_id": delivery_id,
            "repository": repository,
            "event_type": event_type,
            "action": action,
        },
    )

    return {"status": "ok", "delivery_id": delivery_id}
