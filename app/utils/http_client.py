"""Async HTTP client configured for web-page fetching.

Uses httpx with a realistic User-Agent header and configurable timeout.
All callers share a single client instance (connection pool reuse).
"""

from __future__ import annotations

import httpx

from app.utils.settings import settings

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BugLensAI/1.0; +https://github.com/LukaszMysliwiec/BugLens-AI)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            timeout=settings.http_timeout,
            follow_redirects=True,
            verify=True,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
