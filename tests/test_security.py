"""Tests for security utilities.

Tests security functions including:
- Webhook signature verification
- IP allowlist verification
- GitHub and Cloudflare IP list fetching
"""

import hashlib
import hmac
import ipaddress
import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException, Request

from backend.utils.security import (
    get_cloudflare_allowlist,
    get_github_allowlist,
    verify_ip_allowlist,
    verify_signature,
)


class TestVerifySignature:
    """Tests for webhook signature verification."""

    def test_verify_signature_with_valid_signature(self) -> None:
        """Test signature verification passes with valid signature."""
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        secret = "test_secret"  # pragma: allowlist secret

        # Generate valid signature
        hash_object = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
        signature = "sha256=" + hash_object.hexdigest()

        # Should not raise exception
        verify_signature(payload_bytes, secret, signature)

    def test_verify_signature_with_invalid_signature(self) -> None:
        """Test signature verification fails with invalid signature."""
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")
        secret = "test_secret"  # pragma: allowlist secret
        invalid_signature = "sha256=invalid_hash"

        with pytest.raises(HTTPException) as exc_info:
            verify_signature(payload_bytes, secret, invalid_signature)

        assert exc_info.value.status_code == 403
        assert "didn't match" in exc_info.value.detail

    def test_verify_signature_with_missing_signature(self) -> None:
        """Test signature verification fails when signature header missing."""
        payload_bytes = b'{"test": "data"}'
        secret = "test_secret"  # pragma: allowlist secret

        with pytest.raises(HTTPException) as exc_info:
            verify_signature(payload_bytes, secret, None)

        assert exc_info.value.status_code == 403
        assert "missing" in exc_info.value.detail

    def test_verify_signature_with_wrong_secret(self) -> None:
        """Test signature verification fails with wrong secret."""
        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Generate signature with one secret
        secret1 = "correct_secret"  # pragma: allowlist secret
        hash_object = hmac.new(secret1.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
        signature = "sha256=" + hash_object.hexdigest()

        # Try to verify with different secret
        secret2 = "wrong_secret"  # pragma: allowlist secret
        with pytest.raises(HTTPException) as exc_info:
            verify_signature(payload_bytes, secret2, signature)

        assert exc_info.value.status_code == 403


class TestVerifyIPAllowlist:
    """Tests for IP allowlist verification."""

    async def test_verify_ip_with_empty_allowlist(self) -> None:
        """Test IP verification passes when allowlist is empty."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"

        # Empty allowlist should allow all IPs
        await verify_ip_allowlist(request, ())

    async def test_verify_ip_with_allowed_ip(self) -> None:
        """Test IP verification passes for allowed IP."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.10"

        allowed_ips = (ipaddress.ip_network("192.168.1.0/24"),)

        # Should not raise exception
        await verify_ip_allowlist(request, allowed_ips)

    async def test_verify_ip_with_blocked_ip(self) -> None:
        """Test IP verification fails for blocked IP."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.1"

        allowed_ips = (ipaddress.ip_network("192.168.1.0/24"),)

        with pytest.raises(HTTPException) as exc_info:
            await verify_ip_allowlist(request, allowed_ips)

        assert exc_info.value.status_code == 403
        assert "not in allowlist" in exc_info.value.detail

    async def test_verify_ip_with_multiple_ranges(self) -> None:
        """Test IP verification with multiple allowed ranges."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "10.0.0.50"

        allowed_ips = (
            ipaddress.ip_network("192.168.1.0/24"),
            ipaddress.ip_network("10.0.0.0/24"),
            ipaddress.ip_network("172.16.0.0/16"),
        )

        # Should not raise exception - IP is in second range
        await verify_ip_allowlist(request, allowed_ips)

    async def test_verify_ip_without_client(self) -> None:
        """Test IP verification fails when client info missing."""
        request = Mock(spec=Request)
        request.client = None

        allowed_ips = (ipaddress.ip_network("192.168.1.0/24"),)

        with pytest.raises(HTTPException) as exc_info:
            await verify_ip_allowlist(request, allowed_ips)

        assert exc_info.value.status_code == 400
        assert "determine client IP" in exc_info.value.detail

    async def test_verify_ip_with_invalid_ip_format(self) -> None:
        """Test IP verification fails with invalid IP address."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "invalid_ip"

        allowed_ips = (ipaddress.ip_network("192.168.1.0/24"),)

        with pytest.raises(HTTPException) as exc_info:
            await verify_ip_allowlist(request, allowed_ips)

        assert exc_info.value.status_code == 400
        assert "parse client IP" in exc_info.value.detail

    async def test_verify_ip_with_ipv6(self) -> None:
        """Test IP verification works with IPv6 addresses."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "2001:db8::1"

        allowed_ips = (ipaddress.ip_network("2001:db8::/32"),)

        # Should not raise exception
        await verify_ip_allowlist(request, allowed_ips)


class TestGetGitHubAllowlist:
    """Tests for fetching GitHub IP allowlist."""

    async def test_get_github_allowlist_success(self) -> None:
        """Test successful GitHub allowlist retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {"hooks": ["192.30.252.0/22", "185.199.108.0/22", "140.82.112.0/20"]}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_github_allowlist(mock_client)

        assert result == ["192.30.252.0/22", "185.199.108.0/22", "140.82.112.0/20"]
        mock_client.get.assert_called_once_with("https://api.github.com/meta", timeout=10.0)

    async def test_get_github_allowlist_empty_hooks(self) -> None:
        """Test GitHub allowlist with empty hooks list."""
        mock_response = Mock()
        mock_response.json.return_value = {"hooks": []}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_github_allowlist(mock_client)

        assert result == []

    async def test_get_github_allowlist_http_error(self) -> None:
        """Test GitHub allowlist fetch handles HTTP errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))

        with pytest.raises(httpx.RequestError):
            await get_github_allowlist(mock_client)


