#!/usr/bin/env bash
# Run the containerized app locally for testing
# Usage: ./dev/dev-container.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

docker compose -f docker-compose.yml up --build "$@"
