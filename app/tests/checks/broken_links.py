"""Broken link detection check.

Fetches a sample of links found on the page (up to MAX_LINKS_TO_CHECK) and
reports any that return non-2xx responses.  Link checking runs concurrently
to stay within a reasonable time budget.
"""

from __future__ import annotations

import asyncio

from app.models.schemas import LinkInfo, Severity, TestResult, TestStatus
from app.utils.http_client import get_client
from app.utils.settings import settings


async def _check_link(url: str) -> tuple[str, int]:
    """Return (url, status_code); status_code=0 on network failure."""
    client = get_client()
    try:
        response = await client.head(url, follow_redirects=True)
        # Some servers reject HEAD; retry with GET on 405
        if response.status_code == 405:
            response = await client.get(url, follow_redirects=True)
        return url, response.status_code
    except Exception:
        return url, 0


async def check_broken_links(links: list[LinkInfo]) -> TestResult:
    """Check a representative sample of page links for broken responses."""
    if not links:
        return TestResult(
            check_name="Broken Links",
            status=TestStatus.skipped,
            severity=Severity.info,
            description="No links found on the page to check.",
            details={"links_checked": 0, "broken": []},
        )

    sample = links[: settings.max_links_to_check]
    tasks = [_check_link(link.href) for link in sample]
    results = await asyncio.gather(*tasks)

    broken = [
        {"url": url, "status_code": code}
        for url, code in results
        if not (200 <= code < 400)
    ]

    if broken:
        return TestResult(
            check_name="Broken Links",
            status=TestStatus.failed,
            severity=Severity.high,
            description=f"{len(broken)} broken or unreachable link(s) detected out of {len(sample)} checked.",
            details={
                "links_checked": len(sample),
                "broken": broken,
            },
        )

    return TestResult(
        check_name="Broken Links",
        status=TestStatus.passed,
        severity=Severity.info,
        description=f"All {len(sample)} sampled links returned valid responses.",
        details={"links_checked": len(sample), "broken": []},
    )
