"""
PR story/timeline aggregation from webhook events.

Aggregates complete PR timeline from webhook payloads including:
- PR lifecycle events (opened, closed, merged, reopened)
- Code updates (commits/synchronize events)
- Reviews (approved, changes requested, comments)
- Labels (added, removed, verified, approved, lgtm)
- Check runs (CI/CD pipeline status)
- Comments and review requests

Architecture:
- All data from webhooks table only (single source of truth)
- Event grouping within 60-second windows for parallel events
- Collapse same-type events for readability
- Summary statistics for quick insights

Example:
    story = await get_pr_story(db_manager, "org/repo", 123)
    if story:
        print(f"PR #{story['pr']['number']}: {story['pr']['title']}")
        for group in story['events']:
            print(f"  {group['timestamp']}: {len(group['events'])} events")
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from simple_logger.logger import get_logger

from github_metrics.database import DatabaseManager

LOGGER = get_logger(name="github_metrics.pr_story")

# Event grouping window - events within this duration are considered parallel
GROUPING_WINDOW_SECONDS = 60


def _parse_payload(payload: dict[str, Any] | str | None) -> dict[str, Any]:
    """Parse payload from database, handling both dict and string formats.

    asyncpg may return JSONB as string depending on configuration.
    This function ensures we always have a dict.

    Args:
        payload: Payload from database (dict, JSON string, or None for NULL values)

    Returns:
        Parsed payload as dict, empty dict if parsing fails or payload is None
    """
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.warning("Failed to parse JSON payload: %s", payload[:100] if payload else "")
            return {}
    return {}


def _extract_event_from_payload(
    event_type: str,
    action: str,
    payload: dict[str, Any],
    delivery_id: str,
) -> list[dict[str, Any]]:
    """
    Extract timeline events from webhook payload.

    Parses webhook payload to extract relevant PR timeline events including
    state changes, reviews, labels, and comments.

    Args:
        event_type: GitHub event type (pull_request, pull_request_review, etc.)
        action: Event action (opened, synchronize, labeled, etc.)
        payload: Full webhook payload
        delivery_id: Webhook delivery ID

    Returns:
        List of extracted events (can be multiple for complex payloads)
        Empty list if event type not relevant for timeline

    Example:
        events = _extract_event_from_payload(
            "pull_request", "opened", payload, "abc123"
        )
        # Returns: [{"type": "pr_opened", "actor": "user", "details": {...}}]
    """
    events: list[dict[str, Any]] = []

    # Extract actor (sender or reviewer)
    actor = payload.get("sender", {}).get("login", "unknown")

    if event_type == "pull_request":
        pr_data = payload.get("pull_request", {})

        # State change events
        if action == "opened":
            events.append({
                "type": "pr_opened",
                "actor": actor,
                "details": {
                    "title": pr_data.get("title", ""),
                    "draft": pr_data.get("draft", False),
                },
                "delivery_id": delivery_id,
            })
        elif action == "closed":
            merged = pr_data.get("merged", False)
            if merged:
                events.append({
                    "type": "pr_merged",
                    "actor": actor,
                    "details": {
                        "merged_by": pr_data.get("merged_by", {}).get("login", actor),
                    },
                    "delivery_id": delivery_id,
                })
            else:
                events.append({
                    "type": "pr_closed",
                    "actor": actor,
                    "details": {},
                    "delivery_id": delivery_id,
                })
        elif action == "reopened":
            events.append({
                "type": "pr_reopened",
                "actor": actor,
                "details": {},
                "delivery_id": delivery_id,
            })
        elif action == "synchronize":
            # Commit/code update
            events.append({
                "type": "commit",
                "actor": actor,
                "details": {
                    "commits": pr_data.get("commits", 0),
                    "head_sha": pr_data.get("head", {}).get("sha", ""),
                },
                "delivery_id": delivery_id,
            })
        elif action == "ready_for_review":
            events.append({
                "type": "ready_for_review",
                "actor": actor,
                "details": {},
                "delivery_id": delivery_id,
            })
        elif action == "review_requested":
            requested_reviewer = payload.get("requested_reviewer", {}).get("login", "unknown")
            events.append({
                "type": "review_requested",
                "actor": actor,
                "details": {
                    "reviewer": requested_reviewer,
                },
                "delivery_id": delivery_id,
            })
        elif action == "labeled":
            label_name = payload.get("label", {}).get("name", "")

            # Special label handling
            if "verified" in label_name.lower():
                events.append({
                    "type": "verified",
                    "actor": actor,
                    "details": {"label": label_name},
                    "delivery_id": delivery_id,
                })
            elif label_name.startswith("approved-"):
                # Custom approval workflow: approved-<username>
                approver = label_name[9:]  # Extract username after "approved-"
                events.append({
                    "type": "approved_label",
                    "actor": approver,
                    "details": {"label": label_name},
                    "delivery_id": delivery_id,
                })
            elif label_name.startswith("lgtm-"):
                # Custom LGTM workflow: lgtm-<username>
                lgtm_user = label_name[5:]  # Extract username after "lgtm-"
                events.append({
                    "type": "lgtm",
                    "actor": lgtm_user,
                    "details": {"label": label_name},
                    "delivery_id": delivery_id,
                })
            else:
                # Generic label add
                events.append({
                    "type": "label_added",
                    "actor": actor,
                    "details": {"label": label_name},
                    "delivery_id": delivery_id,
                })
        elif action == "unlabeled":
            label_name = payload.get("label", {}).get("name", "")
            events.append({
                "type": "label_removed",
                "actor": actor,
                "details": {"label": label_name},
                "delivery_id": delivery_id,
            })

    elif event_type == "pull_request_review":
        if action == "submitted":
            review_state = payload.get("review", {}).get("state", "").lower()
            reviewer = payload.get("review", {}).get("user", {}).get("login", actor)

            if review_state == "approved":
                events.append({
                    "type": "review_approved",
                    "actor": reviewer,
                    "details": {},
                    "delivery_id": delivery_id,
                })
            elif review_state == "changes_requested":
                events.append({
                    "type": "review_changes",
                    "actor": reviewer,
                    "details": {},
                    "delivery_id": delivery_id,
                })
            elif review_state == "commented":
                events.append({
                    "type": "review_comment",
                    "actor": reviewer,
                    "details": {},
                    "delivery_id": delivery_id,
                })

    elif event_type == "issue_comment":
        if action == "created":
            # Only include if this is a PR (has pull_request field in issue)
            if "pull_request" in payload.get("issue", {}):
                comment_data = payload.get("comment", {})
                body = comment_data.get("body", "")
                events.append({
                    "type": "comment",
                    "actor": actor,
                    "details": {
                        "body": body[:500] if len(body) > 500 else body,
                        "truncated": len(body) > 500,
                        "url": comment_data.get("html_url", ""),
                    },
                    "delivery_id": delivery_id,
                })

    return events


def _group_timeline_events(
    events: list[tuple[datetime, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Group events into timeline with parallel event detection and collapsing.

    Groups events within GROUPING_WINDOW_SECONDS as parallel (same timestamp).
    Collapses multiple same-type events into summary for readability.

    Args:
        events: List of (timestamp, event_dict) tuples sorted by timestamp

    Returns:
        Timeline groups with events and optional collapsed summaries

    Example:
        timeline = _group_timeline_events([
            (ts1, {"type": "check_run", ...}),
            (ts2, {"type": "check_run", ...}),  # Within 60s of ts1
        ])
        # Returns grouped timeline with collapsed check_runs
    """
    if not events:
        return []

    timeline: list[dict[str, Any]] = []
    current_group: list[dict[str, Any]] = []
    current_timestamp: datetime | None = None

    for event_time, event_data in events:
        # Start new group if first event or outside grouping window
        if current_timestamp is None or (event_time - current_timestamp) > timedelta(seconds=GROUPING_WINDOW_SECONDS):
            # Save previous group if exists
            if current_group and current_timestamp is not None:
                timeline.append(_create_timeline_group(current_timestamp, current_group))

            # Start new group
            current_group = [event_data]
            current_timestamp = event_time
        else:
            # Add to current group (within window)
            current_group.append(event_data)

    # Add final group
    if current_group and current_timestamp is not None:
        timeline.append(_create_timeline_group(current_timestamp, current_group))

    return timeline