class TestGetCloudflareAllowlist:
    """Tests for fetching Cloudflare IP allowlist."""

    async def test_get_cloudflare_allowlist_success(self) -> None:
        """Test successful Cloudflare allowlist retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "ipv4_cidrs": ["103.21.244.0/22", "103.22.200.0/22"],
                "ipv6_cidrs": ["2400:cb00::/32", "2606:4700::/32"],
            },
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_cloudflare_allowlist(mock_client)

        assert result == [
            "103.21.244.0/22",
            "103.22.200.0/22",
            "2400:cb00::/32",
            "2606:4700::/32",
        ]
        mock_client.get.assert_called_once_with("https://api.cloudflare.com/client/v4/ips", timeout=10.0)

    async def test_get_cloudflare_allowlist_empty_result(self) -> None:
        """Test Cloudflare allowlist with empty results."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_cloudflare_allowlist(mock_client)

        assert result == []

    async def test_get_cloudflare_allowlist_http_error(self) -> None:
        """Test Cloudflare allowlist fetch handles HTTP errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))

        with pytest.raises(httpx.RequestError):
            await get_cloudflare_allowlist(mock_client)


class TestSecurityEdgeCases:
    """Additional tests for security utilities edge cases and error handling."""

    async def test_get_github_allowlist_unexpected_error(self) -> None:
        """Test GitHub allowlist handles unexpected errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=Exception("Unexpected error"))

        with pytest.raises(Exception, match="Unexpected error"):
            await get_github_allowlist(mock_client)

    async def test_get_github_allowlist_http_timeout(self) -> None:
        """Test GitHub allowlist handles HTTP timeout errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(httpx.TimeoutException):
            await get_github_allowlist(mock_client)

    async def test_get_github_allowlist_missing_hooks_key(self) -> None:
        """Test GitHub allowlist with missing hooks key in response."""
        mock_response = Mock()
        mock_response.json.return_value = {}  # No 'hooks' key
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_github_allowlist(mock_client)

        # Should return empty list when key is missing
        assert result == []

    async def test_get_cloudflare_allowlist_unexpected_error(self) -> None:
        """Test Cloudflare allowlist handles unexpected errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=Exception("Unexpected error"))

        with pytest.raises(Exception, match="Unexpected error"):
            await get_cloudflare_allowlist(mock_client)

    async def test_get_cloudflare_allowlist_http_timeout(self) -> None:
        """Test Cloudflare allowlist handles HTTP timeout errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        with pytest.raises(httpx.TimeoutException):
            await get_cloudflare_allowlist(mock_client)

    async def test_get_cloudflare_allowlist_missing_ipv4(self) -> None:
        """Test Cloudflare allowlist with missing ipv4_cidrs."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": {"ipv6_cidrs": ["2400:cb00::/32"]}}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_cloudflare_allowlist(mock_client)

        # Should only return IPv6 CIDRs
        assert result == ["2400:cb00::/32"]

    async def test_get_cloudflare_allowlist_missing_ipv6(self) -> None:
        """Test Cloudflare allowlist with missing ipv6_cidrs."""
        mock_response = Mock()
        mock_response.json.return_value = {"result": {"ipv4_cidrs": ["103.21.244.0/22"]}}
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_cloudflare_allowlist(mock_client)

        # Should only return IPv4 CIDRs
        assert result == ["103.21.244.0/22"]

    async def test_get_cloudflare_allowlist_missing_result_key(self) -> None:
        """Test Cloudflare allowlist with missing result key in response."""
        mock_response = Mock()
        mock_response.json.return_value = {}  # No 'result' key
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await get_cloudflare_allowlist(mock_client)

        # Should return empty list when key is missing
        assert result == []
