"""HTML parser – fetches a page and converts it to a BeautifulSoup tree.

Two strategies are supported:
- Static (default): plain httpx GET – fast, works for server-rendered pages.
- Browser (optional): Playwright headless Chromium – handles JS-rendered content.

All URLs are validated before fetching to prevent SSRF attacks.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.utils.http_client import get_client
from app.utils.settings import settings
from app.utils.url_validator import validate_url


async def fetch_html_static(url: str) -> str:
    """Fetch raw HTML using a plain HTTP GET request."""
    safe_url = validate_url(url)
    client = get_client()
    response = await client.get(safe_url)
    response.raise_for_status()
    return response.text


async def fetch_html_browser(url: str) -> str:
    """Fetch rendered HTML via Playwright headless Chromium.

    Falls back to static fetch if Playwright is unavailable.
    """
    safe_url = validate_url(url)
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(safe_url, wait_until="networkidle", timeout=settings.browser_timeout_ms)
            html = await page.content()
            await browser.close()
            return html
    except Exception:
        return await fetch_html_static(safe_url)


def parse_html(html: str) -> BeautifulSoup:
    """Return a BeautifulSoup tree from raw HTML."""
    return BeautifulSoup(html, "lxml")


async def fetch_and_parse(url: str, use_browser: bool = False) -> tuple[BeautifulSoup, int]:
    """Fetch *url* and return (soup, status_code).

    When *use_browser* is True, Playwright is used (JS rendering).
    Status code is obtained from a separate HEAD/GET request so it is
    always available regardless of the fetch strategy.

    Raises URLValidationError if the URL targets a private/internal host.
    """
    safe_url = validate_url(url)
    client = get_client()

    # Always record the actual HTTP status code via a direct request
    try:
        head_response = await client.head(safe_url)
        status_code = head_response.status_code
    except Exception:
        status_code = 0

    if use_browser:
        html = await fetch_html_browser(safe_url)
    else:
        try:
            response = await client.get(safe_url)
            status_code = response.status_code
            html = response.text
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch {safe_url}: {exc}") from exc

    soup = parse_html(html)
    return soup, status_code
