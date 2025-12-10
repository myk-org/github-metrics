# CLAUDE.md

## Strict Rules (MANDAORY)

### Linter Suppressions PROHIBITED

- ❌ **NEVER** add `# noqa`, `# type: ignore`, `per-file-ignores`
- ❌ **NEVER** disable linter rules to work around issues
- ✅ **FIX THE CODE** - If linter complains, the code is wrong
- If you think a rule is wrong: **ASK** the user for explicit approval

### Code Reuse (Search-First Development)

Before writing ANY new code:

1. **SEARCH** codebase for existing implementations
2. **CHECK** `backend/utils/` for shared functions
3. **VERIFY** no similar logic exists elsewhere
4. **NEVER** duplicate logic - extract to shared module

| Logic Type                                       | Location                       |
| ------------------------------------------------ | ------------------------------ |
| Role-based queries (PR creators, reviewers)      | `utils/contributor_queries.py` |
| SQL query building (params, filters, pagination) | `utils/query_builders.py`      |
| Response formatting (pagination metadata)        | `utils/response_formatters.py` |
| Time/date utilities                              | `utils/datetime_utils.py`      |
| Security (IP validation, HMAC)                   | `utils/security.py`            |

### Python Backend Requirements

- **Type hints MANDATORY** - mypy strict mode, no `Any`
- **90% test coverage MANDATORY** - Tests fail below 90%
- **Async everywhere** - All I/O operations must be async
- **Parameterized queries** - Never f-strings in SQL
- **Fail-fast principle** - No fake defaults (`""`, `0`, `[]`, `{}`)

### React Frontend Requirements

- **Strict TypeScript** - No `any`, no type assertions without justification
- **shadcn/ui ONLY** - Never create custom UI components
- **Use `bun`** - Never `npm` or `yarn`
- **React Query** - All API calls via `@tanstack/react-query`
- **All props typed** - Define interfaces in `src/types/`

---

## Project Architecture

**Stack:** FastAPI (Python) + React (TypeScript) + PostgreSQL + shadcn/ui

**Deployment:** Single container serving both backend API and frontend static files

### Directory Structure

```text
backend/                    # Python FastAPI backend
├── app.py                  # FastAPI app, lifespan, route registration
├── config.py               # Environment-based config (METRICS_*)
├── database.py             # DatabaseManager with asyncpg pool
├── metrics_tracker.py      # Webhook event storage
├── models.py               # SQLAlchemy 2.0 models
├── pr_story.py             # PR timeline generation
├── routes/
│   ├── health.py           # GET /health
│   ├── webhooks.py         # POST /metrics (webhook receiver)
│   └── api/                # REST API endpoints
│       ├── webhooks.py     # GET /api/metrics/webhooks
│       ├── repositories.py # GET /api/metrics/repositories
│       ├── summary.py      # GET /api/metrics/summary
│       ├── contributors.py # GET /api/metrics/contributors
│       ├── user_prs.py     # GET /api/metrics/user-prs
│       ├── trends.py       # GET /api/metrics/trends
│       ├── pr_story.py     # GET /api/metrics/pr-story
│       └── turnaround.py   # GET /api/metrics/turnaround
├── utils/
│   ├── security.py         # GitHub/Cloudflare IP validation, HMAC
│   ├── datetime_utils.py   # Timezone-aware datetime utilities
│   ├── query_builders.py   # SQL query builders
│   └── response_formatters.py # API response formatting
└── migrations/             # Alembic database migrations

frontend/                   # React + TypeScript + shadcn/ui
├── src/
│   ├── components/
│   │   ├── ui/             # shadcn components (DO NOT modify)
│   │   ├── dashboard/      # Dashboard-specific components
│   │   ├── layout/         # App layout (sidebar, header)
│   │   └── shared/         # Reusable components (tables, filters)
│   ├── pages/              # Page components (overview, repos, etc.)
│   ├── hooks/              # Custom hooks (useApi, useFilters)
│   ├── types/              # TypeScript interfaces
│   └── contexts/           # React contexts (theme, filters)
├── package.json            # Frontend dependencies
└── vite.config.ts          # Vite config with proxy to backend

dev/                        # Development scripts
├── run.sh                  # Backend only (with PostgreSQL)
├── run-all.sh              # Backend + Frontend dev servers
├── run-frontend.sh         # Frontend only
├── run-backend.sh          # Backend only
├── docker-compose.yml      # PostgreSQL for development
└── dev-container.sh        # Run containerized app

tests/                      # Test suite
├── conftest.py             # Shared fixtures
├── test_*.py               # Unit tests (mocked database)
└── ui/                     # Playwright UI tests (live server)
```

