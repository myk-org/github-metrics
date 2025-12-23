"""API routes for repository maintainers."""

from typing import TypedDict

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from simple_logger.logger import get_logger

from backend.sig_teams import get_sig_teams_config

# Module-level logger
LOGGER = get_logger(name="backend.routes.api.maintainers")

router = APIRouter(prefix="/api/metrics")


class MaintainersResponse(TypedDict):
    """Response structure for maintainers endpoint."""

    maintainers: dict[str, list[str]]
    all_maintainers: list[str]


@router.get("/maintainers", operation_id="get_maintainers")
async def get_maintainers() -> MaintainersResponse:
    """Get list of maintainers grouped by repository.

    Returns maintainers configuration from SIG teams YAML file.
    Raises 503 Service Unavailable if SIG teams config is not loaded.

    **Response Format:**
    ```json
    {
      "maintainers": {
        "org/repo1": ["maintainer1", "maintainer2"],
        "org/repo2": ["maintainer3"]
      },
      "all_maintainers": ["maintainer1", "maintainer2", "maintainer3"]
    }
    ```

    **Returns:**
    - `maintainers`: Dictionary mapping repositories to their maintainers
    - `all_maintainers`: Deduplicated sorted list of all maintainers across repositories

    **Error Conditions:**
    - 503: SIG teams configuration not loaded
    """
    config = get_sig_teams_config()

    if not config.is_loaded:
        LOGGER.warning("SIG teams configuration not loaded - cannot retrieve maintainers")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SIG teams configuration not loaded",
        )

    # Build maintainers dictionary per repository
    maintainers_by_repo: dict[str, list[str]] = {}
    for repository in config.repositories:
        repo_maintainers = config.get_maintainers(repository)
        if repo_maintainers:
            maintainers_by_repo[repository] = repo_maintainers

    # Get all maintainers (deduplicated and sorted)
    all_maintainers = config.get_all_maintainers()

    return {
        "maintainers": maintainers_by_repo,
        "all_maintainers": all_maintainers,
    }
