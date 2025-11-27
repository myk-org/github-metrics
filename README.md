# GitHub Metrics

Standalone metrics service for GitHub webhook event tracking and visualization.

## Overview

GitHub Metrics is a FastAPI-based service that receives GitHub webhooks, stores event data in PostgreSQL, and provides a real-time dashboard for monitoring repository activity. The service tracks webhook events, pull request metrics, review workflows, CI/CD check runs, and GitHub API usage.

## Features

- **Webhook Processing**: Receives and validates GitHub webhook events with IP allowlist verification and signature validation
- **Real-time Dashboard**: Interactive web dashboard with live updates via WebSocket streaming
- **Event Storage**: Comprehensive event tracking in PostgreSQL with full payload storage
- **PR Analytics**: Track pull request lifecycle, reviews, labels, and code metrics
- **CI/CD Monitoring**: Monitor check runs, test results, and pipeline execution
- **API Usage Tracking**: Track GitHub API rate limit consumption and optimization
- **REST API**: Query metrics programmatically with filtering and pagination
- **Security**: IP allowlist verification (GitHub/Cloudflare), webhook signature validation (HMAC SHA256)
- **Automatic Webhook Setup**: Optionally auto-create webhooks on startup for configured repositories

## Quick Start

### Using Docker Compose

1. Copy the example configuration:

```bash
cp examples/docker-compose.yaml docker-compose.yaml
```

2. Create `.env` file with database password:

```bash
echo "POSTGRES_PASSWORD=your-secure-password-here" > .env
```

3. Start the service:

```bash
docker-compose up -d
```

4. Access the dashboard:

```
http://localhost:8080/dashboard
```

The service will automatically:
- Run database migrations
- Start the metrics server on port 8080

### Docker Compose Configuration

```yaml
services:
  # PostgreSQL database for metrics storage
  github-metrics-postgres:
    image: postgres:16-alpine
    container_name: github-metrics-postgres
    environment:
      - POSTGRES_DB=github_metrics
      - POSTGRES_USER=metrics
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}  # Set in .env file
    volumes:
      - "./postgres-data:/var/lib/postgresql/data"
    ports:
      # Bind to localhost only - prevents external network access
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U metrics -d github_metrics"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # GitHub Metrics service
  github-metrics:
    image: ghcr.io/myk-org/github-metrics:latest
    container_name: github-metrics
    environment:
      # Database configuration
      - METRICS_DB_HOST=github-metrics-postgres
      - METRICS_DB_PORT=5432
      - METRICS_DB_NAME=github_metrics
      - METRICS_DB_USER=metrics
      - METRICS_DB_PASSWORD=${POSTGRES_PASSWORD}
      - METRICS_DB_POOL_SIZE=20
      # Server configuration
      - METRICS_SERVER_HOST=0.0.0.0
      - METRICS_SERVER_PORT=8080
      - METRICS_SERVER_WORKERS=4
      # Webhook security (uncomment to enable)
      # - METRICS_WEBHOOK_SECRET=your-webhook-secret
      # - METRICS_VERIFY_GITHUB_IPS=true
      # - METRICS_VERIFY_CLOUDFLARE_IPS=true
      # Optional: Webhook setup on startup (uncomment to enable)
      # - METRICS_SETUP_WEBHOOK=true
      # - METRICS_GITHUB_TOKEN=ghp_xxx
      # - METRICS_WEBHOOK_URL=https://your-domain.com/metrics
      # - METRICS_REPOSITORIES=org/repo1,org/repo2
    ports:
      - "8080:8080"
    depends_on:
      github-metrics-postgres:
        condition: service_healthy
    restart: unless-stopped
```

## Configuration

All configuration is done via environment variables. No configuration files are required.

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `METRICS_DB_NAME` | PostgreSQL database name | `github_metrics` |
| `METRICS_DB_USER` | PostgreSQL username | `metrics` |
| `METRICS_DB_PASSWORD` | PostgreSQL password | `secure-password` |

### Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_DB_HOST` | Database host | `localhost` |
| `METRICS_DB_PORT` | Database port | `5432` |
| `METRICS_DB_POOL_SIZE` | Connection pool size | `20` |

### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_SERVER_HOST` | Server bind host | `0.0.0.0` |
| `METRICS_SERVER_PORT` | Server bind port | `8080` |
| `METRICS_SERVER_WORKERS` | Uvicorn workers | `4` |

### Security Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_API_KEYS` | Comma-separated API keys for authentication | Empty (no auth) |
| `METRICS_CORS_ORIGINS` | Comma-separated CORS origins | Empty |

### Webhook Security Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_WEBHOOK_SECRET` | Secret for validating webhook signatures (HMAC SHA256) | Empty (no validation) |
| `METRICS_VERIFY_GITHUB_IPS` | Verify requests from GitHub IP allowlist | `false` |
| `METRICS_VERIFY_CLOUDFLARE_IPS` | Verify requests from Cloudflare IP allowlist | `false` |

