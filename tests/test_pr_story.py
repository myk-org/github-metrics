"""Tests for PR story endpoint and aggregation.

Tests comprehensive PR timeline aggregation including:
- Event extraction from webhook payloads
- Event grouping and parallel detection
- Timeline building with collapsed events
- PR story endpoint responses
- Label detection (verified, approve, lgtm)
- Check run matching via head_sha
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from github_metrics.app import app
from github_metrics.pr_story import (
    GROUPING_WINDOW_SECONDS,
    _create_timeline_group,
    _extract_event_from_payload,
    _group_timeline_events,
    get_pr_story,
)

# Test webhook secret for unit tests
TEST_WEBHOOK_SECRET = "test_secret_for_unit_tests"  # pragma: allowlist secret


class TestPRStoryEndpoint:
    """Tests for /api/metrics/pr-story/{repository}/{pr_number} endpoint."""

    def test_get_pr_story_success(self) -> None:
        """Test successful PR story retrieval."""
        # Mock PR webhook event
        mock_pr_event = {
            "delivery_id": "test-delivery-1",
            "event_type": "pull_request",
            "action": "opened",
            "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            "payload": {
                "sender": {"login": "testuser"},
                "pull_request": {
                    "number": 123,
                    "title": "Test PR",
                    "state": "open",
                    "user": {"login": "testuser"},
                    "head": {"sha": "abc123def456"},  # pragma: allowlist secret
                    "created_at": "2024-01-15T10:00:00Z",
                    "merged_at": None,
                    "closed_at": None,
                    "merged": False,
                },
            },
        }

        with patch("github_metrics.app.db_manager") as mock_db:
            # First call returns PR events, second/third calls return empty check_run/status events
            mock_db.fetch = AsyncMock(side_effect=[[mock_pr_event], [], []])

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pr"]["number"] == 123
            assert data["pr"]["repository"] == "testorg/testrepo"
            assert data["pr"]["title"] == "Test PR"
            assert data["pr"]["state"] == "open"
            assert data["pr"]["author"] == "testuser"
            assert "events" in data
            assert "summary" in data

    def test_get_pr_story_not_found(self) -> None:
        """Test PR story returns 404 when no webhooks exist for PR."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(return_value=[])

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/999")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    def test_get_pr_story_database_unavailable(self) -> None:
        """Test PR story returns 500 when database unavailable."""
        with patch("github_metrics.app.db_manager", None):
            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_pr_story_database_error(self) -> None:
        """Test PR story handles database errors."""
        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=Exception("Database error"))

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_pr_story_invalid_pr_number(self) -> None:
        """Test PR story returns 400 for invalid PR numbers."""
        with patch("github_metrics.app.db_manager"):
            client = TestClient(app)

            # Test negative PR number
            response = client.get("/api/metrics/pr-story/testorg/testrepo/-1")
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PR number must be positive" in response.json()["detail"]

            # Test zero PR number
            response = client.get("/api/metrics/pr-story/testorg/testrepo/0")
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PR number must be positive" in response.json()["detail"]

    def test_get_pr_story_with_merged_pr(self) -> None:
        """Test PR story for merged PR."""
        mock_pr_event = {
            "delivery_id": "test-delivery-merged",
            "event_type": "pull_request",
            "action": "closed",
            "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            "payload": {
                "sender": {"login": "testuser"},
                "pull_request": {
                    "number": 123,
                    "title": "Merged PR",
                    "state": "closed",
                    "user": {"login": "testuser"},
                    "head": {"sha": "abc123"},  # pragma: allowlist secret
                    "created_at": "2024-01-15T10:00:00Z",
                    "merged_at": "2024-01-15T12:00:00Z",
                    "closed_at": "2024-01-15T12:00:00Z",
                    "merged": True,
                    "merged_by": {"login": "reviewer"},
                },
            },
        }

        with patch("github_metrics.app.db_manager") as mock_db:
            # First call returns PR events, second/third calls return empty check_run/status events
            mock_db.fetch = AsyncMock(side_effect=[[mock_pr_event], [], []])

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pr"]["state"] == "merged"
            assert data["pr"]["merged_at"] == "2024-01-15T12:00:00+00:00"


