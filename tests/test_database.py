"""Tests for DatabaseManager class.

Tests database connection management including:
- Connection pool lifecycle
- Query execution methods
- Health checks
- Error handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import asyncpg
import pytest

from github_metrics.database import DatabaseManager, get_database_manager


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    async def test_connect_creates_pool(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test connect creates connection pool."""
        mock_pool = AsyncMock(spec=asyncpg.Pool)

        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            await db_manager.connect()

            assert db_manager.pool is mock_pool
            mock_logger.info.assert_called()

    async def test_connect_with_existing_pool_raises_error(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test connect raises error if pool already exists."""
        db_manager.pool = AsyncMock(spec=asyncpg.Pool)

        with pytest.raises(ValueError, match="already exists"):
            await db_manager.connect()

    async def test_disconnect_closes_pool(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test disconnect closes connection pool."""
        mock_pool = AsyncMock(spec=asyncpg.Pool)
        db_manager.pool = mock_pool

        await db_manager.disconnect()

        mock_pool.close.assert_called_once()
        assert db_manager.pool is None
        mock_logger.info.assert_called()

    async def test_disconnect_without_pool_is_safe(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test disconnect is safe when pool doesn't exist."""
        db_manager.pool = None

        # Should not raise exception
        await db_manager.disconnect()

    async def test_execute_runs_query(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test execute method runs query successfully."""
        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock(return_value="INSERT 0 1")

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.execute("INSERT INTO test VALUES ($1)", "value")

        assert result == "INSERT 0 1"
        mock_connection.execute.assert_called_once_with("INSERT INTO test VALUES ($1)", "value")

    async def test_execute_without_pool_raises_error(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test execute raises error when pool not initialized."""
        db_manager.pool = None

        with pytest.raises(ValueError, match="not initialized"):
            await db_manager.execute("SELECT 1")

    async def test_fetch_returns_results(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetch method returns query results."""
        mock_records = [{"id": 1, "name": "test"}]
        mock_connection = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=mock_records)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        results = await db_manager.fetch("SELECT * FROM test WHERE id = $1", 1)

        assert results == mock_records
        mock_connection.fetch.assert_called_once_with("SELECT * FROM test WHERE id = $1", 1)

    async def test_fetch_without_pool_raises_error(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetch raises error when pool not initialized."""
        db_manager.pool = None

        with pytest.raises(ValueError, match="not initialized"):
            await db_manager.fetch("SELECT * FROM test")

    async def test_fetchrow_returns_single_row(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetchrow method returns single row."""
        mock_record = {"id": 1, "name": "test"}
        mock_connection = AsyncMock()
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 1)

        assert result == mock_record
        mock_connection.fetchrow.assert_called_once_with("SELECT * FROM test WHERE id = $1", 1)

    async def test_fetchrow_returns_none_when_no_results(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetchrow returns None when no results found."""
        mock_connection = AsyncMock()
        mock_connection.fetchrow = AsyncMock(return_value=None)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 999)

        assert result is None

    async def test_fetchval_returns_scalar_value(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetchval method returns scalar value."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value=42)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchval("SELECT COUNT(*) FROM test")

        assert result == 42
        mock_connection.fetchval.assert_called_once_with("SELECT COUNT(*) FROM test")

    async def test_health_check_returns_true_when_healthy(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test health check returns True when database is healthy."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value=1)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.health_check()

        assert result is True
        mock_connection.fetchval.assert_called_once_with("SELECT 1")

    async def test_health_check_returns_false_when_pool_not_initialized(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test health check returns False when pool not initialized."""
        db_manager.pool = None

        result = await db_manager.health_check()

        assert result is False
        mock_logger.warning.assert_called()

    async def test_health_check_returns_false_on_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test health check returns False on database exception."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(side_effect=Exception("Connection failed"))

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.health_check()

        assert result is False
        mock_logger.exception.assert_called()

    async def test_context_manager_connect_and_disconnect(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test DatabaseManager works as async context manager."""
        mock_pool = AsyncMock(spec=asyncpg.Pool)

        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            async with db_manager as manager:
                assert manager is db_manager
                assert manager.pool is mock_pool

            # Pool should be closed after exiting context
            mock_pool.close.assert_called_once()


class TestGetDatabaseManager:
    """Tests for get_database_manager factory function."""

    def test_get_database_manager_returns_instance(self) -> None:
        """Test factory function returns DatabaseManager instance."""
        db_manager = get_database_manager()

        assert isinstance(db_manager, DatabaseManager)
        assert db_manager.config is not None
        assert db_manager.logger is not None

    def test_get_database_manager_with_config(self) -> None:
        """Test factory function uses configuration from environment variables."""
        # Environment variables are already set by set_test_env_vars fixture in conftest.py
        # which sets METRICS_DB_NAME=test_metrics and METRICS_DB_USER=test_user
        db_manager = get_database_manager()

        # Verify the config was loaded from the environment variables
        assert db_manager.config.database.name == "test_metrics"
        assert db_manager.config.database.user == "test_user"


class TestDatabaseManagerErrorHandling:
    """Additional tests for DatabaseManager error handling and edge cases."""

    async def test_connect_connection_failure_logs_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test connect logs exception on connection failure."""
        with patch("asyncpg.create_pool", side_effect=asyncpg.PostgresError("Connection failed")):
            with pytest.raises(asyncpg.PostgresError):
                await db_manager.connect()

            mock_logger.exception.assert_called_once()
            assert "Failed to connect" in mock_logger.exception.call_args[0][0]

    async def test_disconnect_error_handling(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test disconnect handles errors and still sets pool to None."""
        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.close.side_effect = Exception("Close error")
        db_manager.pool = mock_pool

        await db_manager.disconnect()

        mock_logger.exception.assert_called_once()
        assert "Error closing" in mock_logger.exception.call_args[0][0]
        assert db_manager.pool is None

    async def test_execute_query_failure_logs_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test execute logs exception on query failure."""
        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock(side_effect=asyncpg.PostgresError("Query error"))

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        with pytest.raises(asyncpg.PostgresError):
            await db_manager.execute("INSERT INTO test VALUES ($1)", "value")

        mock_logger.exception.assert_called_once()
        assert "Failed to execute" in mock_logger.exception.call_args[0][0]

    async def test_fetch_query_failure_logs_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetch logs exception on query failure."""
        mock_connection = AsyncMock()
        mock_connection.fetch = AsyncMock(side_effect=asyncpg.PostgresError("Fetch error"))

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        with pytest.raises(asyncpg.PostgresError):
            await db_manager.fetch("SELECT * FROM test")

        mock_logger.exception.assert_called_once()
        assert "Failed to fetch" in mock_logger.exception.call_args[0][0]

    async def test_fetchrow_query_failure_logs_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetchrow logs exception on query failure."""
        mock_connection = AsyncMock()
        mock_connection.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("Fetchrow error"))

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        with pytest.raises(asyncpg.PostgresError):
            await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 1)

        mock_logger.exception.assert_called_once()
        assert "Failed to fetch single row" in mock_logger.exception.call_args[0][0]

    async def test_fetchval_without_pool_raises_error(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test fetchval raises error when pool not initialized."""
        db_manager.pool = None

        with pytest.raises(ValueError, match="not initialized"):
            await db_manager.fetchval("SELECT COUNT(*) FROM test")

    async def test_fetchval_query_failure_logs_exception(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetchval logs exception on query failure."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("Fetchval error"))

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        with pytest.raises(asyncpg.PostgresError):
            await db_manager.fetchval("SELECT COUNT(*) FROM test")

        mock_logger.exception.assert_called_once()
        assert "Failed to fetch scalar value" in mock_logger.exception.call_args[0][0]

    async def test_context_manager_disconnect_on_exception(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test context manager disconnects pool on exception."""
        mock_pool = AsyncMock(spec=asyncpg.Pool)

        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            with pytest.raises(Exception, match="Test error"):
                async with db_manager:
                    raise Exception("Test error")

        # Pool should still be closed after exception
        mock_pool.close.assert_called_once()

    async def test_fetchrow_logs_no_rows_debug(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetchrow logs debug message when no rows returned."""
        mock_connection = AsyncMock()
        mock_connection.fetchrow = AsyncMock(return_value=None)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 999)

        assert result is None
        # Verify debug log for no rows
        debug_calls = list(mock_logger.debug.call_args_list)
        assert any("no rows" in str(call).lower() for call in debug_calls)

    async def test_fetchrow_logs_one_row_debug(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetchrow logs debug message when one row returned."""
        mock_record = {"id": 1, "name": "test"}
        mock_connection = AsyncMock()
        mock_connection.fetchrow = AsyncMock(return_value=mock_record)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchrow("SELECT * FROM test WHERE id = $1", 1)

        assert result == mock_record
        # Verify debug log for one row
        debug_calls = list(mock_logger.debug.call_args_list)
        assert any("1 row" in str(call).lower() for call in debug_calls)

    async def test_execute_logs_debug_message(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test execute logs debug message on success."""
        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock(return_value="INSERT 0 1")

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.execute("INSERT INTO test VALUES ($1)", "value")

        assert result == "INSERT 0 1"
        mock_logger.debug.assert_called()
        assert "successfully" in mock_logger.debug.call_args[0][0].lower()

    async def test_fetch_logs_debug_message(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetch logs debug message with row count."""
        mock_records = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_connection = AsyncMock()
        mock_connection.fetch = AsyncMock(return_value=mock_records)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        results = await db_manager.fetch("SELECT * FROM test")

        assert len(results) == 3
        mock_logger.debug.assert_called()
        assert "3 rows" in mock_logger.debug.call_args[0][0]

    async def test_fetchval_logs_debug_message(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test fetchval logs debug message with value."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value=42)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.fetchval("SELECT COUNT(*) FROM test")

        assert result == 42
        mock_logger.debug.assert_called()
        assert "42" in str(mock_logger.debug.call_args[0][0])

    async def test_health_check_logs_debug_on_success(
        self,
        db_manager: DatabaseManager,
        mock_logger: Mock,
    ) -> None:
        """Test health check logs debug message on success."""
        mock_connection = AsyncMock()
        mock_connection.fetchval = AsyncMock(return_value=1)

        mock_pool = AsyncMock(spec=asyncpg.Pool)
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        db_manager.pool = mock_pool

        result = await db_manager.health_check()

        assert result is True
        mock_logger.debug.assert_called()
        assert "OK" in mock_logger.debug.call_args[0][0]
