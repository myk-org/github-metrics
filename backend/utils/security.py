"""Security utilities for webhook verification."""

import hashlib
import hmac
import ipaddress

import httpx
from fastapi import HTTPException, Request, status
from simple_logger.logger import get_logger

# Type alias for IP networks (avoiding private type)
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Constants
HTTP_TIMEOUT_SECONDS: float = 10.0
GITHUB_META_URL: str = "https://api.github.com/meta"
CLOUDFLARE_IPS_URL: str = "https://api.cloudflare.com/client/v4/ips"

LOGGER = get_logger(name="backend.utils.security")


async def get_github_allowlist(http_client: httpx.AsyncClient) -> list[str]:
    """Fetch GitHub IP allowlist asynchronously."""
    try:
        response = await http_client.get(GITHUB_META_URL, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        return data.get("hooks", [])
    except httpx.RequestError:
        LOGGER.exception("Error fetching GitHub allowlist")
        raise
    except Exception:
        LOGGER.exception("Unexpected error fetching GitHub allowlist")
        raise


async def get_cloudflare_allowlist(http_client: httpx.AsyncClient) -> list[str]:
    """Fetch Cloudflare IP allowlist asynchronously."""
    try:
        response = await http_client.get(CLOUDFLARE_IPS_URL, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json().get("result", {})
        return result.get("ipv4_cidrs", []) + result.get("ipv6_cidrs", [])
    except httpx.RequestError:
        LOGGER.exception("Error fetching Cloudflare allowlist")
        raise
    except Exception:
        LOGGER.exception("Unexpected error fetching Cloudflare allowlist")
        raise


def verify_signature(payload_body: bytes, secret_token: str, signature_header: str | None = None) -> None:
    """Verify that the payload was sent from GitHub by validating SHA256.

    Args:
        payload_body: original request body to verify
        secret_token: GitHub webhook secret token
        signature_header: header received from GitHub (x-hub-signature-256)

    Raises:
        HTTPException: 403 if signature is missing or invalid
    """
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="x-hub-signature-256 header is missing!")

    hash_object = hmac.new(secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request signatures didn't match!")


async def verify_ip_allowlist(request: Request, allowed_ips: tuple[IPNetwork, ...]) -> None:
    """Verify request IP is in allowlist.

    Args:
        request: FastAPI request object
        allowed_ips: Tuple of allowed IP networks

    Raises:
        HTTPException: 400 if IP cannot be determined, 403 if IP not in allowlist
    """
    if not allowed_ips:
        return

    if not request.client or not request.client.host:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not determine client IP address")

    try:
        src_ip = ipaddress.ip_address(request.client.host)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not parse client IP address") from e

    for valid_ip_range in allowed_ips:
        if src_ip in valid_ip_range:
            return

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"{src_ip} IP is not in allowlist",
    )