class TestEventExtraction:
    """Tests for _extract_event_from_payload function."""

    def test_extract_pr_opened_event(self) -> None:
        """Test extraction of PR opened event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {
                "title": "Test PR",
                "draft": False,
            },
        }

        events = _extract_event_from_payload("pull_request", "opened", payload, "delivery-1")

        assert len(events) == 1
        assert events[0]["type"] == "pr_opened"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["title"] == "Test PR"
        assert events[0]["delivery_id"] == "delivery-1"

    def test_extract_pr_merged_event(self) -> None:
        """Test extraction of PR merged event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {
                "merged": True,
                "merged_by": {"login": "reviewer"},
            },
        }

        events = _extract_event_from_payload("pull_request", "closed", payload, "delivery-2")

        assert len(events) == 1
        assert events[0]["type"] == "pr_merged"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["merged_by"] == "reviewer"

    def test_extract_pr_closed_event(self) -> None:
        """Test extraction of PR closed (not merged) event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {
                "merged": False,
            },
        }

        events = _extract_event_from_payload("pull_request", "closed", payload, "delivery-3")

        assert len(events) == 1
        assert events[0]["type"] == "pr_closed"
        assert events[0]["actor"] == "testuser"

    def test_extract_pr_reopened_event(self) -> None:
        """Test extraction of PR reopened event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {},
        }

        events = _extract_event_from_payload("pull_request", "reopened", payload, "delivery-4")

        assert len(events) == 1
        assert events[0]["type"] == "pr_reopened"
        assert events[0]["actor"] == "testuser"

    def test_extract_synchronize_commit_event(self) -> None:
        """Test extraction of commit/synchronize event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {
                "commits": 5,
                "head": {"sha": "abc123"},  # pragma: allowlist secret
            },
        }

        events = _extract_event_from_payload("pull_request", "synchronize", payload, "delivery-5")

        assert len(events) == 1
        assert events[0]["type"] == "commit"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["commits"] == 5
        assert events[0]["details"]["head_sha"] == "abc123"

    def test_extract_ready_for_review_event(self) -> None:
        """Test extraction of ready_for_review event."""
        payload = {
            "sender": {"login": "testuser"},
            "pull_request": {},
        }

        events = _extract_event_from_payload("pull_request", "ready_for_review", payload, "delivery-6")

        assert len(events) == 1
        assert events[0]["type"] == "ready_for_review"
        assert events[0]["actor"] == "testuser"

    def test_extract_review_requested_event(self) -> None:
        """Test extraction of review_requested event."""
        payload = {
            "sender": {"login": "testuser"},
            "requested_reviewer": {"login": "reviewer1"},
        }

        events = _extract_event_from_payload("pull_request", "review_requested", payload, "delivery-7")

        assert len(events) == 1
        assert events[0]["type"] == "review_requested"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["reviewer"] == "reviewer1"

    def test_extract_verified_label_event(self) -> None:
        """Test extraction of verified label (/verified)."""
        payload = {
            "sender": {"login": "testuser"},
            "label": {"name": "verified"},
        }

        events = _extract_event_from_payload("pull_request", "labeled", payload, "delivery-8")

        assert len(events) == 1
        assert events[0]["type"] == "verified"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["label"] == "verified"

    def test_extract_approved_label_event(self) -> None:
        """Test extraction of approved label (/approve)."""
        payload = {
            "sender": {"login": "bot"},
            "label": {"name": "approved-reviewer1"},
        }

        events = _extract_event_from_payload("pull_request", "labeled", payload, "delivery-9")

        assert len(events) == 1
        assert events[0]["type"] == "approved_label"
        assert events[0]["actor"] == "reviewer1"
        assert events[0]["details"]["label"] == "approved-reviewer1"

    def test_extract_lgtm_label_event(self) -> None:
        """Test extraction of lgtm label (/lgtm)."""
        payload = {
            "sender": {"login": "bot"},
            "label": {"name": "lgtm-reviewer2"},
        }

        events = _extract_event_from_payload("pull_request", "labeled", payload, "delivery-10")

        assert len(events) == 1
        assert events[0]["type"] == "lgtm"
        assert events[0]["actor"] == "reviewer2"
        assert events[0]["details"]["label"] == "lgtm-reviewer2"

    def test_extract_generic_label_added_event(self) -> None:
        """Test extraction of generic label added event."""
        payload = {
            "sender": {"login": "testuser"},
            "label": {"name": "bug"},
        }

        events = _extract_event_from_payload("pull_request", "labeled", payload, "delivery-11")

        assert len(events) == 1
        assert events[0]["type"] == "label_added"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["label"] == "bug"

    def test_extract_label_removed_event(self) -> None:
        """Test extraction of label removed event."""
        payload = {
            "sender": {"login": "testuser"},
            "label": {"name": "in-progress"},
        }

        events = _extract_event_from_payload("pull_request", "unlabeled", payload, "delivery-12")

        assert len(events) == 1
        assert events[0]["type"] == "label_removed"
        assert events[0]["actor"] == "testuser"
        assert events[0]["details"]["label"] == "in-progress"

    def test_extract_review_approved_event(self) -> None:
        """Test extraction of review approved event."""
        payload = {
            "sender": {"login": "testuser"},
            "review": {
                "state": "approved",
                "user": {"login": "reviewer1"},
            },
        }

        events = _extract_event_from_payload("pull_request_review", "submitted", payload, "delivery-13")

        assert len(events) == 1
        assert events[0]["type"] == "review_approved"
        assert events[0]["actor"] == "reviewer1"

    def test_extract_review_changes_requested_event(self) -> None:
        """Test extraction of review changes_requested event."""
        payload = {
            "sender": {"login": "testuser"},
            "review": {
                "state": "changes_requested",
                "user": {"login": "reviewer2"},
            },
        }

        events = _extract_event_from_payload("pull_request_review", "submitted", payload, "delivery-14")

        assert len(events) == 1
        assert events[0]["type"] == "review_changes"
        assert events[0]["actor"] == "reviewer2"

    def test_extract_review_comment_event(self) -> None:
        """Test extraction of review comment event."""
        payload = {
            "sender": {"login": "testuser"},
            "review": {
                "state": "commented",
                "user": {"login": "reviewer3"},
            },
        }

        events = _extract_event_from_payload("pull_request_review", "submitted", payload, "delivery-15")

        assert len(events) == 1
        assert events[0]["type"] == "review_comment"
        assert events[0]["actor"] == "reviewer3"

    def test_extract_issue_comment_event(self) -> None:
        """Test extraction of issue comment event for PR."""
        payload = {
            "sender": {"login": "testuser"},
            "issue": {
                "number": 123,
                "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/123"},
            },
            "comment": {
                "body": "This is a test comment with more than 200 characters" * 10,
            },
        }

        events = _extract_event_from_payload("issue_comment", "created", payload, "delivery-16")

        assert len(events) == 1
        assert events[0]["type"] == "comment"
        assert events[0]["actor"] == "testuser"
        assert len(events[0]["details"]["body"]) <= 500

    def test_extract_issue_comment_non_pr(self) -> None:
        """Test issue comment without pull_request field is ignored."""
        payload = {
            "sender": {"login": "testuser"},
            "issue": {
                "number": 123,
                # No pull_request field
            },
            "comment": {
                "body": "This is a regular issue comment",
            },
        }

        events = _extract_event_from_payload("issue_comment", "created", payload, "delivery-17")

        assert len(events) == 0

    def test_extract_unknown_event_type(self) -> None:
        """Test unknown event types return empty list."""
        payload = {
            "sender": {"login": "testuser"},
        }

        events = _extract_event_from_payload("unknown_event", "unknown_action", payload, "delivery-18")

        assert len(events) == 0


class TestEventGrouping:
    """Tests for _group_timeline_events function."""

    def test_group_timeline_events_empty_list(self) -> None:
        """Test grouping empty event list returns empty timeline."""
        timeline = _group_timeline_events([])

        assert timeline == []

    def test_group_timeline_events_single_event(self) -> None:
        """Test grouping single event."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        event = {"type": "pr_opened", "actor": "testuser", "details": {}}

        timeline = _group_timeline_events([(base_time, event)])

        assert len(timeline) == 1
        assert timeline[0]["timestamp"] == base_time.isoformat()
        assert len(timeline[0]["events"]) == 1
        assert timeline[0]["events"][0]["type"] == "pr_opened"

    def test_group_timeline_events_within_window(self) -> None:
        """Test events within 60-second window are grouped together."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        event1 = {"type": "check_run", "actor": "github-actions", "details": {"conclusion": "success"}}
        event2 = {"type": "check_run", "actor": "github-actions", "details": {"conclusion": "success"}}

        # Events 30 seconds apart (within GROUPING_WINDOW_SECONDS)
        timeline = _group_timeline_events([
            (base_time, event1),
            (base_time + timedelta(seconds=30), event2),
        ])

        assert len(timeline) == 1
        assert len(timeline[0]["events"]) == 2

    def test_group_timeline_events_outside_window(self) -> None:
        """Test events outside 60-second window create separate groups."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        event1 = {"type": "pr_opened", "actor": "testuser", "details": {}}
        event2 = {"type": "commit", "actor": "testuser", "details": {}}

        # Events 61 seconds apart (outside GROUPING_WINDOW_SECONDS)
        timeline = _group_timeline_events([
            (base_time, event1),
            (base_time + timedelta(seconds=GROUPING_WINDOW_SECONDS + 1), event2),
        ])

        assert len(timeline) == 2
        assert len(timeline[0]["events"]) == 1
        assert len(timeline[1]["events"]) == 1

    def test_group_timeline_events_chronological_order(self) -> None:
        """Test timeline maintains chronological order."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        events = [
            (base_time, {"type": "pr_opened", "actor": "user1", "details": {}}),
            (base_time + timedelta(minutes=5), {"type": "commit", "actor": "user1", "details": {}}),
            (base_time + timedelta(minutes=10), {"type": "review_approved", "actor": "user2", "details": {}}),
        ]

        timeline = _group_timeline_events(events)

        assert len(timeline) == 3
        # Verify timestamps are in order
        timestamps = [datetime.fromisoformat(group["timestamp"]) for group in timeline]
        assert timestamps == sorted(timestamps)


class TestTimelineGroupCreation:
    """Tests for _create_timeline_group function."""

    def test_create_timeline_group_single_event(self) -> None:
        """Test creating timeline group with single event."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        event = {"type": "pr_opened", "actor": "testuser", "details": {}}

        group = _create_timeline_group(timestamp, [event])

        assert group["timestamp"] == timestamp.isoformat()
        assert len(group["events"]) == 1
        assert group["collapsed"] is None

    def test_create_timeline_group_collapsed_check_runs(self) -> None:
        """Test collapsing multiple check_run events."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        events = [
            {"type": "check_run", "actor": "ci", "details": {"conclusion": "success"}},
            {"type": "check_run", "actor": "ci", "details": {"conclusion": "success"}},
            {"type": "check_run", "actor": "ci", "details": {"conclusion": "failure"}},
        ]

        group = _create_timeline_group(timestamp, events)

        assert group["collapsed"] is not None
        assert group["collapsed"]["type"] == "check_run"
        assert group["collapsed"]["count"] == 3
        assert "2 passed, 1 failed" in group["collapsed"]["summary"]

    def test_create_timeline_group_collapsed_generic_events(self) -> None:
        """Test collapsing multiple generic events."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        events = [
            {"type": "label_added", "actor": "bot", "details": {"label": "bug"}},
            {"type": "label_added", "actor": "bot", "details": {"label": "priority"}},
        ]

        group = _create_timeline_group(timestamp, events)

        assert group["collapsed"] is not None
        assert group["collapsed"]["type"] == "label_added"
        assert group["collapsed"]["count"] == 2
        assert "2 label_added events" in group["collapsed"]["summary"]

    def test_create_timeline_group_mixed_events_no_collapse(self) -> None:
        """Test mixed event types without collapsing."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        events = [
            {"type": "pr_opened", "actor": "user1", "details": {}},
            {"type": "commit", "actor": "user1", "details": {}},
            {"type": "review_requested", "actor": "user1", "details": {}},
        ]

        group = _create_timeline_group(timestamp, events)

        assert group["collapsed"] is None


class TestGetPRStory:
    """Tests for get_pr_story function."""

    @pytest.mark.asyncio
    async def test_get_pr_story_success(self) -> None:
        """Test successful PR story retrieval with full timeline."""
        mock_db = AsyncMock()

        # Mock PR webhook events
        mock_events = [
            {
                "delivery_id": "delivery-1",
                "event_type": "pull_request",
                "action": "opened",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "payload": {
                    "sender": {"login": "testuser"},
                    "pull_request": {
                        "number": 123,
                        "title": "Test PR",
                        "state": "open",
                        "user": {"login": "testuser"},
                        "head": {"sha": "abc123"},  # pragma: allowlist secret
                        "created_at": "2024-01-15T10:00:00Z",
                        "merged_at": None,
                        "closed_at": None,
                        "merged": False,
                    },
                },
            },
            {
                "delivery_id": "delivery-2",
                "event_type": "pull_request_review",
                "action": "submitted",
                "created_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "payload": {
                    "sender": {"login": "reviewer"},
                    "review": {
                        "state": "approved",
                        "user": {"login": "reviewer"},
                    },
                },
            },
        ]

        # First call returns PR events, second/third calls return empty check_run/status events
        mock_db.fetch = AsyncMock(side_effect=[mock_events, [], []])

        story = await get_pr_story(mock_db, "testorg/testrepo", 123)

        assert story is not None
        assert story["pr"]["number"] == 123
        assert story["pr"]["repository"] == "testorg/testrepo"
        assert story["pr"]["title"] == "Test PR"
        assert story["pr"]["state"] == "open"
        assert story["pr"]["author"] == "testuser"
        assert len(story["events"]) == 2

    @pytest.mark.asyncio
    async def test_get_pr_story_not_found(self) -> None:
        """Test get_pr_story returns None when no events found."""
        mock_db = AsyncMock()
        mock_db.fetch = AsyncMock(return_value=[])

        story = await get_pr_story(mock_db, "testorg/testrepo", 999)

        assert story is None

    @pytest.mark.asyncio
    async def test_get_pr_story_with_check_runs(self) -> None:
        """Test PR story includes check_run events matched by head_sha."""
        mock_db = AsyncMock()

        # PR event with head_sha
        pr_event = {
            "delivery_id": "delivery-1",
            "event_type": "pull_request",
            "action": "opened",
            "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            "payload": {
                "sender": {"login": "testuser"},
                "pull_request": {
                    "number": 123,
                    "title": "Test PR",
                    "state": "open",
                    "user": {"login": "testuser"},
                    "head": {"sha": "abc123"},  # pragma: allowlist secret
                    "created_at": "2024-01-15T10:00:00Z",
                    "merged_at": None,
                    "closed_at": None,
                    "merged": False,
                },
            },
        }

        # Check run event
        check_run_event = {
            "delivery_id": "delivery-2",
            "created_at": datetime(2024, 1, 15, 10, 5, 0, tzinfo=UTC),
            "payload": {
                "check_run": {
                    "name": "test-suite",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "abc123",  # pragma: allowlist secret
                },
            },
        }

        # First call returns PR events, second call returns check_run events, third call returns empty status events
        mock_db.fetch = AsyncMock(side_effect=[[pr_event], [check_run_event], []])

        story = await get_pr_story(mock_db, "testorg/testrepo", 123)

        assert story is not None
        assert story["summary"]["total_check_runs"] == 1

    @pytest.mark.asyncio
    async def test_get_pr_story_summary_statistics(self) -> None:
        """Test PR story calculates summary statistics correctly."""
        mock_db = AsyncMock()

        mock_events = [
            {
                "delivery_id": "delivery-1",
                "event_type": "pull_request",
                "action": "synchronize",
                "created_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                "payload": {
                    "sender": {"login": "testuser"},
                    "pull_request": {
                        "number": 123,
                        "title": "Test PR",
                        "state": "open",
                        "user": {"login": "testuser"},
                        "head": {"sha": "abc123"},  # pragma: allowlist secret
                        "created_at": "2024-01-15T10:00:00Z",
                        "merged_at": None,
                        "closed_at": None,
                        "merged": False,
                        "commits": 5,
                    },
                },
            },
            {
                "delivery_id": "delivery-2",
                "event_type": "pull_request_review",
                "action": "submitted",
                "created_at": datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                "payload": {
                    "sender": {"login": "reviewer"},
                    "review": {
                        "state": "approved",
                        "user": {"login": "reviewer"},
                    },
                },
            },
            {
                "delivery_id": "delivery-3",
                "event_type": "issue_comment",
                "action": "created",
                "created_at": datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                "payload": {
                    "sender": {"login": "commenter"},
                    "issue": {
                        "number": 123,
                        "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/123"},
                    },
                    "comment": {
                        "body": "Test comment",
                    },
                },
            },
        ]

        mock_db.fetch = AsyncMock(side_effect=[mock_events, [], []])

        story = await get_pr_story(mock_db, "testorg/testrepo", 123)

        assert story is not None
        assert story["summary"]["total_commits"] == 1
        assert story["summary"]["total_reviews"] == 1
        assert story["summary"]["total_comments"] == 1


class TestPRStoryEndpointIntegration:
    """Integration tests for PR story endpoint with complex scenarios."""

    def test_get_pr_story_complete_lifecycle(self) -> None:
        """Test PR story with complete PR lifecycle.

        Note: get_pr_story extracts metadata from FIRST pull_request event,
        so the first event must have the final state (merged=True).
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        mock_events = [
            {
                "delivery_id": "delivery-1",
                "event_type": "pull_request",
                "action": "closed",
                "created_at": base_time,
                "payload": {
                    "sender": {"login": "author"},
                    "pull_request": {
                        "number": 123,
                        "title": "Feature: Add new API",
                        "state": "closed",
                        "user": {"login": "author"},
                        "head": {"sha": "abc123"},  # pragma: allowlist secret
                        "created_at": "2024-01-15T10:00:00Z",
                        "merged_at": "2024-01-15T10:15:00Z",
                        "closed_at": "2024-01-15T10:15:00Z",
                        "merged": True,
                        "merged_by": {"login": "reviewer1"},
                        "draft": False,
                    },
                },
            },
            {
                "delivery_id": "delivery-2",
                "event_type": "pull_request",
                "action": "labeled",
                "created_at": base_time + timedelta(minutes=5),
                "payload": {
                    "sender": {"login": "bot"},
                    "label": {"name": "lgtm-reviewer1"},
                    "pull_request": {
                        "number": 123,
                        "title": "Feature: Add new API",
                        "state": "closed",
                        "user": {"login": "author"},
                        "head": {"sha": "abc123"},  # pragma: allowlist secret
                        "created_at": "2024-01-15T10:00:00Z",
                        "merged_at": "2024-01-15T10:15:00Z",
                        "closed_at": "2024-01-15T10:15:00Z",
                        "merged": True,
                    },
                },
            },
            {
                "delivery_id": "delivery-3",
                "event_type": "pull_request_review",
                "action": "submitted",
                "created_at": base_time + timedelta(minutes=10),
                "payload": {
                    "sender": {"login": "reviewer1"},
                    "review": {
                        "state": "approved",
                        "user": {"login": "reviewer1"},
                    },
                },
            },
        ]

        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_events, [], []])

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pr"]["state"] == "merged"
            assert len(data["events"]) == 3
            assert data["summary"]["total_reviews"] == 1

    def test_get_pr_story_with_all_label_types(self) -> None:
        """Test PR story correctly detects all label types."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)

        mock_events = [
            {
                "delivery_id": "delivery-1",
                "event_type": "pull_request",
                "action": "opened",
                "created_at": base_time,
                "payload": {
                    "sender": {"login": "author"},
                    "pull_request": {
                        "number": 123,
                        "title": "Test PR",
                        "state": "open",
                        "user": {"login": "author"},
                        "head": {"sha": "abc123"},  # pragma: allowlist secret
                        "created_at": "2024-01-15T10:00:00Z",
                        "merged_at": None,
                        "closed_at": None,
                        "merged": False,
                    },
                },
            },
            {
                "delivery_id": "delivery-2",
                "event_type": "pull_request",
                "action": "labeled",
                "created_at": base_time + timedelta(seconds=1),
                "payload": {
                    "sender": {"login": "bot"},
                    "label": {"name": "verified"},
                },
            },
            {
                "delivery_id": "delivery-3",
                "event_type": "pull_request",
                "action": "labeled",
                "created_at": base_time + timedelta(seconds=2),
                "payload": {
                    "sender": {"login": "bot"},
                    "label": {"name": "approved-reviewer1"},
                },
            },
            {
                "delivery_id": "delivery-4",
                "event_type": "pull_request",
                "action": "labeled",
                "created_at": base_time + timedelta(seconds=3),
                "payload": {
                    "sender": {"login": "bot"},
                    "label": {"name": "lgtm-reviewer2"},
                },
            },
        ]

        with patch("github_metrics.app.db_manager") as mock_db:
            mock_db.fetch = AsyncMock(side_effect=[mock_events, [], []])

            client = TestClient(app)
            response = client.get("/api/metrics/pr-story/testorg/testrepo/123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify all label events are in events
            event_types = []
            for event in data["events"]:
                event_types.append(event["event_type"])

            assert "verified" in event_types
            assert "approved_label" in event_types
            assert "lgtm" in event_types
