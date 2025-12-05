#!/bin/bash
set -e
cd "$(dirname "$0")/../frontend"
echo "Starting React frontend on http://localhost:3003..."
bun run dev --port 3003