---

## Development Workflow

### Environment Setup

```bash
# Install Python dependencies
uv sync --extra tests

# Install frontend dependencies
cd frontend && bun install
```

### Running Development Servers

```bash
# Backend only (http://localhost:8765)
./dev/run.sh

# Frontend only (http://localhost:3003)
./dev/run-frontend.sh

# Both servers together
./dev/run-all.sh

# Containerized app (production-like)
./dev/dev-container.sh
```

**Note:** Backend has hot reload enabled - no restart needed for code changes.

### Testing

**All tests must pass - run in parallel:**

```bash
tox                                        # API tests (unit + integration)
tox -e ui                                  # UI tests (Playwright)
docker build -t github-metrics-testing .   # Docker build verification
bun run lint                               # Frontend linting
prek run --all-files                       # Pre-commit hooks (Python linting, formatting, type checking)
```

**Run tests in parallel with Claude Code:**

- Agent 1: `tox` (API tests)
- Agent 2: `tox -e ui` (UI tests - requires browser)
- Agent 3: `docker build -t github-metrics-testing .` (Docker build)
- Agent 4: `bun run lint` (Frontend linting)
- Agent 5: `prek run --all-files` (Pre-commit hooks)

### Code Quality

```bash
# Pre-commit hooks (linting, formatting, type checking)
prek run --all-files

# Frontend linting
cd frontend && bun run lint
```

---

## Backend Development

### Configuration

Environment variables only (no config files):

```bash
export METRICS_DB_NAME=github_metrics
export METRICS_DB_USER=metrics
export METRICS_DB_PASSWORD=your-password
export METRICS_DB_HOST=localhost
export METRICS_DB_PORT=5432
export METRICS_WEBHOOK_SECRET=your-webhook-secret
```

### Database Patterns

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

### Type Hints

```python
# ✅ CORRECT - Complete type hints
async def get_metrics(
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> list[dict[str, Any]]:
    ...

# ❌ WRONG - No types
async def get_metrics(start_time, end_time):
    ...
```

### Anti-Defensive Programming

**Fail-fast is better than hiding bugs with fake data.**

**When defensive checks are ACCEPTABLE:**

- Destructors (`__del__`) - can be called during failed init
- Optional parameters - explicitly allow `None`
- Lazy initialization - attribute starts as `None` by design

**When defensive checks are VIOLATIONS:**

- Required parameters in `__init__()` - ALWAYS provided
- GitHub webhook fields - stable format, let it fail if malformed

```python
# ❌ WRONG - Checking required parameter
def __init__(self, config: MetricsConfig):
    self.config = config

def method(self):
    if self.config:  # VIOLATION - config always exists
        value = self.config.database.host

# ✅ CORRECT - No check
def method(self):
    value = self.config.database.host
```

### Logging

```python
from simple_logger.logger import get_logger

LOGGER = get_logger(name="backend.app")

LOGGER.debug("Detailed information")
LOGGER.info("General information")
LOGGER.warning("Warning")
LOGGER.exception("Error with traceback")  # For exceptions
```

---

## Frontend Development

### Package Manager

**Use `bun` for ALL frontend operations (never `npm` or `yarn`):**

```bash
cd frontend
bun install
bun run dev
bun run lint
bunx shadcn@latest add <component>
```

### TypeScript Rules

```typescript
// ✅ CORRECT - Fully typed component
interface SummaryCardsProps {
  readonly metrics: MetricsSummary;
  readonly isLoading: boolean;
  readonly onRefresh: () => void;
}

export function SummaryCards({
  metrics,
  isLoading,
  onRefresh,
}: SummaryCardsProps): JSX.Element {
  // implementation
}

// ❌ WRONG - No types
export function SummaryCards(props) {
  // ...
}
```

### shadcn/ui Components

**MANDATORY: All UI components MUST use shadcn/ui. NO custom implementations.**

**Installing components:**

```bash
cd frontend
bunx shadcn@latest add button
bunx shadcn@latest add card
bunx shadcn@latest add table
bunx shadcn@latest add dialog
bunx shadcn@latest add dropdown-menu
bunx shadcn@latest add select
bunx shadcn@latest add command    # Multi-select, autocomplete
bunx shadcn@latest add calendar
bunx shadcn@latest add sidebar
bunx shadcn@latest add skeleton   # Loading states
```

**Composing custom components:**

