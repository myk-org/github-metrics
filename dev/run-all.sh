#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$0")"

echo "Starting both frontend and backend servers..."

# Start backend in a new process group
setsid "$SCRIPT_DIR/run-backend.sh" &
BACKEND_PID=$!

# Give backend a moment to start
sleep 2

# Start frontend in a new process group
setsid "$SCRIPT_DIR/run-frontend.sh" &
FRONTEND_PID=$!

# Trap to gracefully shutdown both
cleanup() {
    echo ""
    echo "Shutting down servers gracefully..."

    # Send SIGINT to process groups (negative PID = process group)
    kill -INT -$BACKEND_PID 2>/dev/null || true
    kill -INT -$FRONTEND_PID 2>/dev/null || true

    # Wait for graceful shutdown (up to 10 seconds)
    for _ in {1..10}; do
        if ! kill -0 $BACKEND_PID 2>/dev/null && ! kill -0 $FRONTEND_PID 2>/dev/null; then
            echo "All servers stopped."
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    echo "Force stopping remaining processes..."
    kill -9 -$BACKEND_PID 2>/dev/null || true
    kill -9 -$FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Backend: http://localhost:8765"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop both servers"

# Wait for both
wait
