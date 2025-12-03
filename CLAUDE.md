# CLAUDE.md

## Internal API Philosophy

**CRITICAL: This is a self-contained metrics service, NOT a public Python module.**

### Backward Compatibility Policy

**NO backward compatibility required for internal APIs:**

- Internal methods in `github_metrics/` can change freely
- Return types can change (e.g., `Any` → `bool`)
- Method signatures can be modified without deprecation
- No version pinning or deprecation warnings needed

**Backward compatibility ONLY for:**

- Environment variable names (METRICS\_\*)
- REST API endpoints (/api/metrics/\*)
- Webhook payload handling (must follow GitHub webhook spec)

**Rationale:**

- This service is deployed as a single container
- All code is updated together - no external dependencies
- Internal refactoring is safe and encouraged
- Optimize for performance and clarity, not compatibility

### Anti-Defensive Programming

**CRITICAL: Eliminate unnecessary defensive programming overhead.**

**Philosophy:**

- This service fails-fast on startup if critical dependencies are missing
- Required parameters in `__init__()` are ALWAYS provided
- Checking for None on required parameters is pure overhead
- Defensive checks are ONLY acceptable for truly optional parameters
- **Fail-fast is better than hiding bugs with fake data**

---

## STRICT RULE: Linter Suppressions PROHIBITED

**CRITICAL: ALL forms of linter warning suppression are STRICTLY PROHIBITED.**

### Policy:
- ❌ **NEVER** add `# noqa` comments to suppress linter warnings
- ❌ **NEVER** use `# noqa: <code>` inline suppressions
- ❌ **NEVER** add `per-file-ignores` in `pyproject.toml`
- ❌ **NEVER** disable rules globally in `pyproject.toml` to work around issues
- ❌ **NEVER** use ANY workaround to bypass linter rules

### The ONLY Solution:
**FIX THE CODE.** If the linter complains, the code is wrong. Fix it properly.

### If you think a linter rule is wrong:
1. **STOP** - Do NOT add any suppression
2. **ASK** the user for explicit approval
3. **WAIT** for user response before proceeding
4. **DOCUMENT** the user's approval in the commit message

### Enforcement:
- Any PR containing `# noqa` comments → **REJECTED**
- Any PR adding `per-file-ignores` → **REJECTED**
- Any PR disabling linter rules → **REJECTED**
- User must **explicitly approve** any exception

**NO EXCEPTIONS. NO WORKAROUNDS. NO EXCUSES. FIX THE CODE.**

---

## WHEN Defensive Checks Are ACCEPTABLE

### 1. Destructors (`__del__`)

**Reason:** Can be called during failed initialization

```python
# ✅ CORRECT - __del__ can be called before __init__ completes
def __del__(self):
    if hasattr(self, "logger"):  # Legitimate - may not exist yet
        self.logger.debug("Cleanup")
```

### 2. Optional Parameters

**Reason:** Parameter explicitly allows None

```python
# ✅ CORRECT - start_time/end_time are optional in API
async def get_metrics(
    start_time: datetime | None = None,
    end_time: datetime | None = None
):
    if start_time:  # Legitimate check - parameter is optional
        query += " AND created_at >= $1"
```

### 3. Lazy Initialization

**Reason:** Attribute explicitly starts as None

```python
# ✅ CORRECT - pool starts as None by design
def __init__(self):
    self.pool: asyncpg.Pool | None = None  # Starts uninitialized

async def connect(self):
    if self.pool is None:  # Legitimate - lazy initialization
        self.pool = await asyncpg.create_pool(...)
```

---

## WHEN Defensive Checks Are VIOLATIONS

### 1. Required Parameters in `__init__()`

**VIOLATION:** Checking for attributes that are ALWAYS provided

```python
# ❌ WRONG - config is required parameter, ALWAYS provided
def __init__(self, config: MetricsConfig, logger: logging.Logger):
    self.config = config

def some_method(self):
    if self.config:  # VIOLATION - config is always present
        value = self.config.database.host

# ✅ CORRECT
def some_method(self):
    value = self.config.database.host  # No check needed
```

### 2. Webhook Payload Fields

**VIOLATION:** Checking for fields that are ALWAYS in GitHub webhooks

GitHub webhook format is stable:

- `sender` always exists in webhook payloads
- `repository.full_name` always exists
- `X-GitHub-Delivery` header always exists

