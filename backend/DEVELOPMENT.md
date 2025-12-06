# Backend Development Guide

## Overview

The backend is a FastAPI-based REST API and GitHub webhook receiver that provides metrics tracking and analytics.

**Technology Stack:**

- **Framework:** FastAPI with async/await pattern
- **Database:** PostgreSQL 16+ with asyncpg connection pool
- **Language:** Python 3.13+ with strict type hints
- **Configuration:** Environment variables (METRICS_*)
- **Package Manager:** uv (unified Python package manager)
- **Type Checking:** mypy strict mode
- **Testing:** pytest with asyncio support
- **Linting:** ruff (format + lint)

**Key Features:**

- GitHub webhook event processing and storage
- RESTful API for metrics queries
- Real-time analytics with PostgreSQL JSONB indexing
- Async database operations with connection pooling
- IP allowlist validation for webhooks
- HMAC signature verification

## Project Structure

```text
backend/
├── app.py                      # FastAPI app setup
│                              # - Application initialization
│                              # - Lifespan management (startup/shutdown)
│                              # - Route registration
│                              # - Static file serving
│                              # - Database connection pooling
├── config.py                   # Environment-based configuration
├── database.py                 # DatabaseManager with asyncpg pool
├── metrics_tracker.py          # Webhook event storage and tracking
├── models.py                   # SQLAlchemy 2.0 declarative models
├── pr_story.py                 # Pull request timeline generation
├── routes/
│   ├── __init__.py            # Route registration
│   ├── health.py              # GET /health, GET /favicon.ico
│   ├── webhooks.py            # POST /metrics (webhook receiver)
│   ├── dashboard.py           # GET /dashboard (UI entry point)
│   └── api/                   # REST API endpoints
│       ├── __init__.py
│       ├── webhooks.py        # GET /api/metrics/webhooks
│       ├── repositories.py    # GET /api/metrics/repositories
│       ├── summary.py         # GET /api/metrics/summary
│       ├── contributors.py    # GET /api/metrics/contributors
│       ├── user_prs.py        # GET /api/metrics/user-prs
│       ├── trends.py          # GET /api/metrics/trends
│       ├── pr_story.py        # GET /api/metrics/pr-story
│       ├── turnaround.py      # GET /api/metrics/turnaround
│       └── team_dynamics.py   # GET /api/metrics/team-dynamics
├── utils/
│   ├── __init__.py
│   ├── security.py            # IP validation, HMAC signature verification
│   ├── datetime_utils.py      # Timezone-aware datetime utilities
│   ├── query_builders.py      # SQL query construction with pagination
│   ├── response_formatters.py # API response formatting
│   └── contributor_queries.py # Role-based contributor queries (creators, reviewers)
├── migrations/                # Alembic database migrations
│   ├── env.py                 # Alembic environment configuration
│   ├── script.py.mako         # Migration template
│   └── versions/              # Migration files
└── web/
    ├── dashboard.py           # Jinja2 template rendering
    ├── templates/
    │   └── metrics_dashboard.html
    └── static/
        ├── css/
        │   └── metrics_dashboard.css
        └── js/
            └── metrics/
                ├── dashboard.js
                ├── navigation.js
                └── ...
```

## Getting Started

### Prerequisites

