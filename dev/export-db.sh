#!/bin/bash
# Export data from production container and import to local dev database
# Usage: ./dev/export-db.sh <ssh_host> [container_name] [prod_db] [prod_user]
#
# Example:
#   ./dev/export-db.sh prod-server.example.com github-metrics-db github_metrics metrics

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

SSH_HOST="${1:?Usage: $0 <ssh_host> [container_name] [prod_db] [prod_user]}"
CONTAINER_NAME="${2:-github-metrics-db}"
PROD_DB="${3:-github_metrics}"
PROD_USER="${4:-metrics}"

# Load local .env or use defaults
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

LOCAL_HOST="${METRICS_DB_HOST:-localhost}"
LOCAL_PORT="${METRICS_DB_PORT:-15432}"
LOCAL_DB="${METRICS_DB_NAME:-github_metrics_dev}"
LOCAL_USER="${METRICS_DB_USER:-postgres}"
LOCAL_PASSWORD="${METRICS_DB_PASSWORD:-dev}"

# Detect container runtime by checking which one has the container
echo "Connecting to $SSH_HOST to find container..."

# Check docker first (more common), then podman
if ssh "$SSH_HOST" "docker ps --format '{{.Names}}' 2>/dev/null" | grep -q "^${CONTAINER_NAME}\$"; then
    CONTAINER_RUNTIME="docker"
elif ssh "$SSH_HOST" "podman ps --format '{{.Names}}' 2>/dev/null" | grep -q "^${CONTAINER_NAME}\$"; then
    CONTAINER_RUNTIME="podman"
else
    echo "Error: Container '$CONTAINER_NAME' not found on $SSH_HOST"
    echo ""
    echo "Available docker containers:"
    ssh "$SSH_HOST" "docker ps --format '{{.Names}}' 2>/dev/null" || echo "  (none or docker not available)"
    echo ""
    echo "Available podman containers:"
    ssh "$SSH_HOST" "podman ps --format '{{.Names}}' 2>/dev/null" || echo "  (none or podman not available)"
    exit 1
fi

echo "Found container in $CONTAINER_RUNTIME"

echo ""
echo "Exporting from production:"
echo "  SSH Host: $SSH_HOST"
echo "  Container: $CONTAINER_NAME"
echo "  Database: $PROD_DB"
echo "  User: $PROD_USER"
echo ""
echo "Importing to local:"
echo "  Host: $LOCAL_HOST:$LOCAL_PORT"
echo "  Database: $LOCAL_DB"
echo "  User: $LOCAL_USER"
echo ""

# Export from prod container via SSH (data only, no schema - we use migrations)
echo "Exporting data from production container..."
# Use --inserts to generate plain INSERT statements instead of COPY commands
# COPY uses backslash commands that are restricted in some psql environments
# Note: Variables are properly quoted to prevent shell injection
ssh "$SSH_HOST" "${CONTAINER_RUNTIME} exec '${CONTAINER_NAME}' pg_dump -U '${PROD_USER}' -d '${PROD_DB}' --data-only --no-owner --no-privileges --inserts" > /tmp/prod_data.sql

# Check if export was successful
if [ ! -s /tmp/prod_data.sql ]; then
    echo "Error: Export failed or database is empty"
    rm -f /tmp/prod_data.sql
    exit 1
fi

echo "Exported $(wc -l < /tmp/prod_data.sql) lines"

# Import to local using the dev container's psql
echo "Importing to local database..."
LOCAL_CONTAINER="github-metrics-dev-db"

# Check if local dev container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${LOCAL_CONTAINER}$"; then
    echo "Error: Local dev container '$LOCAL_CONTAINER' is not running."
    echo "Start it first with: ./dev/run.sh"
    rm -f /tmp/prod_data.sql
    exit 1
fi

# Check if tables exist (migrations must have run)
if ! docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -c "SELECT 1 FROM webhooks LIMIT 1" >/dev/null 2>&1; then
    echo "Error: Database tables don't exist. Migrations haven't run."
    echo "Make sure ./dev/run.sh completed successfully (wait for 'Starting development server' message)"
    rm -f /tmp/prod_data.sql
    exit 1
fi

# Copy SQL file into container and import
docker cp /tmp/prod_data.sql "$LOCAL_CONTAINER":/tmp/prod_data.sql
docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -f /tmp/prod_data.sql
docker exec "$LOCAL_CONTAINER" rm /tmp/prod_data.sql

rm /tmp/prod_data.sql

echo ""
echo "Done! Local database populated with production data."
