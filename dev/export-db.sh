#!/bin/bash
# Export data from production container and import to local dev database
# Usage: ./dev/export-db.sh <ssh_host> [container_name] [prod_db] [prod_user] [prod_password] [local_container] [remote_runtime] [use_sudo]
#
# Parameters:
#   ssh_host        - Required. SSH host to connect to
#   container_name  - Container name on remote host (default: github-metrics-db)
#   prod_db         - Production database name (default: github_metrics)
#   prod_user       - Production database user (default: metrics)
#   prod_password   - Production database password (default: empty, uses peer/trust auth)
#   local_container - Local dev container name (default: github-metrics-dev-db)
#   remote_runtime  - Remote container runtime: docker or podman (default: docker)
#   use_sudo        - Use sudo for remote runtime: true or false (default: false)
#
# Example:
#   ./dev/export-db.sh prod-server.example.com
#   ./dev/export-db.sh prod-server.example.com github-metrics-db github_metrics metrics "" github-metrics-dev-db podman true
#   ./dev/export-db.sh prod-server.example.com github-metrics-db github_metrics metrics mypassword

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Cleanup function for remote temp file
cleanup_remote() {
    if [[ -n "${REMOTE_TMP_FILE:-}" && -n "${SSH_HOST:-}" ]]; then
        ssh -T "$SSH_HOST" "rm -f $REMOTE_TMP_FILE" 2>/dev/null || true
    fi
}
trap cleanup_remote EXIT

SSH_HOST="${1:?Usage: $0 <ssh_host> [container_name] [prod_db] [prod_user] [prod_password] [local_container] [remote_runtime] [use_sudo]}"
CONTAINER_NAME="${2:-github-metrics-db}"
PROD_DB="${3:-github_metrics}"
PROD_USER="${4:-metrics}"
PROD_PASSWORD="${5:-}"
LOCAL_CONTAINER="${6:-github-metrics-dev-db}"
REMOTE_RUNTIME="${7:-docker}"
USE_SUDO="${8:-false}"

# Validate remote runtime
if [[ "$REMOTE_RUNTIME" != "docker" && "$REMOTE_RUNTIME" != "podman" ]]; then
    echo "Error: remote_runtime must be 'docker' or 'podman', got '$REMOTE_RUNTIME'"
    exit 1
fi

# Build remote command prefix
if [[ "$USE_SUDO" == "true" ]]; then
    REMOTE_CMD="sudo $REMOTE_RUNTIME"
else
    REMOTE_CMD="$REMOTE_RUNTIME"
fi

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

# Detect local container runtime (docker preferred, fallback to podman)
if command -v docker &>/dev/null; then
    LOCAL_RUNTIME="docker"
elif command -v podman &>/dev/null; then
    LOCAL_RUNTIME="podman"
else
    echo "Error: Neither docker nor podman is installed locally"
    exit 1
fi

echo ""
echo "Exporting from production:"
echo "  SSH Host: $SSH_HOST"
echo "  Runtime: $REMOTE_RUNTIME (sudo: $USE_SUDO)"
echo "  Container: $CONTAINER_NAME"
echo "  Database: $PROD_DB"
echo "  User: $PROD_USER"
if [[ -n "$PROD_PASSWORD" ]]; then
    echo "  Password: [REDACTED]"
else
    echo "  Auth: peer/trust"
fi
echo ""
echo "Importing to local:"
echo "  Runtime: $LOCAL_RUNTIME"
echo "  Host: $LOCAL_HOST:$LOCAL_PORT"
echo "  Database: $LOCAL_DB"
echo "  User: $LOCAL_USER"
echo ""

# ============================================
# Pre-flight checks
# ============================================
echo "Checking local prerequisites..."

# Check if local dev container is running
if ! "$LOCAL_RUNTIME" ps --format '{{.Names}}' | grep -q "^${LOCAL_CONTAINER}$"; then
    echo "Error: Local dev container '$LOCAL_CONTAINER' is not running."
    echo "Start it first with: ./dev/run-backend.sh or ./dev/run-all.sh"
    exit 1
fi

# Check if tables exist (migrations must have run)
if ! "$LOCAL_RUNTIME" exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -c "SELECT 1 FROM webhooks LIMIT 1" >/dev/null 2>&1; then
    echo "Error: Database tables don't exist. Migrations haven't run."
    echo "Make sure ./dev/run-backend.sh or ./dev/run-all.sh completed successfully"
    exit 1
fi

echo "Local prerequisites OK"
echo ""

# ============================================
# Remote export
# ============================================
# Export from prod container via SSH (data only, no schema - we use migrations)
echo "Exporting data from production container..."
# Use --inserts to generate plain INSERT statements instead of COPY commands
# COPY uses backslash commands that are restricted in some psql environments

# Build pg_dump arguments
PG_DUMP_ARGS="--data-only --no-owner --no-privileges --inserts --exclude-table=alembic_version"
REMOTE_TMP_FILE="/tmp/prod_data_export_$$.sql"

# Step 1: Run pg_dump on remote and save to temp file there
REMOTE_EXPORT_CMD="$REMOTE_CMD exec '$CONTAINER_NAME' pg_dump -U '$PROD_USER' -d '$PROD_DB' $PG_DUMP_ARGS > $REMOTE_TMP_FILE"

if [[ -n "$PROD_PASSWORD" ]]; then
    # Pass password via environment to avoid process list exposure
    ssh -T "$SSH_HOST" "PGPASSWORD='$PROD_PASSWORD' $REMOTE_EXPORT_CMD"
else
    ssh -T "$SSH_HOST" "$REMOTE_EXPORT_CMD"
fi

# Step 2: Copy the dump file from remote to local
echo "Copying dump file from remote..."
if ! rsync --compress --partial --progress -e "ssh -T" "$SSH_HOST:$REMOTE_TMP_FILE" /tmp/prod_data.sql; then
    echo "Error: rsync transfer failed"
    exit 1
fi

# Check if export was successful
if [ ! -s /tmp/prod_data.sql ]; then
    echo "Error: Export failed or database is empty"
    rm -f /tmp/prod_data.sql
    exit 1
fi

echo "Exported $(wc -l < /tmp/prod_data.sql) lines"
echo ""

# ============================================
# Local import
# ============================================
# Import with optimizations for large files
FILE_SIZE=$(du -h /tmp/prod_data.sql | cut -f1)

# Truncate all tables before import (preserve schema, clear data)
echo "Clearing existing data from local database..."
"$LOCAL_RUNTIME" exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -c "TRUNCATE TABLE webhooks, pull_requests, pr_events, pr_reviews, pr_labels, check_runs, api_usage CASCADE;"

echo "Importing $FILE_SIZE of data (this may take a while for large databases)..."
"$LOCAL_RUNTIME" cp /tmp/prod_data.sql "$LOCAL_CONTAINER":/tmp/prod_data.sql

# Run import with performance optimizations
# Single transaction mode (-1) is faster than individual commits
# ON_ERROR_STOP=1 exits on first error instead of cascading failures
"$LOCAL_RUNTIME" exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -1 --set ON_ERROR_STOP=1 -f /tmp/prod_data.sql

"$LOCAL_RUNTIME" exec "$LOCAL_CONTAINER" rm /tmp/prod_data.sql
rm /tmp/prod_data.sql

echo ""
echo "Done! Local database populated with production data."
