# GitHub Metrics Test Suite

Comprehensive test suite for the github-metrics project.

## Overview

This test suite provides comprehensive coverage for all core components of the GitHub Metrics service including:

- Configuration loading and validation
- Database connection management
- Metrics tracking and storage
- Security utilities (signature verification, IP allowlisting)
- FastAPI endpoints and HTTP handlers

## Test Files

### `conftest.py`

Central fixtures file providing:
- Test environment variable setup
- Mock database manager
- Mock metrics tracker
- Sample webhook payloads (pull_request, issue_comment, push)
- Valid webhook signatures
- FastAPI test client

### `test_config.py` (19 tests)

Tests for configuration module:
- Database configuration URL construction
- Server configuration
- Security configuration (API keys, CORS)
- Webhook security configuration
- GitHub API configuration
- Environment variable parsing (required, optional, comma-separated lists)
- Singleton pattern for `get_config()`

### `test_database.py` (21 tests)

Tests for DatabaseManager class:
- Connection pool lifecycle (connect, disconnect)
- Query execution methods (`execute`, `fetch`, `fetchrow`, `fetchval`)
- Health checks
- Error handling
- Async context manager support
- Factory function `get_database_manager()`

### `test_metrics_tracker.py` (7 tests)

Tests for MetricsTracker class:
- Webhook event tracking with all fields
- Optional field handling
- Complex nested payload serialization
- JSON serialization with non-serializable types (datetime)
- Database error handling
- Default value handling

### `test_security.py` (17 tests)

Tests for security utilities:
- HMAC signature verification (valid, invalid, missing)
- IP allowlist verification (IPv4, IPv6, ranges, blocked IPs)
- GitHub IP allowlist fetching
- Cloudflare IP allowlist fetching
- Error handling for network failures

### `test_app.py` (20 tests)

Tests for FastAPI application endpoints:
- `/health` - Health check endpoint
- `/favicon.ico` - Favicon endpoint
- `/metrics` - Webhook receiver endpoint with signature verification
- `/dashboard` - Dashboard HTML page
- `/api/metrics/webhooks` - Webhook events listing with pagination
- `/api/metrics/webhooks/{delivery_id}` - Single webhook event details
- `/api/metrics/summary` - Overall metrics summary
- `/api/metrics/repositories` - Repository statistics
- Datetime string parsing utility

## Running Tests

### Install Dependencies

```bash
# Install test dependencies
uv sync --extra tests
```

### Run All Tests

```bash
# Run all tests with verbose output
uv run pytest tests/ -v

# Run all tests with coverage
uv run pytest tests/ --cov=github_metrics --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_config.py -v

# Run specific test class
uv run pytest tests/test_config.py::TestDatabaseConfig -v

# Run specific test
uv run pytest tests/test_config.py::TestDatabaseConfig::test_connection_url -v
```

### Run with Different Verbosity

```bash
# Short output
uv run pytest tests/

# Verbose output with test names
uv run pytest tests/ -v

# Very verbose with full test details
uv run pytest tests/ -vv

# Show local variables on failure
uv run pytest tests/ -l
```

### Run with Coverage

```bash
# Basic coverage report
uv run pytest tests/ --cov=github_metrics

# Coverage with missing lines
uv run pytest tests/ --cov=github_metrics --cov-report=term-missing

# Generate HTML coverage report
uv run pytest tests/ --cov=github_metrics --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Tests in Parallel

```bash
# Run tests in parallel (requires pytest-xdist)
uv run pytest tests/ -n auto
```

## Test Coverage Summary

Current test coverage: **61% overall**

| Module | Coverage |
|--------|----------|
| `config.py` | 100% |
| `metrics_tracker.py` | 100% |
| `models.py` | 93% |
| `utils/security.py` | 91% |
| `database.py` | 82% |
| `app.py` | 62% |
| `web/dashboard.py` | 100% |
| `webhook_setup.py` | 0% (needs tests) |

## Test Patterns

### Async Tests

All async tests use `pytest-asyncio` with auto mode:

```python
async def test_something(self, mock_db_manager: Mock) -> None:
    """Test async operation."""
    result = await some_async_function()
    assert result is not None
```

### Mocking Database Operations

```python
from unittest.mock import AsyncMock, Mock

# Mock database manager
mock_db = AsyncMock()
mock_db.fetch = AsyncMock(return_value=[{"id": 1}])
mock_db.execute = AsyncMock(return_value="INSERT 0 1")
```

### Testing FastAPI Endpoints

```python
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/health")
assert response.status_code == 200
```

### Testing with Environment Variables

```python
import os

# Set env vars in conftest.py set_test_env_vars fixture
os.environ["METRICS_DB_NAME"] = "test_db"
```

## Best Practices

1. **Use Fixtures**: Reuse common test setup via pytest fixtures in `conftest.py`
2. **Mock External Dependencies**: Always mock database, HTTP clients, and external APIs
3. **Test Edge Cases**: Test success, failure, empty data, and invalid input cases
4. **Use Descriptive Names**: Test names should describe what is being tested
5. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
6. **Async Tests**: Use `async def` for tests that call async functions
7. **Type Hints**: All test functions have complete type hints
8. **Docstrings**: All test methods have docstrings explaining what they test

## Adding New Tests

When adding new features:

1. Create test file: `tests/test_<module_name>.py`
2. Add fixtures to `conftest.py` if reusable
3. Follow existing test patterns
4. Aim for 100% coverage of new code
5. Test both happy path and error cases
6. Run tests before committing: `uv run pytest tests/ -v`

## Continuous Integration

Tests are designed to run without external dependencies (no real database required).
All external resources (database, HTTP clients) are mocked for fast, deterministic testing.

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError: No module named 'github_metrics'`:

```bash
# Install project in editable mode
uv sync --extra tests
```

### Async Warnings

If you get warnings about async fixtures:

```bash
# Already configured in pyproject.toml:
# asyncio_mode = "auto"
# asyncio_default_fixture_loop_scope = "function"
```

### Coverage Not Working

```bash
# Make sure pytest-cov is installed
uv sync --extra tests

# Run with coverage explicitly
uv run pytest tests/ --cov=github_metrics
```

## Future Improvements

Areas that need additional test coverage:

1. **Dashboard Controller** (`web/dashboard.py`) - Consider adding edge-case tests
   - Error handling for corrupted template files
   - Mutation testing to validate robustness

2. **Webhook Setup** (`webhook_setup.py`) - Currently 0% coverage
   - GitHub API integration
   - Webhook creation
   - Repository configuration

3. **FastAPI Lifespan** (`app.py`) - Needs integration tests
   - Startup/shutdown sequence
   - IP allowlist loading
   - Database initialization

4. **Error Handling** - More comprehensive error scenarios
   - Network failures
   - Database connection errors
   - Malformed payloads

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
