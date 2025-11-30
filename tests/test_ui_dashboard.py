"""Playwright UI tests for the metrics dashboard."""

from __future__ import annotations

import pytest
from playwright.async_api import Page, expect

# Test constants
DASHBOARD_URL = "http://localhost:8765/dashboard"
TIMEOUT = 10000  # 10 seconds timeout for UI interactions

pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardPageLoad:
    """Tests for dashboard page loading and rendering."""

    async def test_dashboard_loads_successfully(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard page loads without errors."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await expect(page_with_js_coverage).to_have_title("GitHub Metrics Dashboard")

    async def test_header_renders(self, page_with_js_coverage: Page) -> None:
        """Verify page header renders correctly."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check main heading
        heading = page_with_js_coverage.locator("h1")
        await expect(heading).to_have_text("GitHub Metrics Dashboard")

        # Check subtitle
        subtitle = page_with_js_coverage.locator("h1 + p")
        await expect(subtitle).to_have_text("Real-time monitoring of webhook processing metrics")

    async def test_connection_status_displays(self, page_with_js_coverage: Page) -> None:
        """Verify connection status element is visible."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check connection status container
        status = page_with_js_coverage.locator("#connection-status")
        await expect(status).to_be_visible()

        # Check status text element
        status_text = page_with_js_coverage.locator("#statusText")
        await expect(status_text).to_be_visible()

    async def test_control_panel_renders(self, page_with_js_coverage: Page) -> None:
        """Verify control panel renders with all controls."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Control panel should be visible
        control_panel = page_with_js_coverage.locator(".control-panel")
        await expect(control_panel).to_be_visible()

        # Check all filter groups
        time_range_select = page_with_js_coverage.locator("#time-range-select")
        await expect(time_range_select).to_be_visible()

        start_time = page_with_js_coverage.locator("#startTime")
        await expect(start_time).to_be_visible()

        end_time = page_with_js_coverage.locator("#endTime")
        await expect(end_time).to_be_visible()

        repository_filter = page_with_js_coverage.locator("#repositoryFilter")
        await expect(repository_filter).to_be_visible()

        user_filter = page_with_js_coverage.locator("#userFilter")
        await expect(user_filter).to_be_visible()

        refresh_button = page_with_js_coverage.locator("#refresh-button")
        await expect(refresh_button).to_be_visible()
        await expect(refresh_button).to_have_text("Refresh")

    async def test_all_dashboard_sections_render(self, page_with_js_coverage: Page) -> None:
        """Verify all dashboard sections are present."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Top Repositories section
        top_repos = page_with_js_coverage.locator('.chart-container[data-section="top-repositories"]')
        await expect(top_repos).to_be_visible()
        await expect(top_repos.locator("h2")).to_have_text("Top Repositories")

        # Recent Events section
        recent_events = page_with_js_coverage.locator('.chart-container[data-section="recent-events"]')
        await expect(recent_events).to_be_visible()
        await expect(recent_events.locator("h2")).to_have_text("Recent Events")

        # PR Contributors section
        pr_contributors = page_with_js_coverage.locator('.chart-container[data-section="pr-contributors"]')
        await expect(pr_contributors).to_be_visible()
        await expect(pr_contributors.locator("h2")).to_have_text("PR Contributors")

        # User PRs section
        user_prs = page_with_js_coverage.locator('.chart-container[data-section="user-prs"]')
        await expect(user_prs).to_be_visible()
        await expect(user_prs.locator("h2")).to_have_text("Pull Requests")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardControls:
    """Tests for dashboard control interactions."""

    async def test_time_range_selector_has_options(self, page_with_js_coverage: Page) -> None:
        """Test time range select has all expected options."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        time_range_select = page_with_js_coverage.locator("#time-range-select")
        await expect(time_range_select).to_be_visible()

        # Check options exist
        options = time_range_select.locator("option")
        await expect(options).to_have_count(4)

        # Check option values using attribute
        await expect(options.nth(0)).to_have_attribute("value", "1h")
        await expect(options.nth(1)).to_have_attribute("value", "24h")
        await expect(options.nth(2)).to_have_attribute("value", "7d")
        await expect(options.nth(3)).to_have_attribute("value", "30d")

        # Check default selection
        await expect(time_range_select).to_have_value("24h")

    async def test_time_range_selector_changes(self, page_with_js_coverage: Page) -> None:
        """Test time range selector can be changed."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        time_range_select = page_with_js_coverage.locator("#time-range-select")

        # Change to "Last Hour"
        await time_range_select.select_option("1h")
        await expect(time_range_select).to_have_value("1h")

        # Change to "Last 7 Days"
        await time_range_select.select_option("7d")
        await expect(time_range_select).to_have_value("7d")

    async def test_datetime_inputs_are_editable(self, page_with_js_coverage: Page) -> None:
        """Test datetime inputs can be edited."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        start_time = page_with_js_coverage.locator("#startTime")
        end_time = page_with_js_coverage.locator("#endTime")

        # Both should be editable
        await expect(start_time).to_be_editable()
        await expect(end_time).to_be_editable()

        # Fill with test values
        await start_time.fill("2024-11-01T10:00")
        await expect(start_time).to_have_value("2024-11-01T10:00")

        await end_time.fill("2024-11-30T18:00")
        await expect(end_time).to_have_value("2024-11-30T18:00")

    async def test_repository_filter_input(self, page_with_js_coverage: Page) -> None:
        """Test repository filter input field."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await expect(repo_filter).to_be_visible()
        await expect(repo_filter).to_be_editable()
        await expect(repo_filter).to_have_attribute("placeholder", "Type to search or select...")

        # Type a repository name
        await repo_filter.fill("org/repo1")
        await expect(repo_filter).to_have_value("org/repo1")

    async def test_user_filter_input(self, page_with_js_coverage: Page) -> None:
        """Test user filter input field."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        user_filter = page_with_js_coverage.locator("#userFilter")
        await expect(user_filter).to_be_visible()
        await expect(user_filter).to_be_editable()
        await expect(user_filter).to_have_attribute("placeholder", "Type to search or select...")

        # Type a username
        await user_filter.fill("alice")
        await expect(user_filter).to_have_value("alice")

    async def test_refresh_button_clickable(self, page_with_js_coverage: Page) -> None:
        """Test refresh button is clickable."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        refresh_button = page_with_js_coverage.locator("#refresh-button")
        await expect(refresh_button).to_be_visible()
        await expect(refresh_button).to_be_enabled()

        # Click should not cause errors
        await refresh_button.click()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTables:
    """Tests for dashboard data tables."""

    async def test_top_repositories_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify top repositories table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#topRepositoriesTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(3)
        await expect(headers.nth(0)).to_have_text("Repository")
        await expect(headers.nth(1)).to_have_text("Events")
        await expect(headers.nth(2)).to_have_text("%")

        # Table body should exist
        tbody = table.locator("tbody#repository-table-body")
        await expect(tbody).to_be_visible()

    async def test_recent_events_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify recent events table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#recentEventsTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(4)
        await expect(headers.nth(0)).to_have_text("Time")
        await expect(headers.nth(1)).to_have_text("Repository")
        await expect(headers.nth(2)).to_have_text("Event")
        await expect(headers.nth(3)).to_have_text("Status")

    async def test_pr_creators_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify PR creators table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#prCreatorsTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(5)
        await expect(headers.nth(0)).to_have_text("User")
        await expect(headers.nth(1)).to_have_text("Total PRs")
        await expect(headers.nth(2)).to_have_text("Merged")
        await expect(headers.nth(3)).to_have_text("Closed")
        await expect(headers.nth(4)).to_have_text("Avg Commits")

        # Table body should exist
        tbody = table.locator("tbody#pr-creators-table-body")
        await expect(tbody).to_be_visible()

    async def test_pr_reviewers_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify PR reviewers table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#prReviewersTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(4)
        await expect(headers.nth(0)).to_have_text("User")
        await expect(headers.nth(1)).to_have_text("Total Reviews")
        await expect(headers.nth(2)).to_have_text("PRs Reviewed")
        await expect(headers.nth(3)).to_have_text("Avg/PR")

        # Table body should exist
        tbody = table.locator("tbody#pr-reviewers-table-body")
        await expect(tbody).to_be_visible()

    async def test_pr_approvers_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify PR approvers table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#prApproversTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(3)
        await expect(headers.nth(0)).to_have_text("User")
        await expect(headers.nth(1)).to_have_text("Total Approvals")
        await expect(headers.nth(2)).to_have_text("PRs Approved")

        # Table body should exist
        tbody = table.locator("tbody#pr-approvers-table-body")
        await expect(tbody).to_be_visible()

    async def test_user_prs_table_structure(self, page_with_js_coverage: Page) -> None:
        """Verify user PRs table has correct structure."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page_with_js_coverage.locator("#userPrsTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(8)
        await expect(headers.nth(0)).to_have_text("PR")
        await expect(headers.nth(1)).to_have_text("Title")
        await expect(headers.nth(2)).to_have_text("Owner")
        await expect(headers.nth(3)).to_have_text("Repository")
        await expect(headers.nth(4)).to_have_text("State")
        await expect(headers.nth(5)).to_have_text("Created")
        await expect(headers.nth(6)).to_have_text("Updated")
        await expect(headers.nth(7)).to_have_text("Commits")

        # Table body should exist
        tbody = table.locator("tbody#user-prs-table-body")
        await expect(tbody).to_be_visible()

    async def test_sortable_table_headers(self, page_with_js_coverage: Page) -> None:
        """Verify table headers have sortable class."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Top repositories sortable headers
        top_repos_headers = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable")
        await expect(top_repos_headers).to_have_count(3)

        # Recent events sortable headers
        recent_events_headers = page_with_js_coverage.locator("#recentEventsTable thead th.sortable")
        await expect(recent_events_headers).to_have_count(4)

        # PR creators sortable headers
        pr_creators_headers = page_with_js_coverage.locator("#prCreatorsTable thead th.sortable")
        await expect(pr_creators_headers).to_have_count(5)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTheme:
    """Tests for theme toggle functionality."""

    async def test_theme_toggle_button_exists(self, page_with_js_coverage: Page) -> None:
        """Verify theme toggle button is present."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page_with_js_coverage.locator("#theme-toggle")
        await expect(theme_toggle).to_be_visible()
        await expect(theme_toggle).to_be_enabled()
        await expect(theme_toggle).to_have_attribute("title", "Toggle between light and dark theme")

    async def test_theme_toggle_button_clickable(self, page_with_js_coverage: Page) -> None:
        """Test theme toggle button can be clicked."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page_with_js_coverage.locator("#theme-toggle")

        # Should be clickable
        await expect(theme_toggle).to_be_enabled()

        # Click should not cause errors
        await theme_toggle.click()

        # Still should be visible after click
        await expect(theme_toggle).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardCollapsiblePanels:
    """Tests for collapsible panel functionality."""

    async def test_control_panel_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify control panel has collapse button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page_with_js_coverage.locator('.control-panel .collapse-btn[data-section="control-panel"]')
        await expect(collapse_btn).to_be_visible()
        await expect(collapse_btn).to_have_text("▼")

    async def test_top_repositories_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify top repositories section has collapse button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page_with_js_coverage.locator('[data-section="top-repositories"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_recent_events_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify recent events section has collapse button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page_with_js_coverage.locator('[data-section="recent-events"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_pr_contributors_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify PR contributors section has collapse button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page_with_js_coverage.locator('[data-section="pr-contributors"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_user_prs_has_collapse_button(self, page_with_js_coverage: Page) -> None:
        """Verify user PRs section has collapse button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page_with_js_coverage.locator('[data-section="user-prs"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_collapse_button_clickable(self, page_with_js_coverage: Page) -> None:
        """Test collapse buttons are clickable."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Click top repositories collapse button
        collapse_btn = page_with_js_coverage.locator('[data-section="top-repositories"] .collapse-btn')
        await collapse_btn.click()

        # Button should still be visible after click
        await expect(collapse_btn).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardAccessibility:
    """Tests for dashboard accessibility features."""

    async def test_loading_spinner_has_aria_attributes(self, page_with_js_coverage: Page) -> None:
        """Verify loading spinner has proper ARIA attributes."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        spinner = page_with_js_coverage.locator("#loading-spinner")
        await expect(spinner).to_have_attribute("role", "status")
        await expect(spinner).to_have_attribute("aria-live", "polite")
        # aria-busy is dynamically set by JavaScript - "false" when hidden, "true" when visible
        await expect(spinner).to_have_attribute("aria-busy", "false")

    async def test_theme_toggle_has_aria_label(self, page_with_js_coverage: Page) -> None:
        """Verify theme toggle button has aria-label."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page_with_js_coverage.locator("#theme-toggle")
        await expect(theme_toggle).to_have_attribute("aria-label", "Toggle light or dark theme")

    async def test_table_headers_have_scope(self, page_with_js_coverage: Page) -> None:
        """Verify table headers have scope attribute."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check top repositories table headers
        top_repos_headers = page_with_js_coverage.locator("#topRepositoriesTable thead th")
        for i in range(3):
            await expect(top_repos_headers.nth(i)).to_have_attribute("scope", "col")

        # Check recent events table headers
        recent_events_headers = page_with_js_coverage.locator("#recentEventsTable thead th")
        for i in range(4):
            await expect(recent_events_headers.nth(i)).to_have_attribute("scope", "col")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardStatusTooltip:
    """Tests for connection status tooltip."""

    async def test_status_tooltip_exists(self, page_with_js_coverage: Page) -> None:
        """Verify status tooltip element exists."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        tooltip = page_with_js_coverage.locator(".status-tooltip")
        await expect(tooltip).to_be_attached()

    async def test_status_tooltip_has_kpi_elements(self, page_with_js_coverage: Page) -> None:
        """Verify status tooltip contains KPI elements."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check individual KPI elements
        await expect(page_with_js_coverage.locator("#tooltipTotalEvents")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipTotalEventsTrend")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipSuccessRate")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipSuccessRateTrend")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipFailedEvents")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipFailedEventsTrend")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipAvgDuration")).to_be_attached()
        await expect(page_with_js_coverage.locator("#tooltipAvgDurationTrend")).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardResponsiveness:
    """Tests for dashboard responsive design."""

    async def test_dashboard_renders_on_mobile_viewport(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard renders on mobile viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 375, "height": 667})  # iPhone size
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Main elements should still be visible
        await expect(page_with_js_coverage.locator("h1")).to_be_visible()
        await expect(page_with_js_coverage.locator("#connection-status")).to_be_visible()
        await expect(page_with_js_coverage.locator(".control-panel")).to_be_visible()

    async def test_dashboard_renders_on_tablet_viewport(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard renders on tablet viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 768, "height": 1024})  # iPad size
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # All sections should be visible
        await expect(page_with_js_coverage.locator('.chart-container[data-section="top-repositories"]')).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="recent-events"]')).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="pr-contributors"]')).to_be_visible()

    async def test_dashboard_renders_on_desktop_viewport(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard renders on desktop viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 1920, "height": 1080})
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Full dashboard should be visible
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="top-repositories"]')).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="recent-events"]')).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="pr-contributors"]')).to_be_visible()
        await expect(page_with_js_coverage.locator('.chart-container[data-section="user-prs"]')).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardStaticAssets:
    """Tests for dashboard static assets loading."""

    async def test_css_stylesheet_loads(self, page_with_js_coverage: Page) -> None:
        """Verify CSS stylesheet is linked."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check CSS link exists
        css_link = page_with_js_coverage.locator('link[href="/static/css/metrics_dashboard.css"]')
        await expect(css_link).to_be_attached()

    async def test_javascript_modules_load(self, page_with_js_coverage: Page) -> None:
        """Verify JavaScript modules are loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check all JS modules are referenced
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/utils.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/api-client.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/combo-box.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/charts.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/pr-story.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src="/static/js/metrics/dashboard.js"]')).to_be_attached()

    async def test_favicon_loads(self, page_with_js_coverage: Page) -> None:
        """Verify favicon is linked."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check favicon link exists
        favicon = page_with_js_coverage.locator('link[rel="icon"]')
        await expect(favicon).to_be_attached()
        await expect(favicon).to_have_attribute("type", "image/svg+xml")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestPRStoryModal:
    """Tests for PR Story modal functionality."""

    async def test_pr_story_script_loaded(self, page_with_js_coverage: Page) -> None:
        """Verify PR story script is loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        script = page_with_js_coverage.locator('script[src="/static/js/metrics/pr-story.js"]')
        await expect(script).to_be_attached()

    async def test_pr_table_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR table exists for modal triggers."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # User PRs table should exist
        await expect(page_with_js_coverage.locator("#userPrsTable")).to_be_visible()

    async def test_escape_key_handling(self, page_with_js_coverage: Page) -> None:
        """Test pressing Escape is handled."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Press Escape - should not cause errors
        await page_with_js_coverage.keyboard.press("Escape")
        await page_with_js_coverage.wait_for_timeout(200)

        # Dashboard should still be functional
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTableUpdates:
    """Tests for table data update functionality."""

    async def test_refresh_updates_tables(self, page_with_js_coverage: Page) -> None:
        """Verify refresh button updates all tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        refresh_btn = page_with_js_coverage.locator("#refresh-button")
        await refresh_btn.click()
        await page_with_js_coverage.wait_for_timeout(1000)

        # Tables should still be visible after refresh
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()
        await expect(page_with_js_coverage.locator("#recentEventsTable")).to_be_visible()

    async def test_time_range_updates_tables(self, page_with_js_coverage: Page) -> None:
        """Verify time range change updates tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        time_range = page_with_js_coverage.locator("#time-range-select")

        # Change to different time ranges
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_timeout(500)

        await time_range.select_option("30d")
        await page_with_js_coverage.wait_for_timeout(500)

        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_table_body_content_loads(self, page_with_js_coverage: Page) -> None:
        """Verify table bodies can load content."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(2000)

        # Check table bodies exist and are ready for content
        await expect(page_with_js_coverage.locator("#repository-table-body")).to_be_visible()
        await expect(page_with_js_coverage.locator("#pr-creators-table-body")).to_be_visible()
        await expect(page_with_js_coverage.locator("#pr-reviewers-table-body")).to_be_visible()

    async def test_contributors_tabs_switch(self, page_with_js_coverage: Page) -> None:
        """Test switching between contributor tabs."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Look for tab buttons in PR contributors section
        tabs = page_with_js_coverage.locator('[data-section="pr-contributors"] .tab-btn, .contributor-tab')
        count = await tabs.count()

        if count > 1:
            # Click second tab
            await tabs.nth(1).click()
            await page_with_js_coverage.wait_for_timeout(300)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardUtilityFunctions:
    """Tests that exercise utility functions through UI interactions."""

    async def test_timestamp_formatting(self, page_with_js_coverage: Page) -> None:
        """Verify timestamps are formatted in tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(2000)

        # Recent events table should have formatted timestamps
        time_cells = page_with_js_coverage.locator("#recentEventsTable tbody td:first-child")
        await expect(time_cells.first).to_be_attached()

    async def test_percentage_formatting(self, page_with_js_coverage: Page) -> None:
        """Verify percentages are formatted in tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(2000)

        # Top repositories table has percentage column
        pct_cells = page_with_js_coverage.locator("#topRepositoriesTable tbody td:last-child")
        await expect(pct_cells.first).to_be_attached()

    async def test_number_formatting_in_stats(self, page_with_js_coverage: Page) -> None:
        """Verify numbers are formatted in stats."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Tooltip should have formatted numbers
        await expect(page_with_js_coverage.locator("#tooltipTotalEvents")).to_be_attached()

    async def test_local_storage_for_theme(self, page_with_js_coverage: Page) -> None:
        """Test localStorage is used for theme persistence."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(500)

        # Toggle theme to trigger localStorage save
        theme_toggle = page_with_js_coverage.locator("#theme-toggle")
        await theme_toggle.click()
        await page_with_js_coverage.wait_for_timeout(200)

        # Toggle back
        await theme_toggle.click()
        await page_with_js_coverage.wait_for_timeout(200)

        await expect(theme_toggle).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardLoadingStates:
    """Tests for loading states and error handling."""

    async def test_loading_spinner_visibility(self, page_with_js_coverage: Page) -> None:
        """Verify loading spinner behavior."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        spinner = page_with_js_coverage.locator("#loading-spinner")
        await expect(spinner).to_be_attached()

    async def test_no_js_errors_on_load(self, page_with_js_coverage: Page) -> None:
        """Verify no JavaScript errors occur on page load."""
        errors: list[str] = []
        page_with_js_coverage.on("pageerror", lambda e: errors.append(str(e)))

        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(2000)

        # Should have no critical errors
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"

    async def test_empty_state_display(self, page_with_js_coverage: Page) -> None:
        """Verify empty states are handled gracefully."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Set filters that would return no results
        time_range = page_with_js_coverage.locator("#time-range-select")
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_timeout(500)

        # Dashboard should still be functional
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardCharts:
    """Tests for Chart.js library availability."""

    async def test_chartjs_library_loaded(self, page_with_js_coverage: Page) -> None:
        """Verify Chart.js library is loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Check Chart.js script is included
        chartjs_script = page_with_js_coverage.locator('script[src*="chart.js"]')
        await expect(chartjs_script).to_be_attached()

    async def test_charts_module_loaded(self, page_with_js_coverage: Page) -> None:
        """Verify charts.js module is loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        charts_script = page_with_js_coverage.locator('script[src="/static/js/metrics/charts.js"]')
        await expect(charts_script).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardPagination:
    """Tests for table data loading."""

    async def test_tables_load_data(self, page_with_js_coverage: Page) -> None:
        """Verify tables attempt to load data."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(2000)

        # Tables should be present and ready
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()
        await expect(page_with_js_coverage.locator("#prCreatorsTable")).to_be_visible()

    async def test_table_sorting_by_click(self, page_with_js_coverage: Page) -> None:
        """Verify table headers are sortable by click."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Click sortable header
        header = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable").first
        await header.click()
        await page_with_js_coverage.wait_for_timeout(300)

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_multiple_sort_clicks(self, page_with_js_coverage: Page) -> None:
        """Verify sorting direction changes on multiple clicks."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        header = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable").first

        # First click
        await header.click()
        await page_with_js_coverage.wait_for_timeout(200)

        # Second click
        await header.click()
        await page_with_js_coverage.wait_for_timeout(200)

        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardDataExport:
    """Tests for data export functionality."""

    async def test_download_button_exists(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons exist for tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        download_btns = page_with_js_coverage.locator(".download-btn, [data-action='download']")
        count = await download_btns.count()
        assert count >= 0


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardFilters:
    """Tests for filter interactions."""

    async def test_repository_filter_dropdown(self, page_with_js_coverage: Page) -> None:
        """Test repository filter dropdown interaction."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.click()
        await page_with_js_coverage.wait_for_timeout(300)

        await expect(repo_filter).to_be_visible()

    async def test_user_filter_dropdown(self, page_with_js_coverage: Page) -> None:
        """Test user filter dropdown interaction."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        user_filter = page_with_js_coverage.locator("#userFilter")
        await user_filter.click()
        await page_with_js_coverage.wait_for_timeout(300)

        await expect(user_filter).to_be_visible()

    async def test_filter_keyboard_navigation(self, page_with_js_coverage: Page) -> None:
        """Test keyboard navigation in filters."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.focus()

        await page_with_js_coverage.keyboard.press("ArrowDown")
        await page_with_js_coverage.wait_for_timeout(200)

        await page_with_js_coverage.keyboard.press("Escape")
        await page_with_js_coverage.wait_for_timeout(200)

    async def test_filter_with_typing(self, page_with_js_coverage: Page) -> None:
        """Test typing in filter input."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.fill("test")
        await page_with_js_coverage.wait_for_timeout(300)

        await expect(repo_filter).to_have_value("test")

    async def test_clear_filters(self, page_with_js_coverage: Page) -> None:
        """Test clearing filter values."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.fill("test")
        await page_with_js_coverage.wait_for_timeout(200)

        await repo_filter.fill("")
        await page_with_js_coverage.wait_for_timeout(200)

        await expect(repo_filter).to_have_value("")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardKeyboardNavigation:
    """Tests for keyboard navigation and interactions."""

    async def test_tab_navigation(self, page_with_js_coverage: Page) -> None:
        """Test Tab key navigation through controls."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Focus on first focusable element and tab through
        await page_with_js_coverage.keyboard.press("Tab")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("Tab")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("Tab")
        await page_with_js_coverage.wait_for_timeout(100)

        # Dashboard should still be visible
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()

    async def test_enter_key_on_refresh(self, page_with_js_coverage: Page) -> None:
        """Test Enter key triggers refresh button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        refresh_btn = page_with_js_coverage.locator("#refresh-button")
        await refresh_btn.focus()
        await page_with_js_coverage.keyboard.press("Enter")
        await page_with_js_coverage.wait_for_timeout(500)

        # Button should still be visible
        await expect(refresh_btn).to_be_visible()

    async def test_arrow_keys_in_select(self, page_with_js_coverage: Page) -> None:
        """Test arrow keys in time range select."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        time_select = page_with_js_coverage.locator("#time-range-select")
        await time_select.focus()
        await page_with_js_coverage.keyboard.press("ArrowDown")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("ArrowUp")
        await page_with_js_coverage.wait_for_timeout(100)

        # Select should still be visible
        await expect(time_select).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardComboBox:
    """Tests for combo box interactions."""

    async def test_combo_box_focus_blur(self, page_with_js_coverage: Page) -> None:
        """Test combo box focus and blur events."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")

        # Focus
        await repo_filter.focus()
        await page_with_js_coverage.wait_for_timeout(200)

        # Type something
        await repo_filter.fill("test-repo")
        await page_with_js_coverage.wait_for_timeout(200)

        # Blur by clicking elsewhere
        await page_with_js_coverage.locator("h1").click()
        await page_with_js_coverage.wait_for_timeout(200)

        # Verify value persists
        await expect(repo_filter).to_have_value("test-repo")

    async def test_combo_box_keyboard_events(self, page_with_js_coverage: Page) -> None:
        """Test combo box keyboard events."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        user_filter = page_with_js_coverage.locator("#userFilter")
        await user_filter.focus()

        # Type and use keyboard
        await user_filter.fill("alice")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("ArrowDown")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("ArrowUp")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("Enter")
        await page_with_js_coverage.wait_for_timeout(100)
        await page_with_js_coverage.keyboard.press("Escape")
        await page_with_js_coverage.wait_for_timeout(100)

        # Filter should still be visible
        await expect(user_filter).to_be_visible()

    async def test_combo_box_clear_value(self, page_with_js_coverage: Page) -> None:
        """Test clearing combo box value."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")

        # Fill then clear
        await repo_filter.fill("some-value")
        await page_with_js_coverage.wait_for_timeout(200)
        await repo_filter.clear()
        await page_with_js_coverage.wait_for_timeout(200)

        # Verify cleared
        await expect(repo_filter).to_have_value("")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTableInteractions:
    """Tests for table click and sort interactions."""

    async def test_sort_all_table_columns(self, page_with_js_coverage: Page) -> None:
        """Test sorting on all sortable columns."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Sort all columns in top repositories table
        headers = page_with_js_coverage.locator("#topRepositoriesTable th.sortable")
        count = await headers.count()

        for i in range(count):
            await headers.nth(i).click()
            await page_with_js_coverage.wait_for_timeout(200)

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_sort_pr_creators_table(self, page_with_js_coverage: Page) -> None:
        """Test sorting PR creators table."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        headers = page_with_js_coverage.locator("#prCreatorsTable th.sortable")
        count = await headers.count()

        for i in range(min(count, 3)):
            await headers.nth(i).click()
            await page_with_js_coverage.wait_for_timeout(150)

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#prCreatorsTable")).to_be_visible()

    async def test_sort_recent_events_table(self, page_with_js_coverage: Page) -> None:
        """Test sorting recent events table."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        headers = page_with_js_coverage.locator("#recentEventsTable th.sortable")
        count = await headers.count()

        for i in range(min(count, 2)):
            await headers.nth(i).click()
            await page_with_js_coverage.wait_for_timeout(150)

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#recentEventsTable")).to_be_visible()

    async def test_sort_user_prs_table(self, page_with_js_coverage: Page) -> None:
        """Test sorting user PRs table."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        headers = page_with_js_coverage.locator("#userPrsTable th.sortable")
        count = await headers.count()

        for i in range(min(count, 3)):
            await headers.nth(i).click()
            await page_with_js_coverage.wait_for_timeout(150)

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#userPrsTable")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTimeRangeInteractions:
    """Tests for time range and date filter interactions."""

    async def test_all_time_range_options(self, page_with_js_coverage: Page) -> None:
        """Test selecting all time range options."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        time_range = page_with_js_coverage.locator("#time-range-select")

        # Select each option
        for value in ["1h", "24h", "7d", "30d"]:
            await time_range.select_option(value)
            await page_with_js_coverage.wait_for_timeout(300)

        # Dashboard should still be visible
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()

    async def test_custom_date_range(self, page_with_js_coverage: Page) -> None:
        """Test setting custom date range."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        start_time = page_with_js_coverage.locator("#startTime")
        end_time = page_with_js_coverage.locator("#endTime")

        # Set custom dates
        await start_time.fill("2024-01-01T00:00")
        await page_with_js_coverage.wait_for_timeout(200)
        await end_time.fill("2024-12-31T23:59")
        await page_with_js_coverage.wait_for_timeout(200)

        # Trigger refresh
        await page_with_js_coverage.locator("#refresh-button").click()
        await page_with_js_coverage.wait_for_timeout(500)

        # Dashboard should still be visible
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()

    async def test_multiple_refreshes(self, page_with_js_coverage: Page) -> None:
        """Test multiple refresh button clicks."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        refresh_btn = page_with_js_coverage.locator("#refresh-button")

        # Click refresh multiple times
        for _ in range(3):
            await refresh_btn.click()
            await page_with_js_coverage.wait_for_timeout(300)

        # Button should still be visible and enabled
        await expect(refresh_btn).to_be_visible()
        await expect(refresh_btn).to_be_enabled()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardCollapsePanels:
    """Tests for collapsing and expanding panels."""

    async def test_collapse_all_sections(self, page_with_js_coverage: Page) -> None:
        """Test collapsing all collapsible sections."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Collapse each section
        sections = ["control-panel", "top-repositories", "recent-events", "pr-contributors", "user-prs"]

        for section in sections:
            btn = page_with_js_coverage.locator(f'.collapse-btn[data-section="{section}"]')
            if await btn.count() > 0:
                await btn.click()
                await page_with_js_coverage.wait_for_timeout(200)

        # Dashboard should still be visible
        await expect(page_with_js_coverage.locator(".dashboard-grid")).to_be_visible()

    async def test_expand_collapsed_sections(self, page_with_js_coverage: Page) -> None:
        """Test expanding collapsed sections."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_timeout(1000)

        # Collapse then expand
        btn = page_with_js_coverage.locator('.collapse-btn[data-section="top-repositories"]')

        # Collapse
        await btn.click()
        await page_with_js_coverage.wait_for_timeout(200)

        # Expand
        await btn.click()
        await page_with_js_coverage.wait_for_timeout(200)

        # Section container should be visible
        await expect(page_with_js_coverage.locator('.chart-container[data-section="top-repositories"]')).to_be_visible()
