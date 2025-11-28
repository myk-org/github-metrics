# Development Setup

## Quick Start

```bash
# Just run (handles everything automatically)
./dev/run.sh
```

This will:
1. Start a PostgreSQL container (port 15432)
2. Run database migrations
3. Start the development server at http://localhost:8765

Press `Ctrl+C` to stop - the database container will be stopped automatically.

## Importing Production Data

If you want to work with real data from production:

```bash
# First, start the dev environment (creates empty DB with migrations)
./dev/run.sh &

# Export from production container via SSH and import to local
./dev/export-db.sh <ssh_host> [container_name] [prod_db] [prod_user]

# Example:
./dev/export-db.sh prod-server.example.com github-metrics-db github_metrics metrics
```

The script will:
1. SSH into the remote server
2. Auto-detect container runtime (docker or podman)
3. Run `pg_dump` inside the container
4. Import the data into your local dev database

## Environment Variables

All variables have sensible defaults for development. Override by creating `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_DB_NAME` | `github_metrics_dev` | Database name |
| `METRICS_DB_USER` | `postgres` | Database user |
| `METRICS_DB_PASSWORD` | `dev` | Database password |
| `METRICS_DB_HOST` | `localhost` | Database host |
| `METRICS_DB_PORT` | `15432` | Database port (non-default to avoid conflicts) |
| `METRICS_SERVER_HOST` | `0.0.0.0` | Server bind host |
| `METRICS_SERVER_PORT` | `8765` | Server port (non-default to avoid conflicts) |
| `METRICS_VERIFY_GITHUB_IPS` | `false` | Skip GitHub IP verification in dev |
| `METRICS_VERIFY_CLOUDFLARE_IPS` | `false` | Skip Cloudflare IP verification in dev |

## Accessing the Dashboard

Once running, open http://localhost:8765/dashboard in your browser.

## API Endpoints

- `GET /api/metrics/summary` - Overall metrics summary
- `GET /api/metrics/webhooks` - Recent webhook events
- `GET /api/metrics/repositories` - Repository statistics
- `GET /api/metrics/contributors` - PR contributors
- `GET /api/metrics/user-prs` - User pull requests
- `GET /api/metrics/pr-story/{repo}/{pr}` - PR timeline/story

## Troubleshooting

### Port 15432 already in use

```bash
# Stop any existing dev container
docker stop github-metrics-dev-db
docker rm github-metrics-dev-db
```

### Database connection issues

```bash
# Check if container is running
docker ps | grep github-metrics-dev-db

# Check container logs
docker logs github-metrics-dev-db
```
