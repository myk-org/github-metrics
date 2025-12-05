# Development Server Guide

Quick reference for running the GitHub Metrics application in development mode.

## Quick Start

```bash
# Start everything (backend + frontend + database)
./dev/run-all.sh
```

Access the application:
- **Frontend**: http://localhost:3003
- **Backend API**: http://localhost:8765
- **Dashboard**: http://localhost:8765/dashboard

## Development Modes

### Full Stack Development (Recommended)

Start both backend and frontend servers together with automatic database setup.

```bash
./dev/run-all.sh
```

**What it does:**
- Starts PostgreSQL container on port 15432
- Runs database migrations automatically
- Starts FastAPI backend with hot reload on port 8765
- Starts React frontend with Vite dev server on port 3003
- Gracefully shuts down all services on Ctrl+C

**When to use:**
- Starting fresh development session
- Working on full-stack features
- Need both frontend and backend running

### Backend Only

Start only the FastAPI backend server (includes database).

```bash
./dev/run-backend.sh
```

**What it does:**
- Starts PostgreSQL container on port 15432
- Runs database migrations via entrypoint.py
- Starts FastAPI server with hot reload on port 8765
- Preserves database data in Docker volume `github-metrics-dev-data`

**When to use:**
- Working on backend-only changes (API, database, business logic)
- Testing API endpoints directly
- Frontend is already running from another terminal

**Access:**
- Backend API: http://localhost:8765
- Dashboard: http://localhost:8765/dashboard

### Frontend Only

Start only the React frontend server.

```bash
./dev/run-frontend.sh
```

**What it does:**
- Starts Vite dev server on port 3003
- Proxies API requests to backend at localhost:8765
- Hot module replacement enabled

**When to use:**
- Working on UI/UX changes
- Backend is already running (from `run-backend.sh` or `run-all.sh`)
- Testing frontend components in isolation

**Access:**
- Frontend: http://localhost:3003

**Prerequisites:**
Backend must be running on port 8765 for API calls to work.

### Container Development

Run the entire application in Docker containers (production-like environment).

```bash
./dev/dev-container.sh
```

**What it does:**
- Builds application Docker image
- Starts PostgreSQL container
- Starts application container with both backend and frontend
- Uses Docker Compose watch mode for automatic rebuilds

**When to use:**
- Testing production-like deployment
- Debugging container-specific issues
- Verifying Dockerfile changes
- CI/CD pipeline testing

**Access:**
- Application: http://localhost:8765

**Note:** This mode uses the production build (no hot reload). Rebuild required for code changes.

## Database Management

### Importing Production Data

Export data from production/staging and import to local development database.

**Usage:**

```bash
./dev/export-db.sh <ssh_host> [container_name] [prod_db] [prod_user] [local_container]
```

**Example:**

```bash
# Export from production server
./dev/export-db.sh prod-server.example.com github-metrics-db github_metrics metrics github-metrics-dev-db
```

**What it does:**
1. Connects to production server via SSH
2. Auto-detects container runtime (Docker or Podman)
3. Exports data from production database (data only, no schema)
4. Imports data into local development database
5. Preserves local schema (uses migrations for schema)

**Prerequisites:**
- SSH access to production server
- Local dev database running (`./dev/run-backend.sh` or `./dev/run-all.sh`)
- Database migrations completed (automatic on server start)

**Default values:**
- Container name: `github-metrics-db`
- Production database: `github_metrics`
- Production user: `metrics`
- Local container: `github-metrics-dev-db`

**Output:**
Exported data is temporarily saved to `/tmp/prod_data.sql` and cleaned up after import.

### Database Persistence

Database data is persisted in a Docker volume between restarts.

**Volume name:** `github-metrics-dev-data`

**Useful commands:**

```bash
# View database data volume
docker volume inspect github-metrics-dev-data

# Remove database volume (reset database)
docker volume rm github-metrics-dev-data

# Connect to database directly
docker exec -it github-metrics-dev-db psql -U postgres -d github_metrics_dev
```

## Environment Variables

Development scripts use sensible defaults. Override via `.env` file in project root.

**Default values:**

```bash
METRICS_DB_NAME=github_metrics_dev
METRICS_DB_USER=postgres
METRICS_DB_PASSWORD=devpassword123
METRICS_DB_HOST=localhost
METRICS_DB_PORT=15432
METRICS_SERVER_HOST=0.0.0.0
METRICS_SERVER_PORT=8765
METRICS_SERVER_RELOAD=true
METRICS_SERVER_DEBUG=true
METRICS_VERIFY_GITHUB_IPS=false
METRICS_VERIFY_CLOUDFLARE_IPS=false
METRICS_SERVER_ALLOW_ALL_HOSTS=true
```

**Note:** Security checks are disabled in development for easier testing.

## Quick Reference

| Mode | Command | Backend | Frontend | Database | Hot Reload |
|------|---------|---------|----------|----------|------------|
| Full Stack | `./dev/run-all.sh` | :8765 | :3003 | :15432 | ✅ Both |
| Backend Only | `./dev/run-backend.sh` | :8765 | - | :15432 | ✅ Backend |
| Frontend Only | `./dev/run-frontend.sh` | - | :3003 | - | ✅ Frontend |
| Container | `./dev/dev-container.sh` | :8765 | :8765 | internal | ❌ Manual rebuild |

## Troubleshooting

### Port conflicts

If ports are already in use, stop existing services:

```bash
# Stop all dev services
docker stop github-metrics-dev-db github-metrics-app

# Or modify ports in .env file
export METRICS_SERVER_PORT=8766
export METRICS_DB_PORT=15433
```

### Database connection errors

Ensure PostgreSQL container is running:

```bash
docker ps | grep github-metrics-dev-db

# Check database is ready
docker exec github-metrics-dev-db pg_isready -U postgres -d github_metrics_dev
```

### Migration failures

Reset database and re-run migrations:

```bash
# Stop backend
# Remove database volume
docker volume rm github-metrics-dev-data

# Restart backend (migrations run automatically)
./dev/run-backend.sh
```

### Frontend build errors

Clear node_modules and reinstall:

```bash
cd frontend
rm -rf node_modules
bun install
```

## Development Workflow

**Recommended workflow:**

1. Start full stack: `./dev/run-all.sh`
2. Make code changes (hot reload applies automatically)
3. Test in browser at http://localhost:3003
4. Check backend logs in terminal
5. Stop with Ctrl+C (graceful shutdown)

**For backend-only work:**

1. Start backend: `./dev/run-backend.sh`
2. Test API at http://localhost:8765
3. Use curl or Postman for API testing

**For frontend-only work:**

1. Ensure backend is running: `./dev/run-backend.sh` (separate terminal)
2. Start frontend: `./dev/run-frontend.sh`
3. Test UI at http://localhost:3003
