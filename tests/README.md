# Tests

## Overview

This directory contains the test suite for github-metrics, including:
- **Unit tests** - API endpoints, database, configuration, security
- **UI tests** - Playwright-based browser tests for the dashboard

## Prerequisites

### One-time Setup for UI Tests

Install the Chromium browser for Playwright:

```bash
uv run playwright install chromium
```

## Running Tests

### Unit Tests (with uv)

```bash
# Run all unit tests (UI tests excluded by default)
uv run --group tests pytest tests/

# Run with coverage
uv run --group tests pytest tests/ --cov=github_metrics --cov-report=term-missing

# Run specific test file
uv run --group tests pytest tests/test_app.py -v

# Run tests in parallel
uv run --group tests pytest tests/ -n auto
```

### UI Tests (Playwright)

UI tests run against the real dev server, which starts automatically via the session-scoped `dev_server` fixture.

```bash
# Run UI tests
uv run --group tests pytest tests/ -m ui

# Run with visible browser
uv run --group tests pytest tests/ -m ui --headed

# Run with slow motion for debugging
uv run --group tests pytest tests/ -m ui --headed --slowmo 500

# Run all tests including UI
uv run --group tests pytest tests/ -m ''
```

### With tox

```bash
# Run default suite (unit tests + unused code check)
tox

# Run only unit tests
tox -e unittests

# Run UI tests
tox -e ui

# Run unused code check
tox -e unused-code
```

## Test Structure

| File | Description |
|------|-------------|
| `conftest.py` | Shared fixtures (mock config, db, dev_server) |
| `test_app.py` | FastAPI endpoint tests |
| `test_config.py` | Configuration loading tests |
| `test_database.py` | Database manager tests |
| `test_metrics_tracker.py` | Metrics tracker tests |
| `test_security.py` | Security utilities tests |
| `test_ui_dashboard.py` | Playwright UI tests |

## Test Markers

| Marker | Description |
|--------|-------------|
| `ui` | Playwright UI tests (excluded by default) |

## Coverage

Minimum **90% coverage** is required. Check with:

```bash
uv run --group tests pytest tests/ --cov=github_metrics --cov-report=term-missing
```