```python
# ❌ WRONG - sender always exists in GitHub webhook
sender = payload.get("sender", {}).get("login", "unknown")

# ✅ CORRECT - Let it fail if data is malformed
sender = payload["sender"]["login"]  # KeyError = legitimate bug
```

---

## Fail-Fast Principle

**CRITICAL:** Fail-fast is better than hiding bugs with fake data.

### ❌ WRONG: Returning Fake Defaults

```python
# ❌ WRONG - Returns fake data hiding bugs
return ""           # Fake empty string
return 0            # Fake zero
return []           # Fake empty list (when data should exist)
return {}           # Fake empty dict (when data should exist)
```

### ✅ CORRECT: Fail-Fast

```python
# ✅ CORRECT - Fail-fast with clear error
raise ValueError("Data not available")  # Clear error
raise KeyError("Required field missing")  # Clear error
```

---

## Architecture Overview

This is a FastAPI-based metrics service that receives GitHub webhooks, stores event data in PostgreSQL, and provides a real-time dashboard for monitoring.

### Project Structure

```text
github_metrics/
├── app.py                    # Core app setup (350 lines)
│                            # - FastAPI application initialization
│                            # - Lifespan management (startup/shutdown)
│                            # - MCP server integration
│                            # - Database connection pooling
│                            # - Route registration
├── config.py                # Environment-based configuration
├── database.py              # DatabaseManager with asyncpg pool
├── metrics_tracker.py       # Webhook event storage and tracking
├── models.py                # SQLAlchemy 2.0 declarative models
├── pr_story.py              # Pull request timeline generation
├── routes/                  # Modular route handlers
│   ├── __init__.py
│   ├── health.py            # GET /health, GET /favicon.ico
│   ├── webhooks.py          # POST /metrics (webhook receiver)
│   ├── dashboard.py         # GET /dashboard
│   └── api/                 # REST API endpoints
│       ├── __init__.py
│       ├── webhooks.py      # GET /api/metrics/webhooks
│       ├── repositories.py  # GET /api/metrics/repositories
│       ├── summary.py       # GET /api/metrics/summary
│       ├── contributors.py  # GET /api/metrics/contributors
│       ├── user_prs.py      # GET /api/metrics/user-prs
│       ├── trends.py        # GET /api/metrics/trends
│       ├── pr_story.py      # GET /api/metrics/pr-story
│       └── turnaround.py    # GET /api/metrics/turnaround
├── utils/
│   ├── __init__.py
│   ├── security.py          # GitHub/Cloudflare IP validation, HMAC verification
│   ├── datetime_utils.py    # Timezone-aware datetime utilities
│   └── query_filters.py     # SQL query filter builders
└── web/
    ├── dashboard.py         # Jinja2 template rendering
    ├── templates/
    │   └── dashboard.html
    └── static/
        ├── css/
        │   └── dashboard.css
        └── js/
            └── metrics/
                ├── main.js          # Dashboard initialization
                ├── dashboard.js     # Main dashboard logic
                ├── navigation.js    # Sidebar navigation
                ├── turnaround.js    # Turnaround metrics
                └── ...
```

### Core Components

**Application (`github_metrics/app.py`):**

- FastAPI application initialization with CORS middleware
- Lifespan context manager for database connection pooling
- Route registration from modular route handlers
- MCP server integration for external tool access
- Database connection passed to route modules via module-level variables

**Routes (`github_metrics/routes/`):**

- Modular route handlers organized by functionality
- Each API route module has a `db_manager` module-level variable
- Set during app lifespan startup (before routes are called)
- Enables clean separation of routing logic from app setup

**Configuration (`github_metrics/config.py`):**

- Environment variable-based configuration (METRICS\_\*)
- No config files - all via environment variables
- Fail-fast on missing required variables

**Database (`github_metrics/database.py`):**

- DatabaseManager with asyncpg connection pool
- Async query execution (execute, fetch, fetchrow, fetchval)
- Health check support

**Models (`github_metrics/models.py`):**

- SQLAlchemy 2.0 declarative models
- Tables: webhooks, pull_requests, pr_events, pr_reviews, pr_labels, check_runs, api_usage
- PostgreSQL-specific types (UUID, JSONB)

**Security (`github_metrics/utils/security.py`):**

