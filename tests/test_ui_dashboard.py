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

    async def test_dashboard_loads_successfully(self, page: Page) -> None:
        """Verify dashboard page loads without errors."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await expect(page).to_have_title("GitHub Metrics Dashboard")

    async def test_header_renders(self, page: Page) -> None:
        """Verify page header renders correctly."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check main heading
        heading = page.locator("h1")
        await expect(heading).to_have_text("GitHub Metrics Dashboard")

        # Check subtitle
        subtitle = page.locator("h1 + p")
        await expect(subtitle).to_have_text("Real-time monitoring of webhook processing metrics")

    async def test_connection_status_displays(self, page: Page) -> None:
        """Verify connection status element is visible."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check connection status container
        status = page.locator("#connection-status")
        await expect(status).to_be_visible()

        # Check status text element
        status_text = page.locator("#statusText")
        await expect(status_text).to_be_visible()

    async def test_control_panel_renders(self, page: Page) -> None:
        """Verify control panel renders with all controls."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Control panel should be visible
        control_panel = page.locator(".control-panel")
        await expect(control_panel).to_be_visible()

        # Check all filter groups
        time_range_select = page.locator("#time-range-select")
        await expect(time_range_select).to_be_visible()

        start_time = page.locator("#startTime")
        await expect(start_time).to_be_visible()

        end_time = page.locator("#endTime")
        await expect(end_time).to_be_visible()

        repository_filter = page.locator("#repositoryFilter")
        await expect(repository_filter).to_be_visible()

        user_filter = page.locator("#userFilter")
        await expect(user_filter).to_be_visible()

        refresh_button = page.locator("#refresh-button")
        await expect(refresh_button).to_be_visible()
        await expect(refresh_button).to_have_text("Refresh")

    async def test_all_dashboard_sections_render(self, page: Page) -> None:
        """Verify all dashboard sections are present."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Top Repositories section
        top_repos = page.locator('.chart-container[data-section="top-repositories"]')
        await expect(top_repos).to_be_visible()
        await expect(top_repos.locator("h2")).to_have_text("Top Repositories")

        # Recent Events section
        recent_events = page.locator('.chart-container[data-section="recent-events"]')
        await expect(recent_events).to_be_visible()
        await expect(recent_events.locator("h2")).to_have_text("Recent Events")

        # PR Contributors section
        pr_contributors = page.locator('.chart-container[data-section="pr-contributors"]')
        await expect(pr_contributors).to_be_visible()
        await expect(pr_contributors.locator("h2")).to_have_text("PR Contributors")

        # User PRs section
        user_prs = page.locator('.chart-container[data-section="user-prs"]')
        await expect(user_prs).to_be_visible()
        await expect(user_prs.locator("h2")).to_have_text("Pull Requests")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardControls:
    """Tests for dashboard control interactions."""

    async def test_time_range_selector_has_options(self, page: Page) -> None:
        """Test time range select has all expected options."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        time_range_select = page.locator("#time-range-select")
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

    async def test_time_range_selector_changes(self, page: Page) -> None:
        """Test time range selector can be changed."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        time_range_select = page.locator("#time-range-select")

        # Change to "Last Hour"
        await time_range_select.select_option("1h")
        await expect(time_range_select).to_have_value("1h")

        # Change to "Last 7 Days"
        await time_range_select.select_option("7d")
        await expect(time_range_select).to_have_value("7d")

    async def test_datetime_inputs_are_editable(self, page: Page) -> None:
        """Test datetime inputs can be edited."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        start_time = page.locator("#startTime")
        end_time = page.locator("#endTime")

        # Both should be editable
        await expect(start_time).to_be_editable()
        await expect(end_time).to_be_editable()

        # Fill with test values
        await start_time.fill("2024-11-01T10:00")
        await expect(start_time).to_have_value("2024-11-01T10:00")

        await end_time.fill("2024-11-30T18:00")
        await expect(end_time).to_have_value("2024-11-30T18:00")

    async def test_repository_filter_input(self, page: Page) -> None:
        """Test repository filter input field."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        repo_filter = page.locator("#repositoryFilter")
        await expect(repo_filter).to_be_visible()
        await expect(repo_filter).to_be_editable()
        await expect(repo_filter).to_have_attribute("placeholder", "Type to search or select...")

        # Type a repository name
        await repo_filter.fill("org/repo1")
        await expect(repo_filter).to_have_value("org/repo1")

    async def test_user_filter_input(self, page: Page) -> None:
        """Test user filter input field."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        user_filter = page.locator("#userFilter")
        await expect(user_filter).to_be_visible()
        await expect(user_filter).to_be_editable()
        await expect(user_filter).to_have_attribute("placeholder", "Type to search or select...")

        # Type a username
        await user_filter.fill("alice")
        await expect(user_filter).to_have_value("alice")

    async def test_refresh_button_clickable(self, page: Page) -> None:
        """Test refresh button is clickable."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        refresh_button = page.locator("#refresh-button")
        await expect(refresh_button).to_be_visible()
        await expect(refresh_button).to_be_enabled()

        # Click should not cause errors
        await refresh_button.click()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTables:
    """Tests for dashboard data tables."""

    async def test_top_repositories_table_structure(self, page: Page) -> None:
        """Verify top repositories table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#topRepositoriesTable")
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

    async def test_recent_events_table_structure(self, page: Page) -> None:
        """Verify recent events table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#recentEventsTable")
        await expect(table).to_be_visible()

        # Check headers
        headers = table.locator("thead th")
        await expect(headers).to_have_count(4)
        await expect(headers.nth(0)).to_have_text("Time")
        await expect(headers.nth(1)).to_have_text("Repository")
        await expect(headers.nth(2)).to_have_text("Event")
        await expect(headers.nth(3)).to_have_text("Status")

    async def test_pr_creators_table_structure(self, page: Page) -> None:
        """Verify PR creators table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#prCreatorsTable")
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

    async def test_pr_reviewers_table_structure(self, page: Page) -> None:
        """Verify PR reviewers table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#prReviewersTable")
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

    async def test_pr_approvers_table_structure(self, page: Page) -> None:
        """Verify PR approvers table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#prApproversTable")
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

    async def test_user_prs_table_structure(self, page: Page) -> None:
        """Verify user PRs table has correct structure."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        table = page.locator("#userPrsTable")
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

    async def test_sortable_table_headers(self, page: Page) -> None:
        """Verify table headers have sortable class."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Top repositories sortable headers
        top_repos_headers = page.locator("#topRepositoriesTable thead th.sortable")
        await expect(top_repos_headers).to_have_count(3)

        # Recent events sortable headers
        recent_events_headers = page.locator("#recentEventsTable thead th.sortable")
        await expect(recent_events_headers).to_have_count(4)

        # PR creators sortable headers
        pr_creators_headers = page.locator("#prCreatorsTable thead th.sortable")
        await expect(pr_creators_headers).to_have_count(5)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTheme:
    """Tests for theme toggle functionality."""

    async def test_theme_toggle_button_exists(self, page: Page) -> None:
        """Verify theme toggle button is present."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page.locator("#theme-toggle")
        await expect(theme_toggle).to_be_visible()
        await expect(theme_toggle).to_be_enabled()
        await expect(theme_toggle).to_have_attribute("title", "Toggle between light and dark theme")

    async def test_theme_toggle_button_clickable(self, page: Page) -> None:
        """Test theme toggle button can be clicked."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page.locator("#theme-toggle")

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

    async def test_control_panel_has_collapse_button(self, page: Page) -> None:
        """Verify control panel has collapse button."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page.locator('.control-panel .collapse-btn[data-section="control-panel"]')
        await expect(collapse_btn).to_be_visible()
        await expect(collapse_btn).to_have_text("▼")

    async def test_top_repositories_has_collapse_button(self, page: Page) -> None:
        """Verify top repositories section has collapse button."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page.locator('[data-section="top-repositories"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_recent_events_has_collapse_button(self, page: Page) -> None:
        """Verify recent events section has collapse button."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page.locator('[data-section="recent-events"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_pr_contributors_has_collapse_button(self, page: Page) -> None:
        """Verify PR contributors section has collapse button."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page.locator('[data-section="pr-contributors"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_user_prs_has_collapse_button(self, page: Page) -> None:
        """Verify user PRs section has collapse button."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        collapse_btn = page.locator('[data-section="user-prs"] .collapse-btn')
        await expect(collapse_btn).to_be_visible()

    async def test_collapse_button_clickable(self, page: Page) -> None:
        """Test collapse buttons are clickable."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Click top repositories collapse button
        collapse_btn = page.locator('[data-section="top-repositories"] .collapse-btn')
        await collapse_btn.click()

        # Button should still be visible after click
        await expect(collapse_btn).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardAccessibility:
    """Tests for dashboard accessibility features."""

    async def test_loading_spinner_has_aria_attributes(self, page: Page) -> None:
        """Verify loading spinner has proper ARIA attributes."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        spinner = page.locator("#loading-spinner")
        await expect(spinner).to_have_attribute("role", "status")
        await expect(spinner).to_have_attribute("aria-live", "polite")
        # aria-busy is dynamically set by JavaScript - "false" when hidden, "true" when visible
        await expect(spinner).to_have_attribute("aria-busy", "false")

    async def test_theme_toggle_has_aria_label(self, page: Page) -> None:
        """Verify theme toggle button has aria-label."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page.locator("#theme-toggle")
        await expect(theme_toggle).to_have_attribute("aria-label", "Toggle light or dark theme")

    async def test_table_headers_have_scope(self, page: Page) -> None:
        """Verify table headers have scope attribute."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check top repositories table headers
        top_repos_headers = page.locator("#topRepositoriesTable thead th")
        for i in range(3):
            await expect(top_repos_headers.nth(i)).to_have_attribute("scope", "col")

        # Check recent events table headers
        recent_events_headers = page.locator("#recentEventsTable thead th")
        for i in range(4):
            await expect(recent_events_headers.nth(i)).to_have_attribute("scope", "col")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardStatusTooltip:
    """Tests for connection status tooltip."""

    async def test_status_tooltip_exists(self, page: Page) -> None:
        """Verify status tooltip element exists."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        tooltip = page.locator(".status-tooltip")
        await expect(tooltip).to_be_attached()

    async def test_status_tooltip_has_kpi_elements(self, page: Page) -> None:
        """Verify status tooltip contains KPI elements."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check individual KPI elements
        await expect(page.locator("#tooltipTotalEvents")).to_be_attached()
        await expect(page.locator("#tooltipTotalEventsTrend")).to_be_attached()
        await expect(page.locator("#tooltipSuccessRate")).to_be_attached()
        await expect(page.locator("#tooltipSuccessRateTrend")).to_be_attached()
        await expect(page.locator("#tooltipFailedEvents")).to_be_attached()
        await expect(page.locator("#tooltipFailedEventsTrend")).to_be_attached()
        await expect(page.locator("#tooltipAvgDuration")).to_be_attached()
        await expect(page.locator("#tooltipAvgDurationTrend")).to_be_attached()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardResponsiveness:
    """Tests for dashboard responsive design."""

    async def test_dashboard_renders_on_mobile_viewport(self, page: Page) -> None:
        """Verify dashboard renders on mobile viewport."""
        await page.set_viewport_size({"width": 375, "height": 667})  # iPhone size
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Main elements should still be visible
        await expect(page.locator("h1")).to_be_visible()
        await expect(page.locator("#connection-status")).to_be_visible()
        await expect(page.locator(".control-panel")).to_be_visible()

    async def test_dashboard_renders_on_tablet_viewport(self, page: Page) -> None:
        """Verify dashboard renders on tablet viewport."""
        await page.set_viewport_size({"width": 768, "height": 1024})  # iPad size
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # All sections should be visible
        await expect(page.locator('.chart-container[data-section="top-repositories"]')).to_be_visible()
        await expect(page.locator('.chart-container[data-section="recent-events"]')).to_be_visible()
        await expect(page.locator('.chart-container[data-section="pr-contributors"]')).to_be_visible()

    async def test_dashboard_renders_on_desktop_viewport(self, page: Page) -> None:
        """Verify dashboard renders on desktop viewport."""
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Full dashboard should be visible
        await expect(page.locator(".dashboard-grid")).to_be_visible()
        await expect(page.locator('.chart-container[data-section="top-repositories"]')).to_be_visible()
        await expect(page.locator('.chart-container[data-section="recent-events"]')).to_be_visible()
        await expect(page.locator('.chart-container[data-section="pr-contributors"]')).to_be_visible()
        await expect(page.locator('.chart-container[data-section="user-prs"]')).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardStaticAssets:
    """Tests for dashboard static assets loading."""

    async def test_css_stylesheet_loads(self, page: Page) -> None:
        """Verify CSS stylesheet is linked."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check CSS link exists
        css_link = page.locator('link[href="/static/css/metrics_dashboard.css"]')
        await expect(css_link).to_be_attached()

    async def test_javascript_modules_load(self, page: Page) -> None:
        """Verify JavaScript modules are loaded."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check all JS modules are referenced
        await expect(page.locator('script[src="/static/js/metrics/utils.js"]')).to_be_attached()
        await expect(page.locator('script[src="/static/js/metrics/api-client.js"]')).to_be_attached()
        await expect(page.locator('script[src="/static/js/metrics/combo-box.js"]')).to_be_attached()
        await expect(page.locator('script[src="/static/js/metrics/charts.js"]')).to_be_attached()
        await expect(page.locator('script[src="/static/js/metrics/pr-story.js"]')).to_be_attached()
        await expect(page.locator('script[src="/static/js/metrics/dashboard.js"]')).to_be_attached()

    async def test_favicon_loads(self, page: Page) -> None:
        """Verify favicon is linked."""
        await page.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check favicon link exists
        favicon = page.locator('link[rel="icon"]')
        await expect(favicon).to_be_attached()
        await expect(favicon).to_have_attribute("type", "image/svg+xml")
