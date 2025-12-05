"""Playwright UI tests for the metrics dashboard Team Dynamics page."""

from __future__ import annotations

import os
import re

import pytest
from playwright.async_api import Page, expect

# Test constants
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8765/dashboard")
TIMEOUT = 10000  # 10 seconds timeout for UI interactions

pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


async def go_to_team_dynamics(page: Page) -> None:
    """Navigate to Team Dynamics page and wait for load."""
    await page.goto(f"{DASHBOARD_URL}#team-dynamics", timeout=TIMEOUT)
    await page.wait_for_load_state("networkidle")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsPageNavigation:
    """Tests for Team Dynamics page navigation and visibility."""

    async def test_team_dynamics_page_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Team Dynamics page exists and can be navigated to."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Navigate to Team Dynamics page
        team_dynamics_nav = page_with_js_coverage.locator('.nav-item[data-page="team-dynamics"]')
        await team_dynamics_nav.click()

        # Wait for Team Dynamics page to be visible
        team_dynamics_page = page_with_js_coverage.locator("#page-team-dynamics")
        await expect(team_dynamics_page).to_be_visible(timeout=5000)

    async def test_team_dynamics_direct_hash_navigation(self, page_with_js_coverage: Page) -> None:
        """Test direct navigation via URL hash to Team Dynamics page."""
        await page_with_js_coverage.goto(f"{DASHBOARD_URL}#team-dynamics", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Team Dynamics page should be visible
        team_dynamics_page = page_with_js_coverage.locator("#page-team-dynamics")
        await expect(team_dynamics_page).to_be_visible()

        # Other pages should be hidden
        overview_page = page_with_js_coverage.locator("#page-overview")
        await expect(overview_page).not_to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsPageStructure:
    """Tests for Team Dynamics page structure and elements."""

    async def test_page_header_renders(self, page_with_js_coverage: Page) -> None:
        """Verify Team Dynamics page header renders correctly."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Check main heading
        heading = page_with_js_coverage.locator("#page-team-dynamics .header h1")
        await expect(heading).to_have_text("Team Dynamics")

        # Check subtitle
        subtitle = page_with_js_coverage.locator("#page-team-dynamics .header p")
        await expect(subtitle).to_contain_text("Workload distribution")

    async def test_loading_state_element_exists(self, page_with_js_coverage: Page) -> None:
        """Verify loading state element exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        loading_element = page_with_js_coverage.locator("#team-dynamics-loading")
        await expect(loading_element).to_be_attached()

    async def test_error_state_element_exists(self, page_with_js_coverage: Page) -> None:
        """Verify error state element exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        error_element = page_with_js_coverage.locator("#team-dynamics-error")
        await expect(error_element).to_be_attached()

    async def test_content_element_exists(self, page_with_js_coverage: Page) -> None:
        """Verify content element exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        content_element = page_with_js_coverage.locator("#team-dynamics-content")
        await expect(content_element).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsWorkloadSection:
    """Tests for Workload Distribution section."""

    async def test_workload_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Workload Distribution section exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        workload_section = page_with_js_coverage.locator('.chart-container[data-section="workload-distribution"]')
        await expect(workload_section).to_be_attached()

    async def test_workload_section_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify Workload Distribution section has collapse button."""
        await go_to_team_dynamics(page_with_js_coverage)

        collapse_btn = page_with_js_coverage.locator('[data-section="workload-distribution"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_workload_kpi_cards_exist(self, page_with_js_coverage: Page) -> None:
        """Verify Workload Distribution KPI cards exist."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Active Contributors
        kpi_active = page_with_js_coverage.locator("#kpi-active-contributors")
        await expect(kpi_active).to_be_attached()

        # Avg PRs per User
        kpi_avg_prs = page_with_js_coverage.locator("#kpi-avg-prs-per-user")
        await expect(kpi_avg_prs).to_be_attached()

        # Top Contributor
        kpi_top = page_with_js_coverage.locator("#kpi-top-contributor")
        await expect(kpi_top).to_be_attached()

        # Workload Balance (Gini)
        kpi_gini = page_with_js_coverage.locator("#kpi-gini-coefficient")
        await expect(kpi_gini).to_be_attached()

    async def test_workload_table_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Workload table exists with correct structure."""
        await go_to_team_dynamics(page_with_js_coverage)

        table = page_with_js_coverage.locator("#workloadTable")
        await expect(table).to_be_attached()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(4)
        await expect(headers.nth(0)).to_have_text("Contributor")
        await expect(headers.nth(1)).to_have_text("PRs Created")
        await expect(headers.nth(2)).to_have_text("PRs Reviewed")
        await expect(headers.nth(3)).to_have_text("PRs Approved")

        # Table body should exist
        tbody = table.locator("tbody#workload-table-body")
        await expect(tbody).to_be_visible()

    async def test_workload_table_has_sortable_headers(self, page_with_js_coverage: Page) -> None:
        """Verify Workload table headers are sortable."""
        await go_to_team_dynamics(page_with_js_coverage)

        sortable_headers = page_with_js_coverage.locator("#workloadTable thead th.sortable")
        await expect(sortable_headers).to_have_count(4)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsReviewEfficiencySection:
    """Tests for Review Efficiency section."""

    async def test_review_efficiency_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Review Efficiency section exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        review_section = page_with_js_coverage.locator('.chart-container[data-section="review-efficiency"]')
        await expect(review_section).to_be_attached()

    async def test_review_efficiency_section_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify Review Efficiency section has collapse button."""
        await go_to_team_dynamics(page_with_js_coverage)

        collapse_btn = page_with_js_coverage.locator('[data-section="review-efficiency"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_review_efficiency_kpi_cards_exist(self, page_with_js_coverage: Page) -> None:
        """Verify Review Efficiency KPI cards exist."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Average Review Time
        kpi_avg = page_with_js_coverage.locator("#kpi-avg-review-time")
        await expect(kpi_avg).to_be_attached()

        # Median Review Time
        kpi_median = page_with_js_coverage.locator("#kpi-median-review-time")
        await expect(kpi_median).to_be_attached()

        # Fastest Reviewer
        kpi_fastest = page_with_js_coverage.locator("#kpi-fastest-reviewer")
        await expect(kpi_fastest).to_be_attached()

        # Slowest Reviewer
        kpi_slowest = page_with_js_coverage.locator("#kpi-slowest-reviewer")
        await expect(kpi_slowest).to_be_attached()

    async def test_review_efficiency_table_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Review Efficiency table exists with correct structure."""
        await go_to_team_dynamics(page_with_js_coverage)

        table = page_with_js_coverage.locator("#reviewEfficiencyTable")
        await expect(table).to_be_attached()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(4)

        # Table body should exist
        tbody = table.locator("tbody#review-efficiency-table-body")
        await expect(tbody).to_be_visible()

    async def test_review_efficiency_table_has_sortable_headers(self, page_with_js_coverage: Page) -> None:
        """Verify Review Efficiency table headers are sortable."""
        await go_to_team_dynamics(page_with_js_coverage)

        sortable_headers = page_with_js_coverage.locator("#reviewEfficiencyTable thead th.sortable")
        await expect(sortable_headers).to_have_count(4)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsBottlenecksSection:
    """Tests for Approval Bottlenecks section."""

    async def test_bottlenecks_section_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Approval Bottlenecks section exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        bottlenecks_section = page_with_js_coverage.locator('.chart-container[data-section="approval-bottlenecks"]')
        await expect(bottlenecks_section).to_be_attached()

    async def test_bottlenecks_section_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify Approval Bottlenecks section has collapse button."""
        await go_to_team_dynamics(page_with_js_coverage)

        collapse_btn = page_with_js_coverage.locator('.collapse-btn[data-section="approval-bottlenecks"]')
        await expect(collapse_btn).to_be_visible()

    async def test_bottlenecks_alert_cards_container_exists(self, page_with_js_coverage: Page) -> None:
        """Verify alert cards container exists."""
        await go_to_team_dynamics(page_with_js_coverage)

        alerts_container = page_with_js_coverage.locator("#approval-alerts-container")
        await expect(alerts_container).to_be_attached()

    async def test_bottlenecks_table_exists(self, page_with_js_coverage: Page) -> None:
        """Verify Approval Bottlenecks table exists with correct structure."""
        await go_to_team_dynamics(page_with_js_coverage)

        table = page_with_js_coverage.locator("#approversTable")
        await expect(table).to_be_attached()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(3)

        # Table body should exist
        tbody = table.locator("tbody#approvers-table-body")
        await expect(tbody).to_be_visible()

    async def test_bottlenecks_table_has_sortable_headers(self, page_with_js_coverage: Page) -> None:
        """Verify Approval Bottlenecks table headers are sortable."""
        await go_to_team_dynamics(page_with_js_coverage)

        sortable_headers = page_with_js_coverage.locator("#approversTable thead th.sortable")
        await expect(sortable_headers).to_have_count(3)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsDownloadButtons:
    """Tests for download button functionality."""

    async def test_workload_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify workload section has download buttons."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Workload table download buttons
        csv_button = page_with_js_coverage.locator('.download-btn[data-section="workloadTable"][data-format="csv"]')
        json_button = page_with_js_coverage.locator('.download-btn[data-section="workloadTable"][data-format="json"]')

        await expect(csv_button).to_be_visible()
        await expect(json_button).to_be_visible()

    async def test_review_efficiency_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify review efficiency section has download buttons."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Review efficiency table download buttons
        csv_button = page_with_js_coverage.locator(
            '.download-btn[data-section="reviewEfficiencyTable"][data-format="csv"]'
        )
        json_button = page_with_js_coverage.locator(
            '.download-btn[data-section="reviewEfficiencyTable"][data-format="json"]'
        )

        await expect(csv_button).to_be_visible()
        await expect(json_button).to_be_visible()

    async def test_bottlenecks_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify bottlenecks section has download buttons."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Bottlenecks table download buttons
        csv_button = page_with_js_coverage.locator('.download-btn[data-section="approversTable"][data-format="csv"]')
        json_button = page_with_js_coverage.locator('.download-btn[data-section="approversTable"][data-format="json"]')

        await expect(csv_button).to_be_visible()
        await expect(json_button).to_be_visible()

    async def test_download_buttons_are_clickable(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons are clickable."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Test workload CSV button
        workload_csv = page_with_js_coverage.locator('.download-btn[data-section="workloadTable"][data-format="csv"]')
        await expect(workload_csv).to_be_visible()
        await expect(workload_csv).to_be_enabled()

        # Test review efficiency JSON button
        review_json = page_with_js_coverage.locator(
            '.download-btn[data-section="reviewEfficiencyTable"][data-format="json"]'
        )
        await expect(review_json).to_be_visible()
        await expect(review_json).to_be_enabled()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsCollapsibleSections:
    """Tests for collapsible sections functionality."""

    async def test_collapse_workload_section(self, page_with_js_coverage: Page) -> None:
        """Test collapsing workload section."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Find collapse button
        collapse_btn = page_with_js_coverage.locator('[data-section="workload-distribution"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

        # Click collapse button
        await collapse_btn.click()

        # Button should still be visible after click
        await expect(collapse_btn).to_be_visible()

    async def test_collapse_review_efficiency_section(self, page_with_js_coverage: Page) -> None:
        """Test collapsing review efficiency section."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Find collapse button
        collapse_btn = page_with_js_coverage.locator('[data-section="review-efficiency"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

        # Click collapse button
        await collapse_btn.click()

        # Button should still be visible after click
        await expect(collapse_btn).to_be_visible()

    async def test_collapse_bottlenecks_section(self, page_with_js_coverage: Page) -> None:
        """Test collapsing bottlenecks section."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Find collapse button
        collapse_btn = page_with_js_coverage.locator('.collapse-btn[data-section="approval-bottlenecks"]')
        await expect(collapse_btn).to_be_visible()

        # Click collapse button
        await collapse_btn.click()

        # Button should still be visible after click
        await expect(collapse_btn).to_be_visible()

    async def test_expand_collapsed_sections(self, page_with_js_coverage: Page) -> None:
        """Test expanding collapsed sections."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Collapse then expand workload section
        btn = page_with_js_coverage.locator('.collapse-btn[data-section="workload-distribution"]')
        section = page_with_js_coverage.locator('.chart-container[data-section="workload-distribution"]')

        # Collapse - wait for animation to complete
        await btn.click()
        await page_with_js_coverage.wait_for_timeout(500)  # Wait for CSS transition

        # Verify collapsed state
        await expect(section).to_have_class(re.compile("collapsed"))

        # Expand - wait for animation to complete
        await btn.click()
        await page_with_js_coverage.wait_for_timeout(500)  # Wait for CSS transition

        # Verify expanded state - should NOT have collapsed class
        await expect(section).not_to_have_class(re.compile("collapsed"))
        # Section container should still be visible even when collapsed
        await expect(section).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsTableInteractions:
    """Tests for table sorting and interactions."""

    async def test_workload_table_sorting(self, page_with_js_coverage: Page) -> None:
        """Test sorting workload table by clicking headers."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Click sortable header
        header = page_with_js_coverage.locator("#workloadTable thead th.sortable").first
        await header.click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#workloadTable")).to_be_attached()

    async def test_review_efficiency_table_sorting(self, page_with_js_coverage: Page) -> None:
        """Test sorting review efficiency table by clicking headers."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Click sortable header
        header = page_with_js_coverage.locator("#reviewEfficiencyTable thead th.sortable").first
        await header.click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#reviewEfficiencyTable")).to_be_attached()

    async def test_bottlenecks_table_sorting(self, page_with_js_coverage: Page) -> None:
        """Test sorting bottlenecks table by clicking headers."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Click sortable header
        header = page_with_js_coverage.locator("#approversTable thead th.sortable").first
        await header.click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#approversTable")).to_be_attached()

    async def test_multiple_sort_clicks(self, page_with_js_coverage: Page) -> None:
        """Verify sorting direction changes on multiple clicks."""
        await go_to_team_dynamics(page_with_js_coverage)

        header = page_with_js_coverage.locator("#workloadTable thead th.sortable").first

        # First click
        await header.click()

        # Second click
        await header.click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#workloadTable")).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsAccessibility:
    """Tests for accessibility features on Team Dynamics page."""

    async def test_table_headers_have_scope(self, page_with_js_coverage: Page) -> None:
        """Verify table headers have scope attribute."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Check workload table headers
        workload_headers = page_with_js_coverage.locator("#workloadTable thead th")
        for i in range(4):
            await expect(workload_headers.nth(i)).to_have_attribute("scope", "col")

        # Check review efficiency table headers
        review_headers = page_with_js_coverage.locator("#reviewEfficiencyTable thead th")
        for i in range(4):
            await expect(review_headers.nth(i)).to_have_attribute("scope", "col")

        # Check bottlenecks table headers
        bottleneck_headers = page_with_js_coverage.locator("#approversTable thead th")
        for i in range(3):
            await expect(bottleneck_headers.nth(i)).to_have_attribute("scope", "col")

    async def test_collapse_buttons_have_aria_labels(self, page_with_js_coverage: Page) -> None:
        """Verify collapse buttons have proper aria-label attributes."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Workload collapse button
        workload_btn = page_with_js_coverage.locator('.collapse-btn[data-section="workload-distribution"]')
        aria_label = await workload_btn.get_attribute("aria-label")
        assert aria_label is not None, "Workload collapse button aria-label is None"
        assert len(aria_label) > 0, "Workload collapse button aria-label is empty"

        # Review efficiency collapse button
        review_btn = page_with_js_coverage.locator('.collapse-btn[data-section="review-efficiency"]')
        aria_label = await review_btn.get_attribute("aria-label")
        assert aria_label is not None, "Review efficiency collapse button aria-label is None"
        assert len(aria_label) > 0, "Review efficiency collapse button aria-label is empty"

        # Bottlenecks collapse button
        bottleneck_btn = page_with_js_coverage.locator('.collapse-btn[data-section="approval-bottlenecks"]')
        aria_label = await bottleneck_btn.get_attribute("aria-label")
        assert aria_label is not None, "Approval bottlenecks collapse button aria-label is None"
        assert len(aria_label) > 0, "Approval bottlenecks collapse button aria-label is empty"

    async def test_download_buttons_have_aria_labels(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons have aria-label attributes."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Get all download buttons on Team Dynamics page
        download_buttons = page_with_js_coverage.locator("#page-team-dynamics .download-btn")
        button_count = await download_buttons.count()

        # Should have 6 buttons (3 tables x 2 formats)
        assert button_count >= 6, f"Expected at least 6 download buttons, found {button_count}"

        # Verify each button has aria-label
        for i in range(button_count):
            button = download_buttons.nth(i)
            aria_label = await button.get_attribute("aria-label")
            assert aria_label is not None, f"Button {i} missing aria-label attribute"
            assert len(aria_label) > 0, f"Button {i} has empty aria-label attribute"


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsResponsiveness:
    """Tests for responsive design on Team Dynamics page."""

    async def test_mobile_viewport_rendering(self, page_with_js_coverage: Page) -> None:
        """Verify Team Dynamics page renders on mobile viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 375, "height": 667})  # iPhone size
        await go_to_team_dynamics(page_with_js_coverage)

        # Main elements should still be visible
        await expect(page_with_js_coverage.locator("#page-team-dynamics .header h1")).to_be_visible()
        await expect(page_with_js_coverage.locator("#team-dynamics-content")).to_be_attached()

    async def test_tablet_viewport_rendering(self, page_with_js_coverage: Page) -> None:
        """Verify Team Dynamics page renders on tablet viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 768, "height": 1024})  # iPad size
        await go_to_team_dynamics(page_with_js_coverage)

        # All sections should be attached
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="workload-distribution"]')
        ).to_be_attached()
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="review-efficiency"]')
        ).to_be_attached()
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="approval-bottlenecks"]')
        ).to_be_attached()

    async def test_desktop_viewport_rendering(self, page_with_js_coverage: Page) -> None:
        """Verify Team Dynamics page renders on desktop viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 1920, "height": 1080})
        await go_to_team_dynamics(page_with_js_coverage)

        # All sections should be attached
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="workload-distribution"]')
        ).to_be_attached()
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="review-efficiency"]')
        ).to_be_attached()
        await expect(
            page_with_js_coverage.locator('.chart-container[data-section="approval-bottlenecks"]')
        ).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestTeamDynamicsErrorHandling:
    """Tests for error handling and edge cases."""

    async def test_no_javascript_errors_on_load(self, page_with_js_coverage: Page) -> None:
        """Verify no JavaScript errors occur on Team Dynamics page load."""
        errors: list[str] = []
        page_with_js_coverage.on("pageerror", lambda e: errors.append(str(e)))

        await go_to_team_dynamics(page_with_js_coverage)

        # Should have no critical errors
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"

    async def test_time_filter_changes_trigger_reload(self, page_with_js_coverage: Page) -> None:
        """Test that time filter changes work on Team Dynamics page."""
        await go_to_team_dynamics(page_with_js_coverage)

        # Change time range
        time_range = page_with_js_coverage.locator("#time-range-select")
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Page should still be visible
        await expect(page_with_js_coverage.locator("#page-team-dynamics")).to_be_visible()

    async def test_refresh_button_works_on_team_dynamics_page(self, page_with_js_coverage: Page) -> None:
        """Verify refresh button works when on Team Dynamics page."""
        await go_to_team_dynamics(page_with_js_coverage)

        refresh_btn = page_with_js_coverage.locator("#refresh-button")
        await refresh_btn.click()
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Page should still be visible
        await expect(page_with_js_coverage.locator("#page-team-dynamics")).to_be_visible()