### Webhook Setup Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_SETUP_WEBHOOK` | Enable automatic webhook creation on startup | `false` |
| `METRICS_GITHUB_TOKEN` | GitHub token for API access (requires repo admin permissions) | Empty |
| `METRICS_WEBHOOK_URL` | URL where webhooks will be delivered | Empty |
| `METRICS_REPOSITORIES` | Comma-separated list of repositories (org/repo format) | Empty |

## API Endpoints

### Health Check

```
GET /health
```

Returns service health status and database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "database": true,
  "version": "0.1.0"
}
```

### Webhook Receiver

```
POST /metrics
```

Receives GitHub webhook events. Verifies IP allowlist (if configured) and signature, then stores event metrics.

**Headers:**
- `X-GitHub-Delivery`: Unique webhook delivery ID
- `X-GitHub-Event`: Event type (pull_request, issue_comment, etc.)
- `X-Hub-Signature-256`: HMAC SHA256 signature (if METRICS_WEBHOOK_SECRET is set)

**Response:**
```json
{
  "status": "ok",
  "delivery_id": "12345678-1234-1234-1234-123456789abc"
}
```

### Dashboard

```
GET /dashboard
```

Interactive web dashboard with real-time metrics visualization.

### WebSocket Streaming

```
WS /metrics/ws?repository=org/repo&event_type=pull_request&status=success
```

Real-time metrics streaming with optional filtering.

**Query Parameters:**
- `repository`: Filter by repository (org/repo format)
- `event_type`: Filter by event type
- `status`: Filter by status (success, error, partial)

### REST API Endpoints

#### Get Webhook Events

```
GET /api/metrics/webhooks
```

Retrieve webhook events with filtering and pagination.

**Query Parameters:**
- `repository`: Filter by repository (org/repo format)
- `event_type`: Filter by event type
- `status`: Filter by status (success, error, partial)
- `start_time`: Start time in ISO 8601 format (e.g., 2024-01-15T00:00:00Z)
- `end_time`: End time in ISO 8601 format
- `page`: Page number (1-indexed, default: 1)
- `page_size`: Items per page (1-1000, default: 100)

**Response:**
```json
{
  "data": [
    {
      "delivery_id": "12345678-1234-1234-1234-123456789abc",
      "repository": "org/repo",
      "event_type": "pull_request",
      "action": "opened",
      "pr_number": 123,
      "sender": "username",
      "status": "success",
      "created_at": "2024-01-15T10:30:00Z",
      "processed_at": "2024-01-15T10:30:01Z",
      "duration_ms": 1234,
      "api_calls_count": 5,
      "token_spend": 5,
      "token_remaining": 4995,
      "error_message": null
    }
  ],
  "pagination": {
    "total": 1000,
    "page": 1,
    "page_size": 100,
    "total_pages": 10,
    "has_next": true,
    "has_prev": false
  }
}
```

#### Get Webhook Event by ID

```
GET /api/metrics/webhooks/{delivery_id}
```

Get specific webhook event details including full payload.

**Response:**
```json
{
  "delivery_id": "12345678-1234-1234-1234-123456789abc",
  "repository": "org/repo",
  "event_type": "pull_request",
  "action": "opened",
  "pr_number": 123,
  "sender": "username",
  "status": "success",
  "created_at": "2024-01-15T10:30:00Z",
  "processed_at": "2024-01-15T10:30:01Z",
  "duration_ms": 1234,
  "api_calls_count": 5,
  "token_spend": 5,
  "token_remaining": 4995,
  "error_message": null,
  "payload": {
    "action": "opened",
    "pull_request": { ... },
    "repository": { ... },
    "sender": { ... }
  }
}
```

#### Get Repository Statistics

```
GET /api/metrics/repositories
```

Get aggregated statistics per repository.

**Query Parameters:**
- `start_time`: Start time in ISO 8601 format
- `end_time`: End time in ISO 8601 format
- `page`: Page number (1-indexed, default: 1)
- `page_size`: Items per page (1-100, default: 10)

**Response:**
```json
{
  "time_range": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-31T23:59:59Z"
  },
  "repositories": [
    {
      "repository": "org/repo",
      "total_events": 1000,
      "successful_events": 980,
      "failed_events": 20,
      "success_rate": 98.0,
      "avg_processing_time_ms": 1234,
      "total_api_calls": 5000,
      "total_token_spend": 5000
    }
  ],
  "pagination": {
    "total": 50,
    "page": 1,
    "page_size": 10,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

#### Get Metrics Summary

```
GET /api/metrics/summary
```

Get overall metrics summary across all repositories.

**Query Parameters:**
- `start_time`: Start time in ISO 8601 format
- `end_time`: End time in ISO 8601 format

**Response:**
```json
{
  "time_range": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-31T23:59:59Z"
  },
  "summary": {
    "total_events": 10000,
    "successful_events": 9800,
    "failed_events": 200,
    "success_rate": 98.0,
    "avg_processing_time_ms": 1234,
    "total_api_calls": 50000,
    "total_token_spend": 50000,
    "unique_repositories": 50,
    "unique_senders": 100
  }
}
```

## Webhook Setup

### Automatic Webhook Creation

The service can automatically create webhooks on startup by setting environment variables:

```bash
# Enable webhook setup
METRICS_SETUP_WEBHOOK=true

# GitHub token with repo admin permissions
METRICS_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# URL where webhooks will be delivered
METRICS_WEBHOOK_URL=https://your-domain.com/metrics

# Repositories to configure (comma-separated)
METRICS_REPOSITORIES=org/repo1,org/repo2,org/repo3

# Optional: Webhook secret for signature validation
METRICS_WEBHOOK_SECRET=your-webhook-secret
```

The service will:
1. Check if webhooks already exist for each repository
2. Create new webhooks if they don't exist
3. Configure webhooks to send all events (`["*"]`)
4. Log success/failure for each repository

### Manual Webhook Configuration

To manually configure webhooks in GitHub:

1. Go to repository Settings → Webhooks → Add webhook
2. Set **Payload URL**: `https://your-domain.com/metrics`
3. Set **Content type**: `application/json`
4. Set **Secret**: (same as `METRICS_WEBHOOK_SECRET` if configured)
5. Select **Which events**: "Send me everything" or specific events
6. Set **Active**: Checked
7. Click "Add webhook"

## Security

### IP Allowlist Verification

Enable IP verification to only accept webhooks from GitHub or Cloudflare:

```bash
# Verify requests from GitHub IPs
METRICS_VERIFY_GITHUB_IPS=true

# Verify requests from Cloudflare IPs (if using Cloudflare proxy)
METRICS_VERIFY_CLOUDFLARE_IPS=true
```

The service fetches IP ranges from:
- GitHub: `https://api.github.com/meta` (hooks field)
- Cloudflare: `https://www.cloudflare.com/ips-v4` and `ips-v6`

### Webhook Signature Validation

Enable signature validation to verify webhook authenticity:

```bash
# Set webhook secret (same secret configured in GitHub)
METRICS_WEBHOOK_SECRET=your-webhook-secret
```

The service validates webhook signatures using HMAC SHA256 (`X-Hub-Signature-256` header).

### Deployment Recommendations

- Deploy behind a reverse proxy (nginx, Caddy) with HTTPS
- Use firewall rules to restrict access to webhook endpoint
- Store secrets in environment variables or secret management systems
- Enable both IP verification and signature validation for maximum security
- Never expose PostgreSQL port to public internet (bind to 127.0.0.1 only)
- Use strong database passwords (generated, not dictionary words)

## Development

### Requirements

- Python 3.13
- PostgreSQL 16+
- uv (Python package manager)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/your-org/github-metrics.git
cd github-metrics
```

2. Install dependencies:

```bash
uv sync
```

3. Set environment variables:

```bash
export METRICS_DB_NAME=github_metrics
export METRICS_DB_USER=metrics
export METRICS_DB_PASSWORD=dev-password
export METRICS_DB_HOST=localhost
export METRICS_DB_PORT=5432
```

4. Run database migrations:

```bash
uv run alembic upgrade head
```

5. Start the development server:

```bash
uv run entrypoint.py
```

The service will start on `http://localhost:8080`.

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code
uv run ruff check

# Fix linting issues
uv run ruff check --fix

# Type checking
uv run mypy github_metrics/

# Run all checks
uv run ruff check && uv run ruff format && uv run mypy github_metrics/
```

### Testing

```bash
# Run tests
uv run --group tests pytest

# Run with coverage
uv run --group tests pytest --cov=github_metrics

# Run specific test file
uv run --group tests pytest tests/test_app.py -v
```

### Database Migrations

Migrations are automatically applied on container startup. For manual operations:

#### Using Docker (Production/Container)

```bash
# Apply migrations (automatic on container start, or manual)
docker exec -it github-metrics alembic upgrade head

# Rollback last migration
docker exec -it github-metrics alembic downgrade -1

# Show migration history
docker exec -it github-metrics alembic history

# Mark existing database as migrated (one-time for existing DBs)
docker exec -it github-metrics alembic stamp head
```

#### Local Development

```bash
# Create new migration
uv run alembic revision --autogenerate -m "Description of changes"

# Apply migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1

# Show migration history
uv run alembic history
```

## Database Schema

The service stores data in the following tables:

- **webhooks**: Webhook event store with full payload and processing metrics
- **pull_requests**: PR master records with size metrics and state tracking
- **pr_events**: PR timeline events for analytics
- **pr_reviews**: Review data for approval tracking
- **pr_labels**: Label history for workflow tracking
- **check_runs**: Check run results for CI/CD metrics
- **api_usage**: GitHub API usage tracking for rate limit monitoring

All tables use PostgreSQL-specific types (UUID, JSONB) for optimal performance and include comprehensive indexes for fast queries.

## License

Apache-2.0

## Author

myakove