- GitHub IP allowlist verification
- Cloudflare IP allowlist verification
- Webhook signature validation (HMAC SHA256)

**Metrics Tracker (`github_metrics/metrics_tracker.py`):**

- Stores webhook events with full payload
- Tracks processing time and API usage

---

## Development Commands

### Environment Setup

```bash
# Install dependencies
uv sync

# Install with test dependencies
uv sync --extra tests
```

### Running the Server

```bash
# Set required environment variables
export METRICS_DB_NAME=github_metrics
export METRICS_DB_USER=metrics
export METRICS_DB_PASSWORD=your-password

# Run the server
uv run entrypoint.py
```

### Testing

**Two Test Suites:**

This project has separate test suites for API tests and UI tests. **Both must pass to declare all tests passed.**

```bash
# Run API tests (unit tests, integration tests)
tox

# Run UI tests (Playwright browser automation)
tox -e ui

# Run all tests (API + UI)
tox && tox -e ui
```

**API Tests (via `tox`):**
- Unit tests for API endpoints, database operations, utilities
- Integration tests with mocked database
- Fast execution (parallel with pytest-xdist)
- 90% code coverage required
- No external dependencies (uses mocks)

**UI Tests (via `tox -e ui`):**
- Playwright browser automation tests
- Tests against live development server
- Real user interactions: clicks, forms, navigation
- WebSocket real-time updates
- Full-stack integration testing
- Slower execution (requires browser + server)

**Individual Test Commands:**

```bash
# Run specific API test file
uv run --group tests pytest tests/test_app.py -v

# Run with coverage report
uv run --group tests pytest tests/ -n auto --cov=github_metrics --cov-report=term-missing

# Run specific UI test
uv run --group tests pytest tests/ui/test_dashboard.py -v

# Run UI tests with headed browser (see what's happening)
uv run --group tests pytest tests/ui/ --headed
```

### Running Tests in Parallel with Claude Code

When using Claude Code, run both test suites in parallel using two agents to reduce total test time:

**Parallel Execution Strategy:**
- Agent 1: `tox` (API tests - fast execution)
- Agent 2: `tox -e ui` (UI tests - slower execution with browser automation)

**Rationale:**
- UI tests take significantly longer due to browser automation and server startup
- Running both suites concurrently reduces overall test time by approximately 50%
- Both suites are independent and can run simultaneously without conflicts

**Example:**

```bash
# In parallel using two agents:
# Agent 1 (API tests):
tox

# Agent 2 (UI tests):
tox -e ui
```

Both test suites must pass to declare all tests successful.

### Development Server

For debugging and code verification, use the dev server at <http://localhost:8765/>