- **Python 3.13+** - Required for modern type hints and performance improvements
- **PostgreSQL 16+** - Required for JSONB indexing and performance features
- **uv** - Python package manager (install from https://github.com/astral-sh/uv)

### Installation

```bash
# Install all dependencies
uv sync

# Install with test dependencies
uv sync --extra tests
```

### Environment Setup

Create a `.env` file or export environment variables:

```bash
# Database configuration
export METRICS_DB_NAME=github_metrics
export METRICS_DB_USER=postgres
export METRICS_DB_PASSWORD=your-password
export METRICS_DB_HOST=localhost
export METRICS_DB_PORT=5432

# Server configuration
export METRICS_SERVER_HOST=0.0.0.0
export METRICS_SERVER_PORT=8765
export METRICS_SERVER_WORKERS=1

# Security configuration
export METRICS_WEBHOOK_SECRET=your-webhook-secret
export METRICS_VERIFY_GITHUB_IPS=true
export METRICS_VERIFY_CLOUDFLARE_IPS=false

# Optional: MCP server
export METRICS_MCP_ENABLED=false

# Optional: Automatic webhook setup
export METRICS_SETUP_WEBHOOK=false
export METRICS_GITHUB_TOKEN=ghp_your_token
export METRICS_WEBHOOK_URL=https://your-domain/metrics
export METRICS_REPOSITORIES=owner/repo1,owner/repo2
```

### Running the Server

```bash
# Direct execution
uv run entrypoint.py

# Using dev scripts
./dev/run.sh              # Backend only with PostgreSQL container
./dev/run-backend.sh      # Backend only (expects DB running)
./dev/run-all.sh          # Backend + Frontend together
```

Server will be available at:
- API: http://localhost:8765
- Dashboard: http://localhost:8765/dashboard
- Health check: http://localhost:8765/health

## Configuration

All configuration is done via environment variables with the `METRICS_` prefix.

### Database Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METRICS_DB_NAME` | Yes | - | PostgreSQL database name |
| `METRICS_DB_USER` | Yes | - | PostgreSQL username |
| `METRICS_DB_PASSWORD` | Yes | - | PostgreSQL password |
| `METRICS_DB_HOST` | No | `localhost` | PostgreSQL host |
| `METRICS_DB_PORT` | No | `5432` | PostgreSQL port |
| `METRICS_DB_MAX_CONNECTIONS` | No | `10` | Connection pool size |
| `METRICS_DB_MIN_CONNECTIONS` | No | `2` | Minimum connections |

### Server Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METRICS_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `METRICS_SERVER_PORT` | No | `8765` | Server port |
| `METRICS_SERVER_WORKERS` | No | `1` | Uvicorn worker processes |

### Security Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METRICS_WEBHOOK_SECRET` | Yes | - | GitHub webhook secret for HMAC validation |
| `METRICS_VERIFY_GITHUB_IPS` | No | `true` | Verify webhook source is from GitHub IPs |
| `METRICS_VERIFY_CLOUDFLARE_IPS` | No | `false` | Verify webhook source is from Cloudflare IPs |

### MCP Server Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METRICS_MCP_ENABLED` | No | `false` | Enable MCP server for external tool access |

### Webhook Setup Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METRICS_SETUP_WEBHOOK` | No | `false` | Automatically setup webhooks on startup |
| `METRICS_GITHUB_TOKEN` | Conditional | - | GitHub token (required if SETUP_WEBHOOK=true) |
| `METRICS_WEBHOOK_URL` | Conditional | - | Webhook URL (required if SETUP_WEBHOOK=true) |
| `METRICS_REPOSITORIES` | Conditional | - | Comma-separated repos (required if SETUP_WEBHOOK=true) |

## Development Patterns

### Database Operations

All database operations use asyncpg with parameterized queries to prevent SQL injection.

#### Correct Pattern - Parameterized Queries

```python
# ✅ CORRECT - Use $1, $2, $3 placeholders
await db_manager.execute(
    """
    INSERT INTO webhooks (delivery_id, repository, event_type)
    VALUES ($1, $2, $3)
    """,
    delivery_id,
    repository,
    event_type,
)

# ✅ CORRECT - Fetch with parameters
rows = await db_manager.fetch(
    "SELECT * FROM webhooks WHERE repository = $1 AND created_at > $2",
    repository,
    start_time,
)

# ✅ CORRECT - Single row
row = await db_manager.fetchrow(
    "SELECT * FROM webhooks WHERE delivery_id = $1",
    delivery_id,
)

# ✅ CORRECT - Single value
count = await db_manager.fetchval(
    "SELECT COUNT(*) FROM webhooks WHERE repository = $1",
    repository,
)
```

#### Anti-Pattern - SQL Injection Risk

```python
# ❌ WRONG - SQL injection vulnerability
await db_manager.execute(
    f"INSERT INTO webhooks (delivery_id) VALUES ('{delivery_id}')"
)

# ❌ WRONG - String formatting
await db_manager.execute(
    "SELECT * FROM webhooks WHERE repository = '%s'" % repository
)

# ❌ WRONG - f-string interpolation
await db_manager.fetch(
    f"SELECT * FROM webhooks WHERE created_at > '{start_time}'"
)
```

### Type Hints

All functions must have complete type hints. This is enforced by mypy in strict mode.

#### Correct Pattern - Complete Type Hints

```python
from typing import Any
from datetime import datetime

# ✅ CORRECT - Full type hints
async def track_webhook_event(
    delivery_id: str,
    repository: str,
    event_type: str,
    payload: dict[str, Any],
    timestamp: datetime,
) -> None:
    """Track webhook event in database."""
    await db_manager.execute(
        "INSERT INTO webhooks (...) VALUES ($1, $2, $3, $4, $5)",
        delivery_id,
        repository,
        event_type,
        payload,
        timestamp,
    )

# ✅ CORRECT - Return type annotation
async def get_webhook_count(repository: str) -> int:
    """Get total webhook count for repository."""
    count = await db_manager.fetchval(
        "SELECT COUNT(*) FROM webhooks WHERE repository = $1",
        repository,
    )
    return count or 0

# ✅ CORRECT - Optional parameters
async def get_metrics(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Get metrics with optional time filtering."""
    query = "SELECT * FROM webhooks WHERE 1=1"
    params: list[Any] = []

    if start_time:
        params.append(start_time)
        query += f" AND created_at >= ${len(params)}"

    if end_time:
        params.append(end_time)
        query += f" AND created_at <= ${len(params)}"

    return await db_manager.fetch(query, *params)
```

#### Anti-Pattern - Missing Type Hints

```python
# ❌ WRONG - No type hints (mypy will fail)
async def track_webhook_event(delivery_id, repository, event_type, payload):
    await db_manager.execute(...)

# ❌ WRONG - Missing return type
async def get_webhook_count(repository: str):
    return await db_manager.fetchval(...)

# ❌ WRONG - Using Any everywhere
async def get_metrics(start_time: Any, end_time: Any) -> Any:
    return await db_manager.fetch(...)
```

### Async Pattern

All I/O operations must be async to avoid blocking the event loop.

#### Correct Pattern - Async/Await

```python
# ✅ CORRECT - Async database operations
async def get_webhook_events() -> list[dict[str, Any]]:
    """Fetch all webhook events."""
    rows = await db_manager.fetch("SELECT * FROM webhooks")
    return [dict(row) for row in rows]

# ✅ CORRECT - Async API endpoint
@router.get("/api/metrics/webhooks")
async def webhooks_endpoint() -> dict[str, Any]:
    """Get webhook events."""
    events = await get_webhook_events()
    return {"events": events}

# ✅ CORRECT - Async with multiple operations
async def process_webhook(delivery_id: str, payload: dict[str, Any]) -> None:
    """Process webhook and update database."""
    # Both operations are async
    await store_webhook(delivery_id, payload)
    await update_metrics(delivery_id)
```

#### Anti-Pattern - Blocking Operations

```python
# ❌ WRONG - Synchronous database call blocks event loop
def get_webhook_events() -> list[dict[str, Any]]:
    rows = sync_db.execute("SELECT * FROM webhooks")  # Blocks!
    return rows

# ❌ WRONG - Mixing sync/async incorrectly
async def process_webhook(delivery_id: str, payload: dict[str, Any]) -> None:
    store_webhook(delivery_id, payload)  # Missing await!
    await update_metrics(delivery_id)
```

### Logging

Use the `simple_logger` package for consistent logging across the application.

#### Correct Pattern

```python
from simple_logger.logger import get_logger

# Module-level logger with descriptive name
LOGGER = get_logger(name="backend.metrics_tracker")

async def track_webhook(delivery_id: str, repository: str) -> None:
    """Track webhook event."""
    LOGGER.debug(f"Tracking webhook: {delivery_id} for {repository}")

    try:
        await db_manager.execute(...)
        LOGGER.info(f"Webhook {delivery_id} tracked successfully")
    except Exception as error:
        LOGGER.exception(f"Failed to track webhook {delivery_id}: {error}")
        raise

# Use appropriate log levels
LOGGER.debug("Detailed technical information")    # Development debugging
LOGGER.info("General information")                 # Normal operations
LOGGER.warning("Warning that needs attention")     # Potential issues
LOGGER.exception("Error with full traceback")      # For exceptions in except blocks
```

#### Log Level Guidelines

- `DEBUG` - Detailed technical information for development debugging
- `INFO` - General informational messages about normal operations
- `WARNING` - Warnings about potential issues or unusual situations
- `ERROR` - Error messages (use `LOGGER.exception()` in except blocks for full traceback)

### Adding New API Endpoints

Follow these steps to add a new API endpoint:

**1. Create Route File**

Create a new file in `backend/routes/api/` for your endpoint:

```python
# backend/routes/api/my_endpoint.py
from fastapi import APIRouter, Query
from typing import Any

from backend.database import DatabaseManager

router = APIRouter()

# Module-level database manager (set during app startup)
db_manager: DatabaseManager

async def set_db_manager(manager: DatabaseManager) -> None:
    """Set database manager for this module."""
    global db_manager
    db_manager = manager

@router.get("/api/metrics/my-endpoint")
async def my_endpoint(
    repository: str | None = Query(default=None, description="Filter by repository"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, description="Items per page"),
) -> dict[str, Any]:
    """My endpoint description."""
    # Query database
    query = "SELECT * FROM my_table WHERE 1=1"
    params: list[Any] = []

    if repository:
        params.append(repository)
        query += f" AND repository = ${len(params)}"

    # Add pagination
    offset = (page - 1) * page_size
    params.extend([page_size, offset])
    query += f" LIMIT ${len(params) - 1} OFFSET ${len(params)}"

    rows = await db_manager.fetch(query, *params)

    return {
        "data": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
    }
```

**2. Register Router**

Add your router to `backend/routes/__init__.py`:

```python
from backend.routes.api import my_endpoint

# In register_routes function:
await my_endpoint.set_db_manager(db_manager)
app.include_router(my_endpoint.router)
```

**3. Add Tests**

Create tests in `tests/test_my_endpoint.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_my_endpoint(client):
    """Test my endpoint returns data."""
    # Mock database response
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [
        {"id": 1, "name": "test"},
    ]

    with patch("backend.routes.api.my_endpoint.db_manager", mock_db):
        response = client.get("/api/metrics/my-endpoint?repository=test/repo")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "test"
```

**4. Update Documentation**

Add endpoint documentation to API docs and update CLAUDE.md if it introduces new patterns.

### Shared Utilities

The `backend/utils/` directory contains shared utility modules. Always check these before implementing new logic.

#### When to Use Each Utility Module

**`utils/query_builders.py` - SQL Query Construction**

Use for building complex SQL queries with filters and pagination:

```python
from backend.utils.query_builders import build_paginated_query, build_filters

# Build query with filters
filters, params = build_filters(
    repository=repository,
    start_time=start_time,
    end_time=end_time,
)

# Add pagination
query = f"SELECT * FROM webhooks WHERE {filters}"
paginated_query, params = build_paginated_query(query, params, page, page_size)

rows = await db_manager.fetch(paginated_query, *params)
```

**`utils/response_formatters.py` - API Response Formatting**

Use for formatting API responses with pagination metadata:

```python
from backend.utils.response_formatters import format_paginated_response

# Format response with pagination metadata
response = format_paginated_response(
    data=rows,
    page=page,
    page_size=page_size,
    total_count=total_count,
)
# Returns: {"data": [...], "page": 1, "page_size": 10, "total": 100, "pages": 10}
```

**`utils/contributor_queries.py` - Role-Based PR Queries**

Use for queries involving PR creators, reviewers, or approvers:

```python
from backend.utils.contributor_queries import (
    get_pr_creators,
    get_pr_reviewers,
    get_pr_approvers,
)

# Get all users who created PRs
creators = await get_pr_creators(db_manager, repository, start_time, end_time)

# Get all users who reviewed PRs
reviewers = await get_pr_reviewers(db_manager, repository, start_time, end_time)

# Get all users who approved PRs
approvers = await get_pr_approvers(db_manager, repository, start_time, end_time)
```

**`utils/datetime_utils.py` - Timezone-Aware Datetime Handling**

Use for parsing and formatting datetimes:

```python
from backend.utils.datetime_utils import (
    parse_iso_datetime,
    format_datetime,
    now_utc,
)

# Parse ISO 8601 datetime string
dt = parse_iso_datetime("2024-01-01T00:00:00Z")

# Format datetime for API response
formatted = format_datetime(dt)  # "2024-01-01T00:00:00Z"

# Get current UTC time
current_time = now_utc()
```

**`utils/security.py` - IP Validation and HMAC Verification**

Use for webhook security validation:

```python
from backend.utils.security import (
    verify_github_ip,
    verify_cloudflare_ip,
    verify_webhook_signature,
)

# Verify IP is from GitHub
if config.verify_github_ips:
    if not verify_github_ip(client_ip):
        raise HTTPException(status_code=403, detail="Invalid IP")

# Verify webhook signature
if not verify_webhook_signature(payload_body, signature, secret):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

#### Search Before Implementing

Before writing new query logic, response formatting, or datetime handling:

1. Search `utils/` for existing implementations
2. If found, use the shared function
3. If not found, consider adding it to the appropriate utility module
4. Never duplicate logic across files

## Testing

### Running Tests

```bash
# Run all API tests with tox (recommended)
tox

# Run all API tests directly
uv run --group tests pytest tests/ -n auto

# Run specific test file
uv run --group tests pytest tests/test_app.py -v

# Run specific test function
uv run --group tests pytest tests/test_app.py::test_health_endpoint -v

# Run with coverage report
uv run --group tests pytest tests/ -n auto --cov=backend --cov-report=term-missing

# Run UI tests (Playwright browser automation)
tox -e ui

# Run all tests (API + UI)
tox && tox -e ui
```

### Test Organization

#### One Test File Per Module

```text
tests/
├── conftest.py                  # Shared fixtures
├── test_app.py                  # Tests for app.py
├── test_config.py               # Tests for config.py
├── test_database.py             # Tests for database.py
├── test_metrics_tracker.py      # Tests for metrics_tracker.py
├── test_security.py             # Tests for utils/security.py
└── ui/
    └── test_dashboard.py        # UI tests (Playwright)
```

#### Rules

- ❌ NO generic test files like `test_app_additional.py`, `test_app_coverage.py`
- ✅ All tests for a module go in ONE test file
- ✅ Test function names must describe what is being tested

#### Example

```python
# ✅ CORRECT - Descriptive test names
def test_webhook_endpoint_validates_signature():
    """Test webhook endpoint validates HMAC signature."""
    ...

def test_webhook_endpoint_rejects_invalid_ip():
    """Test webhook endpoint rejects requests from invalid IPs."""
    ...

# ❌ WRONG - Generic names
def test_webhook_1():
    ...

def test_webhook_additional():
    ...
```

### Mocking Pattern

#### Mock Database Operations

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_track_webhook():
    """Test webhook tracking."""
    # Create mock database manager
    mock_db = AsyncMock()
    mock_db.execute.return_value = None
    mock_db.fetch.return_value = [{"delivery_id": "test-123"}]

    # Patch module-level db_manager
    with patch("backend.metrics_tracker.db_manager", mock_db):
        await track_webhook_event("test-123", "owner/repo", "push", {})

        # Verify database was called
        mock_db.execute.assert_called_once()
```

#### Mock Configuration

```python
from unittest.mock import Mock

@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return Mock(
        database=Mock(
            host="localhost",
            port=5432,
            name="test_db",
            user="test_user",
            password="test_password",  # pragma: allowlist secret
        ),
        webhook=Mock(
            secret="test_secret_for_unit_tests",  # pragma: allowlist secret
        ),
    )
```

### UI Tests vs Unit Tests

#### UI Tests (`tests/ui/`) - Live Server Testing

- Run against the live development server (no mocking)
- Use Playwright for browser automation
- Test real user interactions and full-stack behavior
- Require dev server to be running
- Test realistic scenarios: clicks, forms, navigation, WebSocket connections

```python
import pytest
from playwright.async_api import Page, expect

@pytest.mark.ui
async def test_dashboard_loads(page: Page):
    """Test dashboard page loads correctly."""
    await page.goto("http://localhost:8765/dashboard")
    await expect(page.locator("h1")).to_have_text("GitHub Metrics Dashboard")
```

#### Unit Tests (`tests/test_*.py`) - Isolated Component Testing

- Use mocking for database and external services
- Test individual components in isolation
- Fast execution without external dependencies
- Verify component behavior with controlled inputs

```python
@pytest.mark.asyncio
async def test_track_webhook_event(mock_db):
    """Test webhook event tracking with mocked database."""
    with patch("backend.metrics_tracker.db_manager", mock_db):
        await track_webhook_event("delivery-123", "repo", "push", {})
        mock_db.execute.assert_called_once()
```

#### When to Use Each

- **UI Tests:** User workflows, page navigation, form submissions, real-time updates
- **Unit Tests:** API endpoints, database queries, utility functions, error handling

## Code Quality

### Pre-Commit Hooks

Run all quality checks before committing:

```bash
# Run all pre-commit hooks
prek run --all-files

# Run on staged files only
prek run
```

#### Hooks Include

- ruff format (code formatting)
- ruff check (linting)
- mypy (type checking)
- pytest (tests with coverage)
- Import sorting and organization

### Individual Tools

```bash
# Format code
uvx ruff format backend/

# Lint code
uvx ruff check backend/

# Type checking
uvx mypy backend/

# Security checks
uvx bandit -r backend/
```

### Coverage Requirements

- **Minimum 90% code coverage required**
- Coverage checked in CI pipeline
- New code without tests will fail CI

```bash
# Check coverage
uv run --group tests pytest --cov=backend --cov-report=term-missing --cov-fail-under=90
```

## Database Migrations

The project uses Alembic for database schema migrations.

### Creating Migrations

```bash
# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "Description of changes"

# Create empty migration for custom SQL
uv run alembic revision -m "Description of changes"
```

**Migration files are created in `backend/migrations/versions/`**

### Applying Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Apply specific number of migrations
uv run alembic upgrade +1

# Rollback last migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade <revision_id>
```

### Migration History

```bash
# Show migration history
uv run alembic history

# Show current revision
uv run alembic current

# Show pending migrations
uv run alembic heads
```

### Migration Best Practices

- **Always review auto-generated migrations** before applying
- **Test migrations on development database** before production
- **Include both upgrade and downgrade** operations
- **Use descriptive migration messages**
- **Never edit applied migrations** - create new ones instead

## Anti-Patterns to Avoid

### No Defensive Programming for Required Parameters

#### VIOLATION - Checking Required Parameters

```python
# ❌ WRONG - config is required, always present
def __init__(self, config: MetricsConfig, logger: logging.Logger):
    self.config = config

def some_method(self):
    if self.config:  # Unnecessary check
        value = self.config.database.host
```

#### CORRECT - Use Required Parameters Directly

```python
# ✅ CORRECT - No defensive check needed
def __init__(self, config: MetricsConfig, logger: logging.Logger):
    self.config = config

def some_method(self):
    value = self.config.database.host  # Fail-fast if None
```

### No Fake Defaults

#### VIOLATION - Returning Fake Data

```python
# ❌ WRONG - Hides bugs with fake data
def get_repository_name(self) -> str:
    return self.repository or ""  # Fake empty string

def get_webhook_count(self) -> int:
    return self.count or 0  # Fake zero when should fail
```

#### CORRECT - Fail-Fast

```python
# ✅ CORRECT - Fail-fast with clear error
def get_repository_name(self) -> str:
    if not self.repository:
        raise ValueError("Repository name not available")
    return self.repository

def get_webhook_count(self) -> int:
    if self.count is None:
        raise ValueError("Count not calculated")
    return self.count
```

### No Linter Suppressions

#### VIOLATION - Suppressing Linters

```python
# ❌ WRONG - Never suppress linters
import unused_module  # noqa: F401
result = dangerous_operation()  # type: ignore

# ❌ WRONG - Never disable rules globally
# In pyproject.toml:
[tool.ruff.per-file-ignores]
"app.py" = ["F401", "E501"]
```

#### CORRECT - Fix the Code

```python
# ✅ CORRECT - Remove unused import
# (import statement removed)

# ✅ CORRECT - Fix type issues
result: int = dangerous_operation()  # Proper type annotation
```

#### If you think a linter rule is wrong

1. STOP - Do NOT add suppression
2. ASK the user for explicit approval
3. WAIT for user response
4. DOCUMENT the approval in commit message

### No Duplicate Logic

#### VIOLATION - Duplicate Query Logic

```python
# ❌ WRONG - Same logic in two files
# In contributors.py:
async def get_contributors():
    rows = await db_manager.fetch(
        "SELECT DISTINCT author FROM pull_requests WHERE repository = $1",
        repository,
    )

# In user_prs.py:
async def get_users():
    rows = await db_manager.fetch(
        "SELECT DISTINCT author FROM pull_requests WHERE repository = $1",
        repository,
    )
```

#### CORRECT - Shared Utility Function

```python
# ✅ CORRECT - In utils/contributor_queries.py
async def get_pr_creators(
    db_manager: DatabaseManager,
    repository: str | None = None,
) -> list[str]:
    """Get all users who created PRs."""
    query = "SELECT DISTINCT author FROM pull_requests WHERE 1=1"
    params: list[Any] = []

    if repository:
        params.append(repository)
        query += f" AND repository = ${len(params)}"

    rows = await db_manager.fetch(query, *params)
    return [row["author"] for row in rows]

# Use in both files:
from backend.utils.contributor_queries import get_pr_creators

contributors = await get_pr_creators(db_manager, repository)
```

### No SQL f-strings

#### VIOLATION - SQL Injection Risk

```python
# ❌ WRONG - SQL injection vulnerability
query = f"SELECT * FROM webhooks WHERE repository = '{repository}'"
rows = await db_manager.fetch(query)
```

#### CORRECT - Parameterized Queries

```python
# ✅ CORRECT - Safe parameterized query
query = "SELECT * FROM webhooks WHERE repository = $1"
rows = await db_manager.fetch(query, repository)
```

## Security

### Webhook Signature Validation

All incoming webhooks must validate HMAC SHA256 signatures:

```python
from backend.utils.security import verify_webhook_signature

# In webhook endpoint
signature = request.headers.get("X-Hub-Signature-256", "")
payload_body = await request.body()

if not verify_webhook_signature(payload_body, signature, config.webhook.secret):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

### IP Allowlist

Optionally verify webhook source IP is from GitHub or Cloudflare:

```python
from backend.utils.security import verify_github_ip, verify_cloudflare_ip

client_ip = request.client.host

if config.verify_github_ips:
    if not verify_github_ip(client_ip):
        raise HTTPException(status_code=403, detail="Invalid source IP")

if config.verify_cloudflare_ips:
    if not verify_cloudflare_ip(client_ip):
        raise HTTPException(status_code=403, detail="Invalid source IP")
```

### Secrets Management

- **Never commit secrets to repository**
- **Store secrets in environment variables**
- **Use secrets management in production** (e.g., AWS Secrets Manager, HashiCorp Vault)
- **Rotate webhook secrets regularly**
- **Use test secrets in unit tests** with `# pragma: allowlist secret` comment

```python
# ✅ CORRECT - Test secret with pragma comment
TEST_WEBHOOK_SECRET = "test_secret_for_unit_tests"  # pragma: allowlist secret
```

## Debugging

### Enable Debug Logging

```bash
export METRICS_LOG_LEVEL=DEBUG
uv run entrypoint.py
```

### Database Query Logging

Enable PostgreSQL query logging in `database.py`:

```python
# Add to DatabaseManager.execute/fetch methods
LOGGER.debug(f"Executing query: {query} with params: {params}")
```

### Hot Reload

The dev server has hot reload enabled. Code changes are automatically detected and the server restarts.

### Accessing the Database

```bash
# Connect to PostgreSQL directly
psql -h localhost -U postgres -d github_metrics

# View webhook events
SELECT delivery_id, repository, event_type, created_at FROM webhooks ORDER BY created_at DESC LIMIT 10;

# View pull requests
SELECT number, title, author, state, created_at FROM pull_requests ORDER BY created_at DESC LIMIT 10;
```

## Performance Optimization

### Database Indexing

Ensure proper indexes exist for query performance:

```sql
-- Indexes for webhook queries
CREATE INDEX idx_webhooks_repository ON webhooks(repository);
CREATE INDEX idx_webhooks_created_at ON webhooks(created_at);
CREATE INDEX idx_webhooks_event_type ON webhooks(event_type);

-- JSONB indexes for payload queries
CREATE INDEX idx_webhooks_payload_sender ON webhooks USING GIN ((payload->'sender'));
```

### Connection Pooling

Adjust connection pool size based on load:

```bash
# Increase pool size for high traffic
export METRICS_DB_MAX_CONNECTIONS=20
export METRICS_DB_MIN_CONNECTIONS=5
```

### Query Optimization

- Use `EXPLAIN ANALYZE` to understand query performance
- Add indexes for frequently queried columns
- Use pagination for large result sets
- Avoid `SELECT *` - specify needed columns
- Use JSONB operators efficiently

```python
# ✅ CORRECT - Efficient JSONB query
await db_manager.fetch(
    "SELECT delivery_id FROM webhooks WHERE payload->>'action' = $1",
    "opened",
)

# ❌ WRONG - Fetching full payload
rows = await db_manager.fetch("SELECT * FROM webhooks")
filtered = [r for r in rows if r["payload"].get("action") == "opened"]
```

## Troubleshooting

### Common Issues

#### Database Connection Errors

```text
Error: FATAL:  password authentication failed for user "postgres"
```

Solution: Verify environment variables are set correctly:

```bash
echo $METRICS_DB_USER
echo $METRICS_DB_PASSWORD
```

#### Port Already in Use

```text
Error: [Errno 48] Address already in use
```

Solution: Kill process using port 8765 or change port:

```bash
lsof -ti:8765 | xargs kill -9
# Or change port
export METRICS_SERVER_PORT=8766
```

#### Migration Errors

```text
Error: Can't locate revision identified by '<revision_id>'
```

Solution: Reset migration head:

```bash
uv run alembic stamp head
```

### Getting Help

- Check logs in console output
- Review GitHub webhook delivery logs
- Check PostgreSQL logs
- Use `LOGGER.debug()` for detailed logging
- Consult CLAUDE.md for project-specific patterns
