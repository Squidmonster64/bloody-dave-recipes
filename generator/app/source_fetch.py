"""SSRF-safe HTTP fetcher for recipe source pages."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from .config import settings

BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.com",
    "instance-data",
}


@dataclass
class FetchResult:
    submitted_url: str
    final_url: str
    content: bytes
    content_type: str
    status_code: int


class SourceFetchError(Exception):
    pass


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or (getattr(ip, "ipv4_mapped", None) and _is_blocked_ip(ip.ipv4_mapped))
    )


def validate_url_target(url: str, *, resolve_dns: bool = True) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise SourceFetchError("Only http:// and https:// URLs are allowed")
    if not parsed.hostname:
        raise SourceFetchError("URL host is required")
    host = parsed.hostname.lower().rstrip(".")
    if host in BLOCKED_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        raise SourceFetchError("URL host is not allowed")
    # Reject literal IPs that are private/metadata.
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip) or str(ip) in {"169.254.169.254", "fd00:ec2::254"}:
            raise SourceFetchError("Private or metadata IP addresses are blocked")
    except ValueError:
        pass

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise SourceFetchError(f"Could not resolve host: {host}") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if _is_blocked_ip(ip) or str(ip) in {"169.254.169.254"}:
                raise SourceFetchError("URL resolves to a blocked network address")
    return parsed.geturl() if parsed.geturl().startswith(parsed.scheme) else url.strip()


async def fetch_source(url: str, *, max_redirects: int = 5) -> FetchResult:
    current = validate_url_target(url)
    headers = {
        "User-Agent": "BloodyDaveRecipeStudio/1.0 (+https://recipes.bloodydaves.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        for _ in range(max_redirects + 1):
            validate_url_target(current)
            response = await client.get(current, headers=headers)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise SourceFetchError("Redirect without Location header")
                current = validate_url_target(urljoin(current, location))
                continue
            if response.status_code >= 400:
                raise SourceFetchError(f"Source returned HTTP {response.status_code}")
            content = response.content
            if len(content) > settings.max_source_bytes:
                raise SourceFetchError("Source response exceeds size limit")
            return FetchResult(
                submitted_url=url,
                final_url=str(response.url),
                content=content,
                content_type=response.headers.get("content-type", ""),
                status_code=response.status_code,
            )
    raise SourceFetchError("Too many redirects")
