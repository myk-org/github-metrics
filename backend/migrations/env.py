"""
Alembic migration environment for GitHub Metrics database.

This module configures Alembic to:
- Use async PostgreSQL via asyncpg
- Load database configuration from environment variables
- Support both online (with database connection) and offline (SQL script) migrations

Key integration points:
- Database config loaded from METRICS_DB_* environment variables
- Async migration support for PostgreSQL
"""

import asyncio
from logging.config import fileConfig
from urllib.parse import quote

from alembic import context
from simple_logger.logger import get_logger
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.config import get_config
from backend.models import Base

# Alembic Config object provides access to alembic.ini values
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get simple logger for Alembic
logger = get_logger(name="alembic.migrations", level="INFO")


def _configure_from_env() -> None:
    """
    Load database configuration from environment variables and set Alembic options.

    Uses METRICS_DB_* environment variables:
    - METRICS_DB_HOST (default: localhost)
    - METRICS_DB_PORT (default: 5432)
    - METRICS_DB_NAME (required)
    - METRICS_DB_USER (required)
    - METRICS_DB_PASSWORD (required)
    """
    metrics_config = get_config()
    db = metrics_config.database

    # Construct PostgreSQL asyncpg URL with URL-encoded credentials
    encoded_user = quote(db.user, safe="")
    encoded_password = quote(db.password, safe="")
    encoded_name = quote(db.name, safe="")

    db_url = f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{db.host}:{db.port}/{encoded_name}"

    # Set database URL in Alembic config
    config.set_main_option("sqlalchemy.url", db_url)

    logger.info(f"Loaded database configuration: {db.user}@{db.host}:{db.port}/{db.name}")


# Load database configuration
try:
    _configure_from_env()
except KeyError:
    logger.exception("Missing required environment variable")
    raise
except Exception:
    logger.exception("Failed to load database configuration")
    raise

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without database connectivity.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    logger.info("Running migrations in offline mode (SQL script generation)")

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with given database connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    logger.info("Running migrations in online mode (async PostgreSQL)")

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with database connection."""
    asyncio.run(run_async_migrations())


# Determine migration mode and execute
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
