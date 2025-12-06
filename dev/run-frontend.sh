#!/bin/bash
set -e

# Check for bun binary
if ! command -v bun &>/dev/null; then
    echo "Error: bun is not installed or not in PATH"
    echo "Install bun from: https://bun.sh"
    exit 1
fi

cd "$(dirname "$0")/../frontend"
echo "Starting React frontend on http://localhost:3003..."
bun run dev --port 3003
