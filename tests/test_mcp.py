"""Tests for MCP server integration.

Tests MCP server mounting and configuration including:
- MCP configuration via environment variable
- MCP server enabled/disabled behavior
"""

import os
from collections.abc import Generator

import pytest

from backend.app import app
from backend.config import _reset_config_for_testing, get_config


@pytest.fixture
def mcp_disabled_env() -> Generator[None]:
    """Fixture to temporarily disable MCP via environment."""
    original_value = os.environ.get("METRICS_MCP_ENABLED")
    os.environ["METRICS_MCP_ENABLED"] = "false"
    _reset_config_for_testing()
    yield
    # Restore original value
    if original_value is not None:
        os.environ["METRICS_MCP_ENABLED"] = original_value
    else:
        os.environ.pop("METRICS_MCP_ENABLED", None)
    _reset_config_for_testing()


class TestMCPConfig:
    """Tests for MCP configuration."""

    def test_mcp_config_enabled_by_default(self) -> None:
        """Test MCP is enabled by default."""
        _reset_config_for_testing()
        config = get_config()
        assert config.mcp.enabled is True

    @pytest.mark.usefixtures("mcp_disabled_env")
    def test_mcp_config_disabled_via_env(self) -> None:
        """Test MCP can be disabled via environment."""
        config = get_config()
        assert config.mcp.enabled is False

    def test_mcp_enabled_with_true_string(self) -> None:
        """Test MCP enabled with 'true' string."""
        os.environ["METRICS_MCP_ENABLED"] = "true"
        try:
            _reset_config_for_testing()
            config = get_config()
            assert config.mcp.enabled is True
        finally:
            _reset_config_for_testing()

    def test_mcp_enabled_with_one_string(self) -> None:
        """Test MCP enabled with '1' string."""
        os.environ["METRICS_MCP_ENABLED"] = "1"
        try:
            _reset_config_for_testing()
            config = get_config()
            assert config.mcp.enabled is True
        finally:
            os.environ["METRICS_MCP_ENABLED"] = "true"
            _reset_config_for_testing()

    def test_mcp_disabled_with_false_string(self) -> None:
        """Test MCP disabled with 'false' string."""
        os.environ["METRICS_MCP_ENABLED"] = "false"
        try:
            _reset_config_for_testing()
            config = get_config()
            assert config.mcp.enabled is False
        finally:
            os.environ["METRICS_MCP_ENABLED"] = "true"
            _reset_config_for_testing()

    def test_mcp_disabled_with_zero_string(self) -> None:
        """Test MCP disabled with '0' string."""
        os.environ["METRICS_MCP_ENABLED"] = "0"
        try:
            _reset_config_for_testing()
            config = get_config()
            assert config.mcp.enabled is False
        finally:
            os.environ["METRICS_MCP_ENABLED"] = "true"
            _reset_config_for_testing()

    def test_mcp_disabled_with_random_string(self) -> None:
        """Test MCP disabled with random string (not truthy)."""
        os.environ["METRICS_MCP_ENABLED"] = "random"
        try:
            _reset_config_for_testing()
            config = get_config()
            assert config.mcp.enabled is False
        finally:
            os.environ["METRICS_MCP_ENABLED"] = "true"
            _reset_config_for_testing()


class TestMCPEndpoint:
    """Tests for MCP endpoint registration."""

    def test_mcp_endpoint_registered(self) -> None:
        """Test /mcp endpoint is registered in the app."""
        mcp_routes = [route for route in app.routes if hasattr(route, "path") and route.path == "/mcp"]
        assert len(mcp_routes) == 1, "MCP endpoint should be registered at /mcp"

    def test_mcp_endpoint_methods(self) -> None:
        """Test /mcp endpoint accepts correct HTTP methods."""
        mcp_routes = [route for route in app.routes if hasattr(route, "path") and route.path == "/mcp"]
        assert len(mcp_routes) == 1

        mcp_route = mcp_routes[0]
        assert hasattr(mcp_route, "methods")
        assert {"GET", "POST", "DELETE"}.issubset(mcp_route.methods)

    def test_excluded_endpoints_have_mcp_exclude_tag(self) -> None:
        """Test that endpoints meant to be excluded have mcp_exclude tag."""
        excluded_paths = ["/metrics", "/dashboard", "/favicon.ico"]

        for route in app.routes:
            if hasattr(route, "path") and route.path in excluded_paths:
                # Route MUST have tags attribute
                assert hasattr(route, "tags"), f"Route {route.path} must have tags attribute"
                # Route MUST have mcp_exclude tag
                assert "mcp_exclude" in route.tags, f"Route {route.path} should have mcp_exclude tag"
