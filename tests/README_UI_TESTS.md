# UI Tests with Playwright

This directory contains Playwright-based UI tests for the GitHub Metrics dashboard.

## Prerequisites

1. **Install dependencies:**
   ```bash
   uv sync --group tests
   ```

2. **Install Playwright browsers:**
   ```bash
   uv run playwright install chromium
   ```

## Running the Tests

### Start the Development Server

Before running UI tests, you need to start the development server:

```bash
./dev/run.sh
```

The server will be available at:
- Dashboard: http://localhost:8765/dashboard
- API: http://localhost:8765/api/metrics/
- PostgreSQL: localhost:15432

### Run UI Tests

In a separate terminal, run the UI tests:

```bash
# Run all UI tests
uv run --group tests pytest tests/test_ui_dashboard.py -v

# Run specific test class
uv run --group tests pytest tests/test_ui_dashboard.py::TestDashboardPageLoad -v

# Run specific test
uv run --group tests pytest tests/test_ui_dashboard.py::TestDashboardPageLoad::test_dashboard_loads_successfully -v

# Run with headed browser (visible browser window)
uv run --group tests pytest tests/test_ui_dashboard.py --headed -v

# Run with slower execution for debugging
uv run --group tests pytest tests/test_ui_dashboard.py --slowmo 1000 -v
```

## Test Structure

### Test Classes

- **TestDashboardPageLoad**: Tests for initial page loading and rendering
- **TestDashboardControls**: Tests for user controls (filters, buttons, selectors)
- **TestDashboardTables**: Tests for data table structure and functionality
- **TestDashboardTheme**: Tests for theme toggle functionality
- **TestDashboardCollapsiblePanels**: Tests for collapsible panel behavior
- **TestDashboardAccessibility**: Tests for accessibility features (ARIA attributes)
- **TestDashboardStatusTooltip**: Tests for connection status tooltip
- **TestDashboardResponsiveness**: Tests for responsive design across viewports
- **TestDashboardStaticAssets**: Tests for static asset loading

### Test Coverage

The UI tests cover:
- Page loading and rendering
- All dashboard sections (Top Repositories, Recent Events, PR Contributors, Pull Requests)
- Control panel filters and buttons
- Data table structures and headers
- Theme toggle functionality
- Collapsible panels
- Accessibility features (ARIA labels, roles)
- Responsive design (mobile, tablet, desktop viewports)
- Static asset loading (CSS, JavaScript modules)

## Configuration

Playwright configuration is defined in `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def browser_context_args() -> dict[str, Any]:
    """Configure Playwright browser context."""
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
        "accept_downloads": False,
    }

@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, Any]:
    """Configure Playwright browser launch arguments."""
    return {
        "headless": True,
        "slow_mo": 0,  # No slow motion by default
    }
```

## Debugging

### Run with Headed Browser

To see the browser while tests run:

```bash
uv run --group tests pytest tests/test_ui_dashboard.py --headed
```

### Slow Down Execution

To slow down test execution for debugging:

```bash
uv run --group tests pytest tests/test_ui_dashboard.py --slowmo 500
```

### Playwright Inspector

Use Playwright's built-in inspector for debugging:

```bash
PWDEBUG=1 uv run --group tests pytest tests/test_ui_dashboard.py
```

### Screenshots on Failure

Playwright automatically captures screenshots on test failures. Check the test output for screenshot paths.

## CI/CD Integration

To run UI tests in CI/CD pipelines:

```bash
# Ensure browsers are installed
uv run playwright install --with-deps chromium

# Run tests in headless mode
uv run --group tests pytest tests/test_ui_dashboard.py -v
```

## Best Practices

1. **Use semantic selectors**: Prefer `data-testid`, `id`, or semantic HTML selectors over CSS classes
2. **Wait for elements**: Use Playwright's auto-waiting with `expect()` assertions
3. **Test behavior, not implementation**: Focus on user interactions and visible outcomes
4. **Keep tests independent**: Each test should be runnable in isolation
5. **Use meaningful test names**: Test names should clearly describe what is being tested

## Known Issues

- Some browsers may show warnings about unsupported OS on Fedora 43
- This is expected and does not affect test functionality (Playwright uses fallback builds)

## Additional Resources

- [Playwright Python Documentation](https://playwright.dev/python/)
- [pytest-playwright Plugin](https://github.com/microsoft/playwright-pytest)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)
