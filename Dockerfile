# GitHub Metrics Service Dockerfile
# Multi-stage build: Frontend (Bun) + Backend (Python)

# Build arguments for version pinning (must be in global scope before any FROM)
ARG UV_VERSION=0.5.14

# ============================================
# Stage 1: Frontend Build (Bun)
# ============================================
FROM docker.io/oven/bun:1 AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for layer caching
COPY frontend/package.json frontend/bun.lock ./

# Install dependencies with frozen lockfile
RUN bun install --frozen-lockfile

# Copy frontend source files
COPY frontend/ ./

# Build frontend (outputs to dist/)
RUN bun run build

# ============================================
# Stage 2: UV Binary
# ============================================
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ============================================
# Stage 3: Final Runtime (Python)
# ============================================
FROM docker.io/python:3.13-slim

ENV HOME_DIR="/app" \
    HOME="/app"
ENV PATH="$HOME_DIR/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON=python3.13 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_SYNC=1 \
    UV_CACHE_DIR="$HOME_DIR/.cache/uv"

WORKDIR $HOME_DIR

# Install system dependencies
# Note: Exact version pinning for Debian packages would require checking
# the python:3.13-slim repository at build time. For production builds,
# consider using apt-cache policy <package> to find available versions
# and pin to specific versions (e.g., curl=7.88.1-10+deb12u8)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Install uv with pinned version
COPY --from=uv /uv /uvx /usr/local/bin/

# Create non-root user EARLY (before copying files or installing dependencies)
# This eliminates the need for slow chown -R after uv sync
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/bash appuser && \
    chown appuser:appuser $HOME_DIR

# Copy project files WITH ownership already set (avoids chown -R overhead)
COPY --chown=appuser:appuser entrypoint.py pyproject.toml uv.lock alembic.ini README.md $HOME_DIR/
COPY --chown=appuser:appuser backend $HOME_DIR/backend/

# Copy built frontend from frontend-builder stage
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist $HOME_DIR/static

# Switch to non-root user BEFORE uv sync
# This ensures .venv is created with correct ownership from the start
USER appuser

# Create cache directory and install dependencies
# No chown needed - files already owned by appuser
RUN mkdir -p $UV_CACHE_DIR && uv sync --frozen

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://127.0.0.1:${METRICS_SERVER_PORT:-8765}/health || exit 1

ENTRYPOINT ["tini", "--", "uv", "run", "entrypoint.py"]