def _create_timeline_group(timestamp: datetime, events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create timeline group with event collapsing for same-type events.

    Collapses multiple same-type events into a summary for better readability.
    For example, 15 check_run events become "15 check runs (12 passed, 3 failed)".

    Args:
        timestamp: Group timestamp
        events: Events in this group

    Returns:
        Timeline group with events and optional collapsed summary
    """
    group: dict[str, Any] = {
        "timestamp": timestamp.isoformat(),
        "events": events,
        "collapsed": None,
    }

    # Count event types
    event_type_counts: dict[str, int] = {}
    for event in events:
        event_type = event["type"]
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

    # Collapse if multiple same-type events
    for event_type, count in event_type_counts.items():
        if count > 1:
            # Special handling for check_runs
            if event_type == "check_run":
                success_count = sum(
                    1 for e in events if e["type"] == "check_run" and e["details"].get("conclusion") == "success"
                )
                failure_count = sum(
                    1
                    for e in events
                    if e["type"] == "check_run" and e["details"].get("conclusion") in ("failure", "cancelled")
                )
                group["collapsed"] = {
                    "type": event_type,
                    "count": count,
                    "summary": f"{count} check runs ({success_count} passed, {failure_count} failed)",
                }
            else:
                # Generic collapse for other event types
                group["collapsed"] = {
                    "type": event_type,
                    "count": count,
                    "summary": f"{count} {event_type} events",
                }
            break  # Only collapse one type per group

    return group


def _flatten_timeline_for_js(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Flatten timeline groups into individual events for JavaScript frontend.

    Transforms the grouped timeline structure into a flat list of events
    with the format expected by the JS frontend:
    - event_type: Type of event (pr_opened, commit, review_approved, etc.)
    - timestamp: ISO timestamp
    - description: Human-readable description
    - children: For grouped events like check_runs, list of child events

    Args:
        timeline: Grouped timeline from _group_timeline_events

    Returns:
        Flat list of events for JS consumption
    """
    flat_events: list[dict[str, Any]] = []

    for group in timeline:
        timestamp = group["timestamp"]
        events = group["events"]

        # Group check_runs by head_sha (commit)
        check_runs = [e for e in events if e["type"] == "check_run"]
        other_events = [e for e in events if e["type"] != "check_run"]

        # Add non-check_run events individually
        for event in other_events:
            flat_event = _convert_event_for_js(event, timestamp)
            flat_events.append(flat_event)

        # Group check_runs by head_sha
        if check_runs:
            check_runs_by_sha: dict[str, list[dict[str, Any]]] = {}
            for cr in check_runs:
                sha = cr["details"].get("head_sha", "unknown")
                if sha not in check_runs_by_sha:
                    check_runs_by_sha[sha] = []
                check_runs_by_sha[sha].append(cr)

            # Create grouped event for each commit's check_runs
            for sha, sha_check_runs in check_runs_by_sha.items():
                success_count = sum(1 for cr in sha_check_runs if cr["details"].get("conclusion") == "success")
                failure_count = sum(
                    1 for cr in sha_check_runs if cr["details"].get("conclusion") in ("failure", "cancelled")
                )
                children = []
                for cr in sha_check_runs:
                    children.append({
                        "name": cr["details"].get("name", "unknown"),
                        "conclusion": cr["details"].get("conclusion"),
                        "status": cr["details"].get("status"),
                    })

                if len(sha_check_runs) > 1:
                    flat_events.append({
                        "event_type": "check_run",
                        "timestamp": timestamp,
                        "description": f"{len(sha_check_runs)} Check Runs ({success_count} ✓, {failure_count} ✗)",
                        "commit": sha,
                        "children": children,
                    })
                else:
                    flat_events.append(_convert_event_for_js(sha_check_runs[0], timestamp))

    return flat_events


def _convert_event_for_js(event: dict[str, Any], timestamp: str) -> dict[str, Any]:
    """
    Convert a single internal event to JS frontend format.

    Args:
        event: Internal event dict with type, actor, details
        timestamp: ISO timestamp string

    Returns:
        Event dict for JS frontend
    """
    event_type = event["type"]
    actor = event.get("actor", "unknown")
    details = event.get("details", {})

    # Build description based on event type
    description = _build_event_description(event_type, actor, details)

    result: dict[str, Any] = {
        "event_type": event_type,
        "timestamp": timestamp,
        "description": description,
    }

    # Add check_run details if applicable
    if event_type == "check_run":
        result["name"] = details.get("name", "unknown")
        result["conclusion"] = details.get("conclusion")
        result["status"] = details.get("status")

    # Add comment details if applicable
    if event_type == "comment":
        result["body"] = details.get("body", "")
        result["truncated"] = details.get("truncated", False)
        result["url"] = details.get("url", "")

    return result


def _build_event_description(event_type: str, actor: str, details: dict[str, Any]) -> str:
    """Build human-readable description for an event."""
    descriptions: dict[str, str] = {
        "pr_opened": f"@{actor} opened this pull request",
        "pr_closed": f"@{actor} closed this pull request",
        "pr_merged": f"@{details.get('merged_by', actor)} merged this pull request",
        "pr_reopened": f"@{actor} reopened this pull request",
        "commit": f"@{actor} pushed commits",
        "ready_for_review": f"@{actor} marked ready for review",
        "review_requested": f"@{actor} requested review from @{details.get('reviewer', 'unknown')}",
        "review_approved": f"@{actor} approved",
        "review_changes": f"@{actor} requested changes",
        "review_comment": f"@{actor} commented",
        "comment": f"@{actor} commented",
        "label_added": f"@{actor} added label '{details.get('label', '')}'",
        "label_removed": f"@{actor} removed label '{details.get('label', '')}'",
        "verified": f"@{actor} verified",
        "approved_label": f"@{actor} approved via label",
        "lgtm": f"@{actor} gave LGTM",
        "check_run": f"{details.get('name', 'Check')} - {details.get('conclusion', 'running')}",
    }
    return descriptions.get(event_type, f"{event_type} by @{actor}")


async def get_pr_story(
    db_manager: DatabaseManager,
    repository: str,
    pr_number: int,
) -> dict[str, Any] | None:
    """
    Get complete PR story/timeline from webhook events.

    Aggregates all webhook events related to a PR into a comprehensive timeline
    including PR state changes, commits, reviews, labels, check runs, and comments.
    Events are grouped by time windows and collapsed for readability.

    Args:
        db_manager: Database connection manager
        repository: Repository in org/repo format
        pr_number: PR number within repository

    Returns:
        Complete PR story dictionary with timeline and summary, or None if PR not found

    Raises:
        ValueError: If database pool not initialized
        asyncpg.PostgresError: If database query fails

    Example:
        story = await get_pr_story(db_manager, "myorg/myrepo", 123)
        if story:
            print(f"PR #{story['pr']['number']}: {story['pr']['title']}")
            print(f"State: {story['pr']['state']}")
            print(f"Timeline events: {len(story['events'])}")
            print(f"Check runs: {story['summary']['total_check_runs']}")
    """
    LOGGER.debug("Fetching PR story for %s #%s", repository, pr_number)

    # Query all PR-related webhook events
    pr_events_query = """
        SELECT
            delivery_id,
            event_type,
            action,
            payload,
            created_at
        FROM webhooks
        WHERE repository = $1 AND pr_number = $2
        ORDER BY created_at ASC
    """

    pr_events = await db_manager.fetch(pr_events_query, repository, pr_number)

    if not pr_events:
        LOGGER.debug("No webhook events found for %s #%s", repository, pr_number)
        return None

    # Extract PR metadata from pull_request events
    # - Title, author, created_at from FIRST event (original values)
    # - State, merged_at, closed_at from LAST event (current values)
    # - Collect ALL head_sha values for check_run matching
    pr_title = ""
    pr_state = "unknown"
    pr_author = "unknown"
    pr_created_at: datetime | None = None
    pr_merged_at: datetime | None = None
    pr_closed_at: datetime | None = None
    all_head_shas: set[str] = set()
    first_pr_event_seen = False

    for row in pr_events:
        if row["event_type"] == "pull_request":
            payload = _parse_payload(row["payload"])
            pr_data = payload.get("pull_request", {})

            # First event: get original title, author, created_at
            if not first_pr_event_seen:
                pr_title = pr_data.get("title", "")
                pr_author = pr_data.get("user", {}).get("login", "unknown")
                created_str = pr_data.get("created_at")
                if created_str:
                    pr_created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                first_pr_event_seen = True

            # Every event: update current state (last one wins)
            pr_state = pr_data.get("state", "unknown")

            # Collect all head_sha values for check_run matching
            head_sha = pr_data.get("head", {}).get("sha")
            if head_sha:
                all_head_shas.add(head_sha)

            # Parse timestamps that change over time
            merged_str = pr_data.get("merged_at")
            if merged_str:
                pr_merged_at = datetime.fromisoformat(merged_str.replace("Z", "+00:00"))

            closed_str = pr_data.get("closed_at")
            if closed_str:
                pr_closed_at = datetime.fromisoformat(closed_str.replace("Z", "+00:00"))

            # Check if merged
            if pr_data.get("merged", False):
                pr_state = "merged"

    # Extract timeline events from webhook payloads
    timeline_events: list[tuple[datetime, dict[str, Any]]] = []

    for row in pr_events:
        payload = _parse_payload(row["payload"])
        events = _extract_event_from_payload(
            row["event_type"],
            row["action"],
            payload,
            row["delivery_id"],
        )
        for event in events:
            timeline_events.append((row["created_at"], event))

    # Get check_run events and status events for ALL commits in this PR
    # Both check_runs and status events should be grouped by head_sha
    # Collect both into a unified structure keyed by (name, head_sha)
    if all_head_shas:
        # Define queries for parallel execution
        check_run_query = """
            SELECT
                delivery_id,
                payload,
                created_at
            FROM webhooks
            WHERE event_type = 'check_run'
              AND repository = $1
              AND payload->'check_run'->>'head_sha' = ANY($2)
            ORDER BY created_at ASC
        """

        status_query = """
            SELECT
                delivery_id,
                payload,
                created_at
            FROM webhooks
            WHERE event_type = 'status'
              AND repository = $1
              AND payload->>'sha' = ANY($2)
            ORDER BY created_at ASC
        """

        # Execute both queries in parallel for better performance
        head_sha_list = list(all_head_shas)
        check_run_events, status_events = await asyncio.gather(
            db_manager.fetch(check_run_query, repository, head_sha_list),
            db_manager.fetch(status_query, repository, head_sha_list),
        )

        # Deduplicate: keep only the latest event for each (name, head_sha) pair
        seen_check_runs: dict[tuple[str, str], dict[str, Any]] = {}
        for row in check_run_events:
            payload = _parse_payload(row["payload"])
            check_run = payload.get("check_run", {})
            check_name = check_run.get("name", "unknown")
            check_head_sha = check_run.get("head_sha", "")
            status = check_run.get("status", "unknown")
            conclusion = check_run.get("conclusion")

            # For queued/in_progress checks, conclusion is None (pending)
            # This is valid and should be shown
            # Key by (name, head_sha) - later events overwrite earlier ones
            key = (check_name, check_head_sha)
            seen_check_runs[key] = {
                "created_at": row["created_at"],
                "delivery_id": row["delivery_id"],
                "name": check_name,
                "status": status,
                "conclusion": conclusion,
                "head_sha": check_head_sha[:7] if check_head_sha else "",
            }

        # Process status events and merge them into seen_check_runs
        # This ensures status events are grouped with check_runs by head_sha
        for row in status_events:
            payload = _parse_payload(row["payload"])
            context = payload.get("context", "unknown")
            sha = payload.get("sha", "")
            state = payload.get("state", "unknown")  # pending, success, failure, error

            # Map status state to check_run conclusion format
            if state == "success":
                conclusion = "success"
            elif state in ("failure", "error"):
                conclusion = "failure"
            else:
                conclusion = None  # pending

            # Use the same key structure as check_runs: (name, head_sha)
            key = (context, sha)

            # Only add if this is the latest status for this (context, sha) pair
            # If a check_run with the same name exists, compare timestamps
            if key in seen_check_runs:
                # Update if this status is newer
                if row["created_at"] > seen_check_runs[key]["created_at"]:
                    seen_check_runs[key] = {
                        "created_at": row["created_at"],
                        "delivery_id": row["delivery_id"],
                        "name": context,
                        "status": "completed" if state in ("success", "failure", "error") else "pending",
                        "conclusion": conclusion,
                        "head_sha": sha[:7] if sha else "",
                    }
            else:
                # Add new status event
                seen_check_runs[key] = {
                    "created_at": row["created_at"],
                    "delivery_id": row["delivery_id"],
                    "name": context,
                    "status": "completed" if state in ("success", "failure", "error") else "pending",
                    "conclusion": conclusion,
                    "head_sha": sha[:7] if sha else "",
                }

        # Group all check_runs (both from check_run events and status events) by head_sha
        # Then add them to timeline grouped by commit
        checks_by_sha: dict[str, list[dict[str, Any]]] = {}
        for check_data in seen_check_runs.values():
            sha = check_data["head_sha"]
            if sha not in checks_by_sha:
                checks_by_sha[sha] = []
            checks_by_sha[sha].append(check_data)

        # Add grouped check_runs to timeline (one event per commit)
        # Use the latest timestamp from all checks for that commit
        for checks in checks_by_sha.values():
            # Find the latest timestamp for this commit's checks
            latest_time = max(check["created_at"] for check in checks)

            # Add all checks for this commit as a single timeline event
            for check_data in checks:
                timeline_events.append((
                    latest_time,  # Use latest timestamp so they group together
                    {
                        "type": "check_run",
                        "actor": "github-actions",
                        "details": {
                            "name": check_data["name"],
                            "status": check_data["status"],
                            "conclusion": check_data["conclusion"],
                            "head_sha": check_data["head_sha"],
                        },
                        "delivery_id": check_data["delivery_id"],
                    },
                ))

    # Sort all events by timestamp
    timeline_events.sort(key=lambda x: x[0])

    # Group events into timeline
    timeline = _group_timeline_events(timeline_events)

    # Calculate summary statistics
    check_runs_summary = {"total": 0, "success": 0, "failure": 0}
    reviews_summary = {"total": 0, "approved": 0, "changes_requested": 0}
    # Count commits as number of unique head_shas (each represents a push/commit update)
    commits_count = len(all_head_shas)
    comments_count = 0

    for _, event in timeline_events:
        event_type = event["type"]

        if event_type == "check_run":
            check_runs_summary["total"] += 1
            conclusion = event["details"].get("conclusion")
            if conclusion == "success":
                check_runs_summary["success"] += 1
            elif conclusion in ("failure", "cancelled"):
                check_runs_summary["failure"] += 1
            # else: pending (conclusion is None) - don't count as success or failure

        elif event_type in ("review_approved", "review_changes", "review_comment"):
            reviews_summary["total"] += 1
            if event_type == "review_approved":
                reviews_summary["approved"] += 1
            elif event_type == "review_changes":
                reviews_summary["changes_requested"] += 1

        elif event_type == "comment":
            comments_count += 1

    # Transform summary to JS expected format
    summary: dict[str, Any] = {
        "total_commits": commits_count,
        "total_reviews": reviews_summary["total"],
        "total_check_runs": check_runs_summary["total"],
        "total_comments": comments_count,
    }

    # Transform timeline groups to flat events for JS
    flat_events = _flatten_timeline_for_js(timeline)

    return {
        "pr": {
            "number": pr_number,
            "repository": repository,
            "title": pr_title,
            "state": pr_state,
            "merged": pr_state == "merged",
            "author": pr_author,
            "created_at": pr_created_at.isoformat() if pr_created_at else None,
            "merged_at": pr_merged_at.isoformat() if pr_merged_at else None,
            "closed_at": pr_closed_at.isoformat() if pr_closed_at else None,
        },
        "events": flat_events,
        "summary": summary,
    }