```typescript
// ✅ CORRECT - Compose from shadcn
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableHead, TableRow, TableCell } from "@/components/ui/table";

export function RepositoriesTable({ data }: Props) {
  return (
    <Card>
      <CardHeader>Repositories</CardHeader>
      <CardContent>
        <Table>
          {/* Use shadcn table components */}
        </Table>
      </CardContent>
    </Card>
  );
}

// ❌ WRONG - Custom HTML structure
export function RepositoriesTable({ data }: Props) {
  return (
    <div className="custom-card">
      <table className="custom-table">
        {/* FORBIDDEN */}
      </table>
    </div>
  );
}
```

### Data Fetching

Use React Query for all API calls:

```typescript
// Define hook in src/hooks/
export function useRepositories(filters: FilterState) {
  return useQuery({
    queryKey: ["repositories", filters],
    queryFn: async (): Promise<RepositoryData> => {
      const response = await fetch(
        `/api/metrics/repositories?${new URLSearchParams(filters)}`,
      );
      if (!response.ok) {
        throw new Error(`Failed to fetch repositories: ${response.statusText}`);
      }
      return response.json() as Promise<RepositoryData>;
    },
    retry: 1,
    staleTime: 1000 * 60 * 5,
  });
}

// Use in component
const { data, isLoading, error } = useRepositories(filters);
```

---

## Testing

### Test File Organization

```text
tests/
├── conftest.py              # Shared fixtures
├── test_app.py              # FastAPI endpoint tests
├── test_database.py         # Database manager tests
├── test_metrics_tracker.py  # Metrics tracker tests
└── ui/
    ├── conftest.py          # Playwright fixtures
    └── test_dashboard.py    # Browser automation tests
```

### Unit Tests (API)

Use mocking for database and external services:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_track_webhook_event():
    """Test webhook event tracking."""
    mock_db = AsyncMock()
    with patch("backend.metrics_tracker.db_manager", mock_db):
        await track_webhook_event("delivery-123", "repo", "push", {})
        mock_db.execute.assert_called_once()
```

### UI Tests (Playwright)

Run against live dev server (no mocking):

```python
@pytest.mark.ui
async def test_dashboard_loads(page: Page):
    """Test dashboard page loads."""
    await page.goto("http://localhost:8000/dashboard")
    await expect(page.locator("h1")).to_have_text("GitHub Metrics")
```

### Test File Naming

- **ONE test file per module** (e.g., `test_app.py` for `app.py`)
- **NO generic files** like `test_app_additional.py`, `test_app_coverage.py`
- **Descriptive function names** (e.g., `test_webhook_endpoint_validates_signature`)

---

## API Design Principles

### No Artificial Result Limits

**MANDATORY: Neither API nor frontend may impose artificial limits on data access.**

```python
# ❌ WRONG - Artificial limits
page_size: int = Query(default=10, ge=1, le=100)  # le=100 forbidden
MAX_OFFSET = 10000
if offset > MAX_OFFSET:
    raise HTTPException(...)

# ✅ CORRECT - No upper limit
page_size: int = Query(default=10, ge=1)
# Let users access ALL their data via pagination
```

```typescript
// ❌ WRONG - Hardcoded limit
const response = await fetch(`/api/data?page_size=100`);
// User can't see item #101

// ✅ CORRECT - Server-side pagination
const response = await fetch(`/api/data?page=${page}&page_size=${pageSize}`);
```

### Pagination Metadata

All paginated endpoints return:

```json
{
  "data": [...],
  "pagination": {
    "total": 1234,
    "page": 1,
    "page_size": 25,
    "total_pages": 50
  }
}
```

---

## Security

### Dashboard Security

⚠️ **CRITICAL:** Dashboard is unauthenticated by design.

- Deploy only on trusted networks (VPN, internal network)
- Never expose to public internet without reverse proxy authentication

### Token Handling

- Store tokens in environment variables
- Never commit tokens to repository
- Use secrets management in production

---

## Internal API Philosophy

**CRITICAL: This is a self-contained service, NOT a public Python module.**

### Backward Compatibility Policy

**NO backward compatibility for internal APIs:**

- Internal methods can change freely
- Return types can change
- Method signatures can be modified
- No deprecation warnings needed

**Backward compatibility ONLY for:**

- Environment variable names (`METRICS_*`)
- REST API endpoints (`/api/metrics/*`)
- Webhook payload handling (GitHub webhook spec)

**Rationale:** Deployed as single container, all code updates together.

---

## Import Organization

**MANDATORY:** All imports at top of files.

- No imports in function bodies or try/except blocks
- Exception: `TYPE_CHECKING` imports can be conditional
- Pre-commit hooks enforce this
