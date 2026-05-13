"""Test runner – orchestrates all QA checks using the Strategy pattern.

Each check is a callable that accepts specific arguments and returns a
TestResult.  The runner invokes them all and collects results.
"""

from __future__ import annotations

import asyncio

from app.models.schemas import PageElements, TestResult
from app.tests.checks.alt_attributes import check_alt_attributes
from app.tests.checks.broken_links import check_broken_links
from app.tests.checks.form_validation import check_form_validation
from app.tests.checks.meta_tags import check_meta_tags
from app.tests.checks.status_check import check_status_code


async def run_all_checks(elements: PageElements, status_code: int) -> list[TestResult]:
    """Execute every QA check and return the combined list of results.

    Synchronous checks run immediately; async checks (network I/O) are
    awaited concurrently to keep total latency low.
    """
    results: list[TestResult] = []

    # --- Synchronous checks (no I/O) ---
    results.append(check_status_code(elements.url, status_code))
    results.append(check_meta_tags(elements))
    results.append(check_alt_attributes(elements))
    results.append(check_form_validation(elements))

    # --- Async check (network I/O) ---
    broken_links_result = await check_broken_links(elements.links)
    results.append(broken_links_result)

    return results
