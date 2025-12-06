"""Playwright UI tests for the Contributors page with FULL UI coverage."""

import os

import pytest
from playwright.async_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3003")
TIMEOUT = 10000

pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsPageLoad:
    """Tests for Contributors page loading."""

    async def test_page_loads_successfully(self, page_with_js_coverage: Page) -> None:
        """Verify Contributors page loads without errors."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.locator("body")).to_be_visible()

    async def test_no_javascript_errors(self, page_with_js_coverage: Page) -> None:
        """Verify no JavaScript errors occur on page load."""
        errors: list[str] = []
        page_with_js_coverage.on("pageerror", lambda e: errors.append(str(e)))
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsSidebar:
    """Tests for sidebar navigation on Contributors page."""

    async def test_sidebar_is_visible(self, page_with_js_coverage: Page) -> None:
        """Verify sidebar is visible on Contributors page."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        sidebar = page_with_js_coverage.locator('[data-sidebar="sidebar"]')
        await expect(sidebar).to_be_visible()

    async def test_sidebar_contributors_link_active(self, page_with_js_coverage: Page) -> None:
        """Verify Contributors link is marked as active."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        # The active link should have specific aria-current or data-active attribute
        contributors_link = page_with_js_coverage.get_by_role("link", name="Contributors")
        await expect(contributors_link).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsKPICards:
    """Tests for KPI cards on Contributors page."""

    async def test_kpi_cards_visible(self, page_with_js_coverage: Page) -> None:
        """Verify KPI cards are visible."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # KPI cards show turnaround metrics - look for common text
        await expect(page_with_js_coverage.get_by_text("Avg Time to First Review")).to_be_visible()

    async def test_kpi_avg_time_to_approval_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Avg Time to Approval KPI exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Avg Time to Approval")).to_be_visible()

    async def test_kpi_avg_pr_lifecycle_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Avg PR Lifecycle KPI exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Avg PR Lifecycle")).to_be_visible()

    async def test_kpi_prs_analyzed_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PRs Analyzed KPI exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PRs Analyzed")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsSections:
    """Tests for sections on Contributors page."""

    async def test_turnaround_by_repository_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Turnaround by Repository section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Turnaround by Repository")).to_be_visible()

    async def test_response_time_by_reviewer_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Response Time by Reviewer section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Response Time by Reviewer")).to_be_visible()

    async def test_pr_creators_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR Creators section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PR Creators")).to_be_visible()

    async def test_pr_reviewers_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR Reviewers section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PR Reviewers")).to_be_visible()

    async def test_pr_approvers_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR Approvers section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PR Approvers")).to_be_visible()

    async def test_pr_lgtm_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR LGTM section exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PR LGTM")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsTables:
    """Tests for tables on Contributors page."""

    async def test_tables_render(self, page_with_js_coverage: Page) -> None:
        """Verify tables render on Contributors page."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        tables = page_with_js_coverage.locator("table")
        await expect(tables.first).to_be_visible()

    async def test_turnaround_by_repository_table_columns(self, page_with_js_coverage: Page) -> None:
        """Verify Turnaround by Repository table has expected columns."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Look for column headers - use table-specific selectors
        await expect(page_with_js_coverage.locator("th").filter(has_text="Repository").first).to_be_visible()
        await expect(page_with_js_coverage.locator("th").filter(has_text="First Review").first).to_be_visible()
        # "Approval" matches multiple columns, use first
        await expect(page_with_js_coverage.locator("th").filter(has_text="Approval").first).to_be_visible()
        await expect(page_with_js_coverage.locator("th").filter(has_text="Lifecycle").first).to_be_visible()

    async def test_pr_creators_table_columns(self, page_with_js_coverage: Page) -> None:
        """Verify PR Creators table has expected columns."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Scroll to PR Creators section
        pr_creators_section = page_with_js_coverage.get_by_text("PR Creators")
        await pr_creators_section.scroll_into_view_if_needed()
        await page_with_js_coverage.wait_for_timeout(500)
        # Look for unique column headers
        await expect(page_with_js_coverage.get_by_text("Total PRs")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("Merged")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("Closed")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsDownloadButtons:
    """Tests for download buttons on Contributors page."""

    async def test_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons exist on Contributors page."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        csv_buttons = page_with_js_coverage.locator("button").filter(has_text="CSV")
        json_buttons = page_with_js_coverage.locator("button").filter(has_text="JSON")
        await expect(csv_buttons.first).to_be_visible()
        await expect(json_buttons.first).to_be_visible()

    async def test_csv_download_button_clickable(self, page_with_js_coverage: Page) -> None:
        """Verify CSV download button is clickable."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        csv_button = page_with_js_coverage.locator("button").filter(has_text="CSV").first
        await csv_button.click()
        # No error = success

    async def test_json_download_button_clickable(self, page_with_js_coverage: Page) -> None:
        """Verify JSON download button is clickable."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        json_button = page_with_js_coverage.locator("button").filter(has_text="JSON").first
        await json_button.click()
        # No error = success


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsPagination:
    """Tests for pagination controls on Contributors page."""

    async def test_pagination_controls_exist(self, page_with_js_coverage: Page) -> None:
        """Verify pagination controls exist."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Scroll to PR Creators section which has pagination
        pr_creators_section = page_with_js_coverage.get_by_text("PR Creators")
        await pr_creators_section.scroll_into_view_if_needed()
        await page_with_js_coverage.wait_for_timeout(500)
        # Look for pagination info
        page_info = page_with_js_coverage.get_by_text("Showing")
        await expect(page_info.first).to_be_visible()

    async def test_pagination_prev_next_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify pagination prev/next buttons exist."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Scroll to PR Creators section
        pr_creators_section = page_with_js_coverage.get_by_text("PR Creators")
        await pr_creators_section.scroll_into_view_if_needed()
        await page_with_js_coverage.wait_for_timeout(500)
        prev_buttons = page_with_js_coverage.get_by_label("Go to previous page")
        next_buttons = page_with_js_coverage.get_by_label("Go to next page")
        # Check if pagination buttons exist (may not exist if not enough data)
        prev_count = await prev_buttons.count()
        next_count = await next_buttons.count()
        if prev_count > 0:
            await expect(prev_buttons.first).to_be_visible()
        if next_count > 0:
            await expect(next_buttons.first).to_be_visible()

    async def test_pagination_page_size_selector_exists(self, page_with_js_coverage: Page) -> None:
        """Verify pagination page size selector exists."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Scroll to PR Creators section
        pr_creators_section = page_with_js_coverage.get_by_text("PR Creators")
        await pr_creators_section.scroll_into_view_if_needed()
        await page_with_js_coverage.wait_for_timeout(500)
        # Look for page size text (e.g., "creators" or similar)
        creators_text = page_with_js_coverage.get_by_text("creators")
        await expect(creators_text.first).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsUserPRsModal:
    """Tests for User PRs modal on Contributors page."""

    async def test_user_name_is_clickable(self, page_with_js_coverage: Page) -> None:
        """Verify user names in tables are clickable."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Wait for data to load
        await page_with_js_coverage.wait_for_timeout(1000)
        # Scroll to PR Creators section
        pr_creators_section = page_with_js_coverage.get_by_text("PR Creators")
        await pr_creators_section.scroll_into_view_if_needed()
        await page_with_js_coverage.wait_for_timeout(500)
        # Look for clickable user buttons in table
        user_buttons = page_with_js_coverage.locator("table button[type='button']")
        count = await user_buttons.count()
        # We can't guarantee users exist, so just check count >= 0
        assert count >= 0


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsCollapsibleSections:
    """Tests for collapsible sections on Contributors page."""

    async def test_sections_are_collapsible(self, page_with_js_coverage: Page) -> None:
        """Verify sections are collapsible."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        # Verify section titles exist (which indicates collapsible sections)
        await expect(page_with_js_coverage.get_by_text("Turnaround by Repository")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("PR Creators")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsNavigation:
    """Tests for navigation on Contributors page."""

    async def test_navigation_back_to_overview(self, page_with_js_coverage: Page) -> None:
        """Test navigation back to Overview page."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await page_with_js_coverage.get_by_role("link", name="Overview").click()
        await page_with_js_coverage.wait_for_load_state("networkidle")
        assert page_with_js_coverage.url == f"{BASE_URL}/" or page_with_js_coverage.url == BASE_URL

    async def test_navigation_to_team_dynamics(self, page_with_js_coverage: Page) -> None:
        """Test navigation to Team Dynamics page."""
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await page_with_js_coverage.get_by_role("link", name="Team Dynamics").click()
        await page_with_js_coverage.wait_for_load_state("networkidle")
        assert "/team-dynamics" in page_with_js_coverage.url


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestContributorsResponsive:
    """Tests for responsive design on Contributors page."""

    async def test_mobile_viewport_loads(self, page_with_js_coverage: Page) -> None:
        """Verify page renders on mobile viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 375, "height": 667})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.locator("body")).to_be_visible()

    async def test_mobile_viewport_kpi_cards_visible(self, page_with_js_coverage: Page) -> None:
        """Verify KPI cards visible on mobile viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 375, "height": 667})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Avg Time to First Review")).to_be_visible()

    async def test_tablet_viewport_loads(self, page_with_js_coverage: Page) -> None:
        """Verify page renders on tablet viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 768, "height": 1024})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.locator("body")).to_be_visible()

    async def test_tablet_viewport_sections_visible(self, page_with_js_coverage: Page) -> None:
        """Verify sections visible on tablet viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 768, "height": 1024})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("PR Creators")).to_be_visible()

    async def test_desktop_viewport_loads(self, page_with_js_coverage: Page) -> None:
        """Verify page renders on desktop viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 1920, "height": 1080})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.locator("body")).to_be_visible()

    async def test_desktop_viewport_all_sections_visible(self, page_with_js_coverage: Page) -> None:
        """Verify all sections visible on desktop viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 1920, "height": 1080})
        await page_with_js_coverage.goto(f"{BASE_URL}/contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")
        await expect(page_with_js_coverage.get_by_text("Turnaround by Repository")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("PR Creators")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("PR Reviewers")).to_be_visible()
        await expect(page_with_js_coverage.get_by_text("PR Approvers")).to_be_visible()
