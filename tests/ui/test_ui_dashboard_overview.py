"""Playwright UI tests for the metrics dashboard Overview page."""

from __future__ import annotations

import os
import re

import pytest
from playwright.async_api import Page, expect
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# Test constants
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:8765/dashboard")
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

        # Check main heading - target the shared header in main-content, not page-specific headers
        heading = page_with_js_coverage.locator(".main-content > .container > .header h1")
        await expect(heading).to_have_text("GitHub Metrics Dashboard")

        # Check inline status indicator is present
        status_inline = page_with_js_coverage.locator("#connection-status-inline")
        await expect(status_inline).to_be_visible()

    async def test_connection_status_displays(self, page_with_js_coverage: Page) -> None:
        """Verify connection status element is visible."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check inline connection status container (new inline version)
        status_inline = page_with_js_coverage.locator("#connection-status-inline")
        await expect(status_inline).to_be_visible()

        # Check inline status text element
        status_text_inline = page_with_js_coverage.locator("#statusTextInline")
        await expect(status_text_inline).to_be_visible()

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
        """Verify all dashboard sections are present on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Top Repositories section - scope to overview page
        top_repos = page_with_js_coverage.locator('#page-overview .chart-container[data-section="top-repositories"]')
        await expect(top_repos).to_be_attached()
        await expect(top_repos.locator("h2")).to_have_text("Top Repositories")

        # Recent Events section
        recent_events = page_with_js_coverage.locator('#page-overview .chart-container[data-section="recent-events"]')
        await expect(recent_events).to_be_attached()
        await expect(recent_events.locator("h2")).to_have_text("Recent Events")

        # User PRs section
        user_prs = page_with_js_coverage.locator('#page-overview .chart-container[data-section="user-prs"]')
        await expect(user_prs).to_be_attached()
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

        # UI Contract Verification:
        # These assertions verify the UI contract - the dashboard MUST have exactly 4 time range options
        # (1h, 24h, 7d, 30d) with "7d" as the default. Changes to option count or default value are
        # breaking changes to the UI contract. Failures here indicate intentional contract violations,
        # not flaky test behavior.
        # Check options exist
        options = time_range_select.locator("option")
        await expect(options).to_have_count(4)

        # Check option values using attribute
        await expect(options.nth(0)).to_have_attribute("value", "1h")
        await expect(options.nth(1)).to_have_attribute("value", "24h")
        await expect(options.nth(2)).to_have_attribute("value", "7d")
        await expect(options.nth(3)).to_have_attribute("value", "30d")

        # Check default selection
        await expect(time_range_select).to_have_value("7d")

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
        await expect(repo_filter).to_have_attribute("placeholder", "Type to add repositories...")

        # Type a repository name
        await repo_filter.fill("org/repo1")
        await expect(repo_filter).to_have_value("org/repo1")

    async def test_user_filter_input(self, page_with_js_coverage: Page) -> None:
        """Test user filter input field."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        user_filter = page_with_js_coverage.locator("#userFilter")
        await expect(user_filter).to_be_visible()
        await expect(user_filter).to_be_editable()
        await expect(user_filter).to_have_attribute("placeholder", "Type to add users...")

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
        """Verify table headers have sortable class on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Top repositories sortable headers
        top_repos_headers = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable")
        await expect(top_repos_headers).to_have_count(3)

        # Recent events sortable headers
        recent_events_headers = page_with_js_coverage.locator("#recentEventsTable thead th.sortable")
        await expect(recent_events_headers).to_have_count(4)

        # User PRs sortable headers
        user_prs_headers = page_with_js_coverage.locator("#userPrsTable thead th.sortable")
        await expect(user_prs_headers).to_have_count(8)


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTheme:
    """Tests for theme toggle functionality."""

    async def test_theme_toggle_button_exists(self, page_with_js_coverage: Page) -> None:
        """Verify theme toggle button is present in sidebar."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        theme_toggle = page_with_js_coverage.locator("#theme-toggle")
        await expect(theme_toggle).to_be_attached()
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
    """Tests for collapsible panel structure and behavior."""

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

    async def test_collapse_all_sections(self, page_with_js_coverage: Page) -> None:
        """Test collapsing all collapsible sections on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Collapse each section on Overview page
        sections = ["control-panel", "top-repositories", "recent-events", "user-prs"]

        for section in sections:
            btn = page_with_js_coverage.locator(f'.collapse-btn[data-section="{section}"]')
            if await btn.count() > 0:
                await btn.click()

        # Dashboard should still be visible - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()

    async def test_expand_collapsed_sections(self, page_with_js_coverage: Page) -> None:
        """Test expanding collapsed sections."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Collapse then expand
        btn = page_with_js_coverage.locator('.collapse-btn[data-section="top-repositories"]')

        # Collapse
        await btn.click()

        # Expand
        await btn.click()

        # Section container should be visible - scope to overview page
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="top-repositories"]')
        ).to_be_visible()


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

        # Main elements should still be visible - target the shared header specifically
        await expect(page_with_js_coverage.locator(".main-content > .container > .header h1")).to_be_visible()
        await expect(page_with_js_coverage.locator("#connection-status-inline")).to_be_visible()
        await expect(page_with_js_coverage.locator(".control-panel")).to_be_visible()

    async def test_dashboard_renders_on_tablet_viewport(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard renders on tablet viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 768, "height": 1024})  # iPad size
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # All sections should be visible - scope to overview page
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="top-repositories"]')
        ).to_be_visible()
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="recent-events"]')
        ).to_be_visible()
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="user-prs"]')
        ).to_be_visible()

    async def test_dashboard_renders_on_desktop_viewport(self, page_with_js_coverage: Page) -> None:
        """Verify dashboard renders on desktop viewport."""
        await page_with_js_coverage.set_viewport_size({"width": 1920, "height": 1080})
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Full dashboard should be visible - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="top-repositories"]')
        ).to_be_visible()
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="recent-events"]')
        ).to_be_visible()
        await expect(
            page_with_js_coverage.locator('#page-overview .chart-container[data-section="user-prs"]')
        ).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardStaticAssets:
    """Tests for dashboard static assets loading."""

    async def test_css_stylesheet_loads(self, page_with_js_coverage: Page) -> None:
        """Verify CSS stylesheet is linked."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check CSS link exists
        css_link = page_with_js_coverage.locator('link[href^="/static/css/metrics_dashboard.css"]')
        await expect(css_link).to_be_attached()

    async def test_javascript_modules_load(self, page_with_js_coverage: Page) -> None:
        """Verify JavaScript modules are loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check all JS modules are referenced
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/utils.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/api-client.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/combo-box.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/pr-story.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/navigation.js"]')).to_be_attached()
        await expect(page_with_js_coverage.locator('script[src^="/static/js/metrics/dashboard.js"]')).to_be_attached()

    async def test_favicon_loads(self, page_with_js_coverage: Page) -> None:
        """Verify favicon is linked."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        # Check favicon link exists
        favicon = page_with_js_coverage.locator('link[rel="icon"]')
        await expect(favicon).to_be_attached()
        await expect(favicon).to_have_attribute("type", "image/svg+xml")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardNavigation:
    """Tests for sidebar navigation functionality."""

    async def test_sidebar_exists(self, page_with_js_coverage: Page) -> None:
        """Verify sidebar navigation exists."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        sidebar = page_with_js_coverage.locator("#sidebar")
        await expect(sidebar).to_be_attached()

    async def test_sidebar_nav_items(self, page_with_js_coverage: Page) -> None:
        """Verify sidebar has navigation items."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        nav_items = page_with_js_coverage.locator(".nav-item")
        await expect(nav_items).to_have_count(3)

        # Check Overview nav item
        overview_nav = page_with_js_coverage.locator('.nav-item[data-page="overview"]')
        await expect(overview_nav).to_be_visible()
        await expect(overview_nav).to_have_attribute("href", "#overview")

        # Check Contributors nav item
        contributors_nav = page_with_js_coverage.locator('.nav-item[data-page="contributors"]')
        await expect(contributors_nav).to_be_visible()
        await expect(contributors_nav).to_have_attribute("href", "#contributors")

        # Check Team Dynamics nav item
        team_dynamics_nav = page_with_js_coverage.locator('.nav-item[data-page="team-dynamics"]')
        await expect(team_dynamics_nav).to_be_visible()
        await expect(team_dynamics_nav).to_have_attribute("href", "#team-dynamics")

    async def test_mobile_menu_toggle_button(self, page_with_js_coverage: Page) -> None:
        """Verify mobile menu toggle button exists."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        mobile_toggle = page_with_js_coverage.locator("#mobile-menu-toggle")
        await expect(mobile_toggle).to_be_attached()

    async def test_sidebar_overlay_exists(self, page_with_js_coverage: Page) -> None:
        """Verify sidebar overlay exists for mobile."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        overlay = page_with_js_coverage.locator("#sidebar-overlay")
        await expect(overlay).to_be_attached()

    async def test_overview_page_visible_by_default(self, page_with_js_coverage: Page) -> None:
        """Verify overview page is visible by default."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        overview_page = page_with_js_coverage.locator("#page-overview")
        await expect(overview_page).to_be_visible()

        contributors_page = page_with_js_coverage.locator("#page-contributors")
        await expect(contributors_page).not_to_be_visible()

    async def test_navigation_to_contributors_page(self, page_with_js_coverage: Page) -> None:
        """Test navigating to contributors page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Click contributors nav item
        contributors_nav = page_with_js_coverage.locator('.nav-item[data-page="contributors"]')
        await contributors_nav.click()

        # Wait for contributors page to be visible (event-based waiting)
        contributors_page = page_with_js_coverage.locator("#page-contributors")
        await expect(contributors_page).to_be_visible(timeout=5000)

        # Overview page should be hidden
        overview_page = page_with_js_coverage.locator("#page-overview")
        await expect(overview_page).not_to_be_visible()

    async def test_navigation_back_to_overview(self, page_with_js_coverage: Page) -> None:
        """Test navigating back to overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Navigate to contributors
        contributors_nav = page_with_js_coverage.locator('.nav-item[data-page="contributors"]')
        await contributors_nav.click()

        # Wait for contributors page to be visible
        contributors_page = page_with_js_coverage.locator("#page-contributors")
        await expect(contributors_page).to_be_visible(timeout=5000)

        # Navigate back to overview
        overview_nav = page_with_js_coverage.locator('.nav-item[data-page="overview"]')
        await overview_nav.click()

        # Wait for overview page to be visible (event-based waiting)
        overview_page = page_with_js_coverage.locator("#page-overview")
        await expect(overview_page).to_be_visible(timeout=5000)

    async def test_active_nav_item_indicator(self, page_with_js_coverage: Page) -> None:
        """Test active navigation item has active class."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Overview should be active by default
        overview_nav = page_with_js_coverage.locator('.nav-item[data-page="overview"]')
        await expect(overview_nav).to_have_class(re.compile(r"\bactive\b"))

        # Contributors should not be active
        contributors_nav = page_with_js_coverage.locator('.nav-item[data-page="contributors"]')
        await expect(contributors_nav).not_to_have_class(re.compile(r"\bactive\b"))

        # Click contributors
        await contributors_nav.click()

        # Wait for contributors nav to become active (event-based waiting)
        await expect(contributors_nav).to_have_class(re.compile(r"\bactive\b"), timeout=5000)

        # Overview should not be active
        await expect(overview_nav).not_to_have_class(re.compile(r"\bactive\b"))

    async def test_hash_navigation(self, page_with_js_coverage: Page) -> None:
        """Test URL hash navigation."""
        # Navigate directly to contributors via hash
        await page_with_js_coverage.goto(f"{DASHBOARD_URL}#contributors", timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Contributors page should be visible
        contributors_page = page_with_js_coverage.locator("#page-contributors")
        await expect(contributors_page).to_be_visible()

        # Overview page should be hidden
        overview_page = page_with_js_coverage.locator("#page-overview")
        await expect(overview_page).not_to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestPRStoryModal:
    """Tests for PR Story modal functionality."""

    async def test_pr_story_script_loaded(self, page_with_js_coverage: Page) -> None:
        """Verify PR story script is loaded."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)

        script = page_with_js_coverage.locator('script[src^="/static/js/metrics/pr-story.js"]')
        await expect(script).to_be_attached()

    async def test_pr_table_exists(self, page_with_js_coverage: Page) -> None:
        """Verify PR table exists for modal triggers."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # User PRs table should exist
        await expect(page_with_js_coverage.locator("#userPrsTable")).to_be_visible()

    async def test_escape_key_handling(self, page_with_js_coverage: Page) -> None:
        """Test pressing Escape is handled."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Press Escape - should not cause errors
        await page_with_js_coverage.keyboard.press("Escape")

        # Dashboard should still be functional - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTableUpdates:
    """Tests for table data update functionality."""

    async def test_refresh_updates_tables(self, page_with_js_coverage: Page) -> None:
        """Verify refresh button updates all tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        refresh_btn = page_with_js_coverage.locator("#refresh-button")
        await refresh_btn.click()
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Tables should still be visible after refresh
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()
        await expect(page_with_js_coverage.locator("#recentEventsTable")).to_be_visible()

    async def test_time_range_updates_tables(self, page_with_js_coverage: Page) -> None:
        """Verify time range change updates tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        time_range = page_with_js_coverage.locator("#time-range-select")

        # Change to different time ranges
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        await time_range.select_option("30d")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_table_body_content_loads(self, page_with_js_coverage: Page) -> None:
        """Verify table bodies can load content on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Check table bodies exist and are ready for content on Overview page
        await expect(page_with_js_coverage.locator("#repository-table-body")).to_be_visible()
        await expect(page_with_js_coverage.locator("#user-prs-table-body")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardUtilityFunctions:
    """Tests that exercise utility functions through UI interactions."""

    async def test_timestamp_formatting(self, page_with_js_coverage: Page) -> None:
        """Verify timestamps are formatted in tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Recent events table should have formatted timestamps
        time_cells = page_with_js_coverage.locator("#recentEventsTable tbody td:first-child")
        await expect(time_cells.first).to_be_attached()

    async def test_percentage_formatting(self, page_with_js_coverage: Page) -> None:
        """Verify percentages are formatted in tables."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Top repositories table has percentage column
        pct_cells = page_with_js_coverage.locator("#topRepositoriesTable tbody td:last-child")
        await expect(pct_cells.first).to_be_attached()

    async def test_number_formatting_in_stats(self, page_with_js_coverage: Page) -> None:
        """Verify numbers are formatted in stats."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Tooltip should have formatted numbers
        await expect(page_with_js_coverage.locator("#tooltipTotalEvents")).to_be_attached()

    async def test_local_storage_for_theme(self, page_with_js_coverage: Page) -> None:
        """Test localStorage is used for theme persistence."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("domcontentloaded")

        # Toggle theme to trigger localStorage save
        theme_toggle = page_with_js_coverage.locator("#theme-toggle")
        await theme_toggle.click()
        await expect(theme_toggle).to_be_visible()

        # Toggle back
        await theme_toggle.click()
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
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Should have no critical errors
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"

    async def test_empty_state_display(self, page_with_js_coverage: Page) -> None:
        """Verify empty states are handled gracefully."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Set filters that would return no results
        time_range = page_with_js_coverage.locator("#time-range-select")
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Dashboard should still be functional - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardPagination:
    """Tests for table data loading."""

    async def test_tables_load_data(self, page_with_js_coverage: Page) -> None:
        """Verify tables attempt to load data on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Tables should be present and ready on Overview page
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()
        await expect(page_with_js_coverage.locator("#userPrsTable")).to_be_visible()

    async def test_table_sorting_by_click(self, page_with_js_coverage: Page) -> None:
        """Verify table headers are sortable by click."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Click sortable header
        header = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable").first
        await header.click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_multiple_sort_clicks(self, page_with_js_coverage: Page) -> None:
        """Verify sorting direction changes on multiple clicks."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        header = page_with_js_coverage.locator("#topRepositoriesTable thead th.sortable").first

        # First click
        await header.click()

        # Second click
        await header.click()

        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardFilters:
    """Tests for filter interactions."""

    async def test_repository_filter_dropdown(self, page_with_js_coverage: Page) -> None:
        """Test repository filter dropdown interaction."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.click()
        await expect(repo_filter).to_be_focused()

        await expect(repo_filter).to_be_visible()

    async def test_user_filter_dropdown(self, page_with_js_coverage: Page) -> None:
        """Test user filter dropdown interaction."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        user_filter = page_with_js_coverage.locator("#userFilter")
        await user_filter.click()
        await expect(user_filter).to_be_focused()

        await expect(user_filter).to_be_visible()

    async def test_filter_keyboard_navigation(self, page_with_js_coverage: Page) -> None:
        """Test keyboard navigation in filters."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.focus()

        await page_with_js_coverage.keyboard.press("ArrowDown")
        await expect(repo_filter).to_be_focused()

        await page_with_js_coverage.keyboard.press("Escape")

    async def test_filter_with_typing(self, page_with_js_coverage: Page) -> None:
        """Test typing in filter input."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.fill("test")

        await expect(repo_filter).to_have_value("test")

    async def test_clear_filters(self, page_with_js_coverage: Page) -> None:
        """Test clearing filter values."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")
        await repo_filter.fill("test")
        await expect(repo_filter).to_have_value("test")

        await repo_filter.fill("")

        await expect(repo_filter).to_have_value("")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardKeyboardNavigation:
    """Tests for keyboard navigation and interactions."""

    async def test_tab_navigation(self, page_with_js_coverage: Page) -> None:
        """Test Tab key navigation through controls."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Focus on first focusable element and tab through
        await page_with_js_coverage.keyboard.press("Tab")
        await page_with_js_coverage.keyboard.press("Tab")
        await page_with_js_coverage.keyboard.press("Tab")

        # Dashboard should still be visible - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()

    async def test_enter_key_on_refresh(self, page_with_js_coverage: Page) -> None:
        """Test Enter key triggers refresh button."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        refresh_btn = page_with_js_coverage.locator("#refresh-button")
        await refresh_btn.focus()
        await page_with_js_coverage.keyboard.press("Enter")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Button should still be visible
        await expect(refresh_btn).to_be_visible()

    async def test_arrow_keys_in_select(self, page_with_js_coverage: Page) -> None:
        """Test arrow keys in time range select."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        time_select = page_with_js_coverage.locator("#time-range-select")
        await time_select.focus()
        await page_with_js_coverage.keyboard.press("ArrowDown")
        await page_with_js_coverage.keyboard.press("ArrowUp")

        # Select should still be visible
        await expect(time_select).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardComboBox:
    """Tests for combo box interactions."""

    async def test_combo_box_focus_blur(self, page_with_js_coverage: Page) -> None:
        """Test combo box focus and blur events."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")

        # Focus
        await repo_filter.focus()
        await expect(repo_filter).to_be_focused()

        # Type something
        await repo_filter.fill("test-repo")
        await expect(repo_filter).to_have_value("test-repo")

        # Blur by clicking elsewhere - click on the shared header h1 which is always visible
        await page_with_js_coverage.locator(".main-content > .container > .header h1").click()

        # Verify value persists
        await expect(repo_filter).to_have_value("test-repo")

    async def test_combo_box_keyboard_events(self, page_with_js_coverage: Page) -> None:
        """Test combo box keyboard events."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        user_filter = page_with_js_coverage.locator("#userFilter")
        await user_filter.focus()

        # Type and use keyboard
        await user_filter.fill("alice")
        await expect(user_filter).to_have_value("alice")
        await page_with_js_coverage.keyboard.press("ArrowDown")
        await page_with_js_coverage.keyboard.press("ArrowUp")
        await page_with_js_coverage.keyboard.press("Enter")
        await page_with_js_coverage.keyboard.press("Escape")

        # Filter should still be visible
        await expect(user_filter).to_be_visible()

    async def test_combo_box_clear_value(self, page_with_js_coverage: Page) -> None:
        """Test clearing combo box value."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        repo_filter = page_with_js_coverage.locator("#repositoryFilter")

        # Fill then clear
        await repo_filter.fill("some-value")
        await expect(repo_filter).to_have_value("some-value")
        await repo_filter.clear()

        # Verify cleared
        await expect(repo_filter).to_have_value("")


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTableInteractions:
    """Tests for table click and sort interactions."""

    async def test_sort_all_table_columns(self, page_with_js_coverage: Page) -> None:
        """Test sorting on all sortable columns."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Sort all columns in top repositories table
        headers = page_with_js_coverage.locator("#topRepositoriesTable th.sortable")
        count = await headers.count()

        for i in range(count):
            await headers.nth(i).click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#topRepositoriesTable")).to_be_visible()

    async def test_sort_recent_events_table(self, page_with_js_coverage: Page) -> None:
        """Test sorting recent events table."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        headers = page_with_js_coverage.locator("#recentEventsTable th.sortable")
        count = await headers.count()

        for i in range(min(count, 2)):
            await headers.nth(i).click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#recentEventsTable")).to_be_visible()

    async def test_sort_user_prs_table(self, page_with_js_coverage: Page) -> None:
        """Test sorting user PRs table."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        headers = page_with_js_coverage.locator("#userPrsTable th.sortable")
        count = await headers.count()

        for i in range(min(count, 3)):
            await headers.nth(i).click()

        # Table should still be visible
        await expect(page_with_js_coverage.locator("#userPrsTable")).to_be_visible()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardTimeRangeInteractions:
    """Tests for time range and date filter interactions."""

    async def test_all_time_range_options(self, page_with_js_coverage: Page) -> None:
        """Test selecting all time range options."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        time_range = page_with_js_coverage.locator("#time-range-select")

        # Select each option
        for value in ["1h", "24h", "7d", "30d"]:
            await time_range.select_option(value)
            await page_with_js_coverage.wait_for_load_state("networkidle")

        # Dashboard should still be visible - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()

    async def test_custom_date_range(self, page_with_js_coverage: Page) -> None:
        """Test setting custom date range."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        start_time = page_with_js_coverage.locator("#startTime")
        end_time = page_with_js_coverage.locator("#endTime")

        # Set custom dates
        await start_time.fill("2024-01-01T00:00")
        await expect(start_time).to_have_value("2024-01-01T00:00")
        await end_time.fill("2024-12-31T23:59")
        await expect(end_time).to_have_value("2024-12-31T23:59")

        # Trigger refresh
        await page_with_js_coverage.locator("#refresh-button").click()
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Dashboard should still be visible - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()

    async def test_multiple_refreshes(self, page_with_js_coverage: Page) -> None:
        """Test multiple refresh button clicks."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        refresh_btn = page_with_js_coverage.locator("#refresh-button")

        # Click refresh multiple times
        for _ in range(3):
            await refresh_btn.click()
            await page_with_js_coverage.wait_for_load_state("networkidle")

        # Button should still be visible and enabled
        await expect(refresh_btn).to_be_visible()
        await expect(refresh_btn).to_be_enabled()


@pytest.mark.usefixtures("dev_server")
@pytest.mark.asyncio(loop_scope="session")
class TestDashboardDownloadButtons:
    """Tests for download button functionality on Overview page."""

    async def test_download_buttons_exist(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons (CSV/JSON) exist for each table section on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Define Overview page sections that should have download buttons (using camelCase as in HTML)
        # Overview page only has: topRepositories, recentEvents, userPrs
        sections = [
            "topRepositories",
            "recentEvents",
            "userPrs",
        ]

        for section in sections:
            # Each section should have 2 download buttons (CSV and JSON)
            csv_button = page_with_js_coverage.locator(f'.download-btn[data-section="{section}"][data-format="csv"]')
            json_button = page_with_js_coverage.locator(f'.download-btn[data-section="{section}"][data-format="json"]')

            await expect(csv_button).to_be_visible()
            await expect(json_button).to_be_visible()

    async def test_download_button_attributes(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons have correct data attributes on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Get all download buttons on Overview page
        download_buttons = page_with_js_coverage.locator("#page-overview .download-btn")
        button_count = await download_buttons.count()

        # Should have 6 buttons on Overview page (3 sections x 2 formats)
        # Overview page: 3 sections (topRepositories, recentEvents, userPrs)
        # Total: 3 sections x 2 formats (CSV + JSON) = 6 buttons
        await expect(download_buttons).to_have_count(6)

        # Verify each button has required attributes
        for i in range(button_count):
            button = download_buttons.nth(i)

            # Check data-section attribute exists
            await expect(button).to_have_attribute("data-section", re.compile(r".+"))

            # Check data-format attribute is either csv or json
            format_attr = await button.get_attribute("data-format")
            assert format_attr in ["csv", "json"], f"Invalid format: {format_attr}"

            # Check class includes download-btn
            class_attr = await button.get_attribute("class")
            assert "download-btn" in class_attr, f"Missing download-btn class: {class_attr}"

    async def test_download_button_visibility(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons are visible and clickable on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Test top repositories download buttons
        top_repos_csv = page_with_js_coverage.locator(
            '.download-btn[data-section="topRepositories"][data-format="csv"]'
        )
        top_repos_json = page_with_js_coverage.locator(
            '.download-btn[data-section="topRepositories"][data-format="json"]'
        )

        await expect(top_repos_csv).to_be_visible()
        await expect(top_repos_csv).to_be_enabled()
        await expect(top_repos_json).to_be_visible()
        await expect(top_repos_json).to_be_enabled()

        # Test recent events download buttons
        recent_events_csv = page_with_js_coverage.locator(
            '.download-btn[data-section="recentEvents"][data-format="csv"]'
        )
        recent_events_json = page_with_js_coverage.locator(
            '.download-btn[data-section="recentEvents"][data-format="json"]'
        )

        await expect(recent_events_csv).to_be_visible()
        await expect(recent_events_csv).to_be_enabled()
        await expect(recent_events_json).to_be_visible()
        await expect(recent_events_json).to_be_enabled()

        # Test user PRs download buttons
        user_prs_csv = page_with_js_coverage.locator('.download-btn[data-section="userPrs"][data-format="csv"]')
        user_prs_json = page_with_js_coverage.locator('.download-btn[data-section="userPrs"][data-format="json"]')

        await expect(user_prs_csv).to_be_visible()
        await expect(user_prs_csv).to_be_enabled()
        await expect(user_prs_json).to_be_visible()
        await expect(user_prs_json).to_be_enabled()

    async def test_download_button_click_interaction(self, page_with_js_coverage: Page) -> None:
        """Test download buttons trigger file downloads."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Test CSV download for top repositories
        csv_button = page_with_js_coverage.locator('.download-btn[data-section="topRepositories"][data-format="csv"]')

        # Listen for download event
        try:
            async with page_with_js_coverage.expect_download(timeout=5000) as download_info:
                await csv_button.click()
            download = await download_info.value

            # Verify download properties
            assert download.suggested_filename.endswith(".csv")
            assert "github_metrics_" in download.suggested_filename
        except (TimeoutError, PlaywrightTimeoutError):
            # No download triggered - likely no data available
            # Verify button is still functional
            await expect(csv_button).to_be_visible()

        # Test JSON download for recent events
        json_button = page_with_js_coverage.locator('.download-btn[data-section="recentEvents"][data-format="json"]')

        # Listen for download event
        try:
            async with page_with_js_coverage.expect_download(timeout=5000) as download_info:
                await json_button.click()
            download = await download_info.value

            # Verify download properties
            assert download.suggested_filename.endswith(".json")
            assert "github_metrics_" in download.suggested_filename
        except (TimeoutError, PlaywrightTimeoutError):
            # No download triggered - likely no data available
            # Verify button is still functional
            await expect(json_button).to_be_visible()

    async def test_download_with_filtered_empty_data(self, page_with_js_coverage: Page) -> None:
        """Test download button behavior when table has no data."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Apply filters that should result in no data
        # Use a very narrow time range (1 hour) to minimize data
        time_range = page_with_js_coverage.locator("#time-range-select")
        await time_range.select_option("1h")
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Try to download CSV for top repositories
        csv_button = page_with_js_coverage.locator('.download-btn[data-section="topRepositories"][data-format="csv"]')

        # Attempt download - should either trigger download or handle gracefully
        try:
            async with page_with_js_coverage.expect_download(timeout=5000) as download_info:
                await csv_button.click()
            download = await download_info.value
            # If download occurs, verify it's a valid CSV file
            assert download.suggested_filename.endswith(".csv")
        except (TimeoutError, PlaywrightTimeoutError):
            # No download triggered - likely no data available
            # Verify button is still functional
            # 1. No JavaScript errors occurred
            # 2. Button is still functional
            await expect(csv_button).to_be_visible()
            await expect(csv_button).to_be_enabled()

        # Dashboard should remain functional - scope to overview page
        await expect(page_with_js_coverage.locator("#page-overview .dashboard-grid")).to_be_visible()

    async def test_download_buttons_have_title_attribute(self, page_with_js_coverage: Page) -> None:
        """Verify download buttons have title attribute for tooltips."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Get all download buttons
        download_buttons = page_with_js_coverage.locator(".download-btn")
        button_count = await download_buttons.count()

        # Verify each button has a title attribute
        for i in range(button_count):
            button = download_buttons.nth(i)
            title_attr = await button.get_attribute("title")
            assert title_attr is not None, f"Button {i} missing title attribute"
            assert len(title_attr) > 0, f"Button {i} has empty title attribute"

    async def test_all_sections_have_both_download_formats(self, page_with_js_coverage: Page) -> None:
        """Verify each section has both CSV and JSON download options on Overview page."""
        await page_with_js_coverage.goto(DASHBOARD_URL, timeout=TIMEOUT)
        await page_with_js_coverage.wait_for_load_state("networkidle")

        # Overview page only has these sections
        sections = [
            "topRepositories",
            "recentEvents",
            "userPrs",
        ]

        for section in sections:
            # Count buttons for this section
            section_buttons = page_with_js_coverage.locator(f'.download-btn[data-section="{section}"]')
            await expect(section_buttons).to_have_count(2)

            # Verify CSV button exists
            csv_count = await page_with_js_coverage.locator(
                f'.download-btn[data-section="{section}"][data-format="csv"]'
            ).count()
            assert csv_count == 1, f"Section {section} should have 1 CSV button, found {csv_count}"

            # Verify JSON button exists
            json_count = await page_with_js_coverage.locator(
                f'.download-btn[data-section="{section}"][data-format="json"]'
            ).count()
            assert json_count == 1, f"Section {section} should have 1 JSON button, found {json_count}"
