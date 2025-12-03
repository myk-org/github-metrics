"""Playwright UI tests for the metrics dashboard Contributors page."""

from __future__ import annotations

import os

import pytest
from playwright.async_api import Page, expect

# Test constants
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8765/dashboard")
TIMEOUT = 10000  # 10 seconds timeout for UI interactions

pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


async def go_to_contributors(page: Page) -> None:
    """Navigate to Contributors page and wait for load."""
    await page.goto(f"{DASHBOARD_URL}#contributors", timeout=TIMEOUT)
    await page.wait_for_load_state("networkidle")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsPage:
    """Tests for Contributors page sections and functionality."""

    async def test_contributors_page_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Contributors page exists."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Navigate to contributors page
        contributors_nav = page_with_js_coverage.locator('.nav-item[data-page="contributors"]')
        await contributors_nav.click()

        # Wait for contributors page to be visible (event-based waiting)
        contributors_page = page_with_js_coverage.locator("#page-contributors")
        await expect(contributors_page).to_be_visible(timeout=5000)

    async def test_turnaround_by_repo_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Turnaround by Repository section exists."""
        await go_to_contributors(page_with_js_coverage)

        # Check if turnaround by repo section exists
        turnaround_by_repo = page_with_js_coverage.locator('.chart-container[data-section="turnaround-by-repo"]')
        await expect(turnaround_by_repo).to_be_attached()

    async def test_turnaround_by_reviewer_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Turnaround by Reviewer section exists."""
        await go_to_contributors(page_with_js_coverage)

        # Check if turnaround by reviewer section exists
        turnaround_by_reviewer = page_with_js_coverage.locator(
            '.chart-container[data-section="turnaround-by-reviewer"]'
        )
        await expect(turnaround_by_reviewer).to_be_attached()

    async def test_contributors_page_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons exist for Contributors page sections."""
        await go_to_contributors(page_with_js_coverage)

        # Contributors page sections that should have download buttons
        sections = [
            "turnaroundByRepo",
            "turnaroundByReviewer",
        ]

        for section in sections:
            # Each section should have 2 download buttons (CSV and JSON)
            csv_button = page_with_js_coverage.locator(f'.download-btn[data-section="{section}"][data-format="csv"]')
            json_button = page_with_js_coverage.locator(f'.download-btn[data-section="{section}"][data-format="json"]')

            await expect(csv_button).to_be_visible()
            await expect(json_button).to_be_visible()

    async def test_contributors_page_download_buttons_clickable(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons are clickable on Contributors page."""
        await go_to_contributors(page_with_js_coverage)

        # Test turnaround by repo CSV button
        turnaround_repo_csv = page_with_js_coverage.locator(
            '.download-btn[data-section="turnaroundByRepo"][data-format="csv"]'
        )
        await expect(turnaround_repo_csv).to_be_visible()
        await expect(turnaround_repo_csv).to_be_enabled()

        # Test turnaround by reviewer JSON button
        turnaround_reviewer_json = page_with_js_coverage.locator(
            '.download-btn[data-section="turnaroundByReviewer"][data-format="json"]'
        )
        await expect(turnaround_reviewer_json).to_be_visible()
        await expect(turnaround_reviewer_json).to_be_enabled()

    async def test_contributors_page_sections_have_collapse_buttons(self, page_with_js_coverage: Page) -> None:
        """Verify Contributors page sections have collapse buttons."""
        await go_to_contributors(page_with_js_coverage)

        # Check collapse buttons exist
        turnaround_repo_collapse = page_with_js_coverage.locator('[data-section="turnaround-by-repo"] .collapse-btn')
        await expect(turnaround_repo_collapse).to_be_visible()

        turnaround_reviewer_collapse = page_with_js_coverage.locator(
            '[data-section="turnaround-by-reviewer"] .collapse-btn'
        )
        await expect(turnaround_reviewer_collapse).to_be_visible()
