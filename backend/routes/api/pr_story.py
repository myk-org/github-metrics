"""API routes for PR story timeline."""

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.database import DatabaseManager
from backend.pr_story import get_pr_story

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.pr_story")

router = APIRouter(prefix="/api/metrics")

# Global database manager (set by app.py during lifespan)
db_manager: DatabaseManager | None = None


@router.get("/pr-story/{repository:path}/{pr_number}", operation_id="get_pr_story")
async def get_pr_story_endpoint(
    repository: str,
    pr_number: int,
) -> dict[str, Any]:
    """Get complete PR story timeline with all events.

    Aggregates all webhook events for a PR into a comprehensive timeline showing
    the complete story from creation to current state or merge/close.

    **Primary Use Cases:**
    - Visualize complete PR lifecycle and history
    - Track when specific events occurred (reviews, approvals, check runs)
    - Debug CI/CD issues by seeing check run history
    - Understand PR review and approval flow
    - Monitor time from creation to merge

    **Parameters:**
    - `repository` (str): Repository in org/repo format (e.g., "myorg/myrepo")
    - `pr_number` (int): Pull request number within the repository

    **Return Structure:**
    See the complete response structure in the module docstring.

    **Events Included:**
    - PR lifecycle (opened, closed, merged, reopened)
    - Code changes (commits/synchronize events)
    - Reviews (approved, changes requested, comments)
    - Labels (added, removed, verified, approved, lgtm)
    - Check runs (CI/CD pipeline status - matched via head_sha)
    - Comments and review requests

    **Event Grouping:**
    - Events within 60 seconds are grouped as parallel
    - Multiple same-type events are collapsed (e.g., "15 check runs")

    **Check Run Matching:**
    Since check_run webhooks don't include PR number, they are matched via
    the PR's head_sha. This ensures all CI/CD events are included.

    **Errors:**
    - 404: PR not found (no webhooks exist for this PR)
    - 500: Database connection error
    """
    if db_manager is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not available",
        )

    if pr_number <= 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="PR number must be positive",
        )

    try:
        story = await get_pr_story(db_manager, repository, pr_number)
        if story is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"PR #{pr_number} not found in {repository}",
            )
        return story
    except HTTPException:
        raise
    except Exception as ex:
        LOGGER.exception("Failed to fetch PR story for %s #%s", repository, pr_number)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch PR story",
        ) from ex