**Before making changes:**
1. Check if the dev server is already running (visit <http://localhost:8765/dashboard>)
2. If running, use it directly - the server has **hot reload** enabled, so no restart is needed when code changes
3. If not running, start it with: `./dev/run.sh`

**Use cases:**
- Verify frontend changes in the browser
- Check API responses in browser DevTools (Network tab)
- Debug JavaScript issues in browser Console
- Test UI interactions manually

**Note:** Always verify code changes in the browser before committing, especially for frontend/UI work.

### Code Quality

```bash
# Run all quality checks (pre-commit hooks)
prek run --all-files
```

---

## Critical Implementation Patterns

### Database Query Pattern

All database operations use asyncpg with parameterized queries:

```python
# ✅ CORRECT - Parameterized query
await db_manager.execute(
    "INSERT INTO webhooks (delivery_id, repository) VALUES ($1, $2)",
    delivery_id,
    repository,
)

# ❌ WRONG - SQL injection risk
await db_manager.execute(
    f"INSERT INTO webhooks (delivery_id) VALUES ('{delivery_id}')"
)
```

### Async Pattern

All I/O operations must be async:

```python
# ✅ CORRECT - Async database operations
async def get_webhook_events():
    rows = await db_manager.fetch("SELECT * FROM webhooks")
    return rows

# ❌ WRONG - Blocking call in async context
def get_webhook_events():
    return sync_db.execute("SELECT * FROM webhooks")
```

### Logging Pattern

```python
from simple_logger.logger import get_logger

LOGGER = get_logger(name="github_metrics.app")

# Use appropriate log levels
LOGGER.debug("Detailed technical information")
LOGGER.info("General information")
LOGGER.warning("Warning that needs attention")
LOGGER.exception("Error with full traceback")  # For exceptions
```

---

## Import Organization

**MANDATORY:** All imports must be at the top of files

- No imports in the middle of functions or try/except blocks
- Exceptions: TYPE_CHECKING imports can be conditional
- Pre-commit hooks enforce this

---

## Type Hints

**MANDATORY:** All functions must have complete type hints (mypy strict mode)

```python
# ✅ CORRECT
async def track_webhook_event(
    delivery_id: str,
    repository: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    ...

# ❌ WRONG
async def track_webhook_event(delivery_id, repository, event_type, payload):
    ...
```

---

## Test Coverage

**MANDATORY:** 90% code coverage required

- Use `uv run --extra tests pytest --cov=github_metrics` to check
- New code without tests will fail CI
- Tests must be in `tests/`

---

## Testing Patterns

### Test File Organization

```bash
tests/
├── conftest.py              # Shared fixtures
├── test_app.py              # FastAPI endpoint tests
├── test_config.py           # Configuration tests
├── test_database.py         # Database manager tests
├── test_metrics_tracker.py  # Metrics tracker tests
└── test_security.py         # Security utilities tests
```

### Mock Testing Pattern

```python
from unittest.mock import AsyncMock, Mock, patch

# Mock database manager
mock_db = AsyncMock()
mock_db.fetch.return_value = [{"delivery_id": "test-123"}]

# Mock with patch
with patch("github_metrics.app.db_manager", mock_db):
    response = client.get("/api/metrics/webhooks")
```

### Test Token Pattern

Use centralized test tokens to avoid security warnings:

```python
# At module level
TEST_WEBHOOK_SECRET = "test_secret_for_unit_tests"  # pragma: allowlist secret

# In fixtures
@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return Mock(
        webhook=Mock(secret=TEST_WEBHOOK_SECRET),
        database=Mock(host="localhost", port=5432),
    )
```

### Test File Naming

**MANDATORY:** Test file and test function names must be meaningful and related to the tested functionality.

**Rules:**
- Test file names must reflect the module being tested (e.g., `test_app.py` for `app.py`)
- Do NOT create generic files like `test_*_additional.py`, `test_*_coverage.py`, `test_*_extra.py`
- All tests for a module go in ONE test file (e.g., all app.py tests in `test_app.py`)
- Test function names must describe what is being tested (e.g., `test_webhook_endpoint_validates_signature`)

```python
# ❌ WRONG - Generic/meaningless file names
test_app_additional.py
test_app_coverage.py
test_database_extra.py

# ✅ CORRECT - One file per module
test_app.py          # All app.py tests
test_database.py     # All database.py tests
test_config.py       # All config.py tests
```

### UI Tests vs Unit Tests

**CRITICAL:** UI tests and unit tests have fundamentally different approaches.

**UI Tests (`tests/ui/`):**

- Run against the **live dev server** (no mocking)
- Use Playwright for browser automation
- Test real user interactions and full-stack behavior
- Require dev server to be running before test execution
- Automatically start/stop server process in test fixtures
- Test realistic scenarios: clicking buttons, filling forms, WebSocket connections
- Verify actual DOM elements, CSS rendering, JavaScript execution

```python
# ✅ CORRECT - UI test runs against real server
@pytest.mark.ui
async def test_dashboard_loads(page: Page):
    """Test dashboard page loads correctly."""
    await page.goto("http://localhost:8000/dashboard")
    await expect(page.locator("h1")).to_have_text("GitHub Metrics Dashboard")
```

**Unit Tests (`tests/test_*.py`):**

- Use mocking for database and external services
- Test individual components in isolation
- Fast execution without external dependencies
- Mock database connections, HTTP clients, file I/O
- Verify component behavior with controlled inputs

```python
# ✅ CORRECT - Unit test with mocking
@pytest.mark.asyncio
async def test_track_webhook_event(mock_db):
    """Test webhook event tracking with mocked database."""
    with patch("github_metrics.metrics_tracker.db_manager", mock_db):
        await track_webhook_event("delivery-123", "repo", "push", {})
        mock_db.execute.assert_called_once()
```

**When to Use Each:**

- **UI Tests:** User workflows, page navigation, form submissions, real-time updates, visual regression
- **Unit Tests:** API endpoints, database queries, utility functions, error handling, configuration parsing

---

## Security Considerations

### Dashboard Security

⚠️ **CRITICAL:** Dashboard endpoint (`/dashboard`) is unauthenticated by design

- Deploy only on trusted networks (VPN, internal network)
- Never expose to public internet without authentication
- Use reverse proxy with authentication for external access

### Token Handling

- Store tokens in environment variables
- Never commit tokens to repository
- Use secrets management in production

---

## Dashboard UI Guidelines

**MANDATORY:** All dashboard components must follow these UI/UX principles.

### Collapsible Sections

All data sections must be collapsible with expand/collapse controls:

```html
<!-- ✅ CORRECT - Section with collapse button -->
<div class="metrics-section">
    <div class="section-header">
        <h2>Pull Requests</h2>
        <button class="collapse-btn" onclick="toggleSection('pr-section')">▼</button>
    </div>
    <div id="pr-section" class="section-content">
        <!-- Section content -->
    </div>
</div>
```

### Shared Time Filters

Time range controls must be visible and functional on all pages:

- Time filters apply globally across all sections
- Persist selected time range across page navigation
- Supported ranges: Last 24h, Last 7 days, Last 30 days, Custom range
- Display current filter selection prominently

```javascript
// ✅ CORRECT - Shared time filter state
const timeFilter = {
    start: '2024-01-01T00:00:00Z',
    end: '2024-01-31T23:59:59Z'
};
// Apply to all API calls
```

### Table Features

All data tables must support:

**Sorting:**
- Click column headers to sort ascending/descending
- Visual indicator for current sort column and direction
- Default sort by most recent/relevant data

**Download:**
- CSV download button for raw data export
- JSON download button for programmatic access
- File naming: `{table_name}_{timestamp}.{format}`

**Pagination:**
- Paginate tables with > 50 rows
- Show row count and current page
- Configurable page size (25, 50, 100 rows)

```html
<!-- ✅ CORRECT - Table with all features -->
<div class="table-controls">
    <button onclick="downloadCSV('pull_requests')">📥 CSV</button>
    <button onclick="downloadJSON('pull_requests')">📥 JSON</button>
</div>
<table class="sortable-table">
    <thead>
        <tr>
            <th onclick="sortTable('pr', 'number')">PR # ▼</th>
            <th onclick="sortTable('pr', 'created')">Created ▲</th>
        </tr>
    </thead>
    <!-- Table body -->
</table>
```

### Theme Support

Implement light/dark mode using CSS variables:

**CSS Variables Pattern:**

```css
/* ✅ CORRECT - Theme-aware CSS variables */
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f5;
    --text-primary: #000000;
    --text-secondary: #666666;
    --border-color: #dddddd;
}

[data-theme="dark"] {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --text-primary: #ffffff;
    --text-secondary: #aaaaaa;
    --border-color: #444444;
}
```

**Theme Toggle:**

```html
<!-- ✅ CORRECT - Theme toggle button -->
<button onclick="toggleTheme()">🌙/☀️</button>

<script>
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}
</script>
```

### Responsive Design

Dashboard must be usable on mobile, tablet, and desktop:

**Breakpoints:**
- Mobile: < 768px (single column, stacked sections)
- Tablet: 768px - 1024px (two column where appropriate)
- Desktop: > 1024px (full layout)

**Mobile Optimizations:**
- Tables scroll horizontally on small screens
- Navigation collapses to hamburger menu
- Touch-friendly button sizes (min 44x44px)
- Readable font sizes (min 16px for body text)

```css
/* ✅ CORRECT - Responsive table */
@media (max-width: 768px) {
    .metrics-table {
        display: block;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }

    .section-header h2 {
        font-size: 1.25rem;  /* Smaller on mobile */
    }
}
```

### Accessibility

**MANDATORY:** Follow WCAG 2.1 AA standards:

- All interactive elements keyboard accessible
- ARIA labels for icon-only buttons
- Sufficient color contrast (4.5:1 for normal text)
- Focus indicators visible
- No content conveyed by color alone

```html
<!-- ✅ CORRECT - Accessible button -->
<button aria-label="Download as CSV" class="download-btn">
    📥 CSV
</button>

<!-- ❌ WRONG - No accessible label -->
<button class="download-btn">📥</button>
```
