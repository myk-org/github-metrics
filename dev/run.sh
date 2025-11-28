#!/bin/bash
# Development server - handles everything automatically
# Usage: ./dev/run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load .env if exists, otherwise use defaults
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Dev defaults (use non-standard port to avoid conflicts)
export METRICS_DB_NAME="${METRICS_DB_NAME:-github_metrics_dev}"
export METRICS_DB_USER="${METRICS_DB_USER:-postgres}"
# Simple password for local dev only - override via .env for different environments
export METRICS_DB_PASSWORD="${METRICS_DB_PASSWORD:-devpassword123}"
export METRICS_DB_HOST="${METRICS_DB_HOST:-localhost}"
export METRICS_DB_PORT="${METRICS_DB_PORT:-15432}"
export METRICS_SERVER_HOST="${METRICS_SERVER_HOST:-0.0.0.0}"
export METRICS_SERVER_ALLOW_ALL_HOSTS="${METRICS_SERVER_ALLOW_ALL_HOSTS:-true}"
export METRICS_SERVER_PORT="${METRICS_SERVER_PORT:-8765}"
export METRICS_VERIFY_GITHUB_IPS="${METRICS_VERIFY_GITHUB_IPS:-false}"
export METRICS_VERIFY_CLOUDFLARE_IPS="${METRICS_VERIFY_CLOUDFLARE_IPS:-false}"
export METRICS_SERVER_RELOAD="${METRICS_SERVER_RELOAD:-true}"

CONTAINER_NAME="github-metrics-dev-db"
VOLUME_NAME="github-metrics-dev-data"

# Start PostgreSQL container if not running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting PostgreSQL container..."

    # Remove stopped container if exists
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    # Create volume for data persistence if it doesn't exist
    docker volume create "$VOLUME_NAME" 2>/dev/null || true

    docker run -d \
        --name "$CONTAINER_NAME" \
        -e POSTGRES_DB="$METRICS_DB_NAME" \
        -e POSTGRES_USER="$METRICS_DB_USER" \
        -e POSTGRES_PASSWORD="$METRICS_DB_PASSWORD" \
        -p "${METRICS_DB_PORT}:5432" \
        -v "${VOLUME_NAME}:/var/lib/postgresql/data" \
        postgres:16-alpine

    echo "Waiting for PostgreSQL to be ready..."
    sleep 3

    # Wait for PostgreSQL to accept connections
    until docker exec "$CONTAINER_NAME" pg_isready -U "$METRICS_DB_USER" -d "$METRICS_DB_NAME" >/dev/null 2>&1; do
        sleep 1
    done
    echo "PostgreSQL ready."
else
    echo "PostgreSQL container already running."
fi

# Cleanup on exit - stop container but preserve data in Docker volume
cleanup() {
    echo ""
    echo "Stopping PostgreSQL container..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "Data preserved in volume: $VOLUME_NAME"
}
trap cleanup EXIT

# Note: Migrations are run automatically by entrypoint.py
# No need to run them here to avoid duplicate execution

# Start server
echo "Starting development server on http://localhost:${METRICS_SERVER_PORT}"
uv run entrypoint.py
