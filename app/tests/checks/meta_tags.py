"""Meta tag presence check.

Validates that the page includes essential SEO and social-sharing meta tags:
- <title>
- meta description
- meta viewport (mobile-friendliness)
"""

from __future__ import annotations

from app.models.schemas import PageElements, Severity, TestResult, TestStatus


def check_meta_tags(elements: PageElements) -> TestResult:
    """Detect missing or empty meta tags."""
    missing: list[str] = []

    if not elements.title:
        missing.append("<title>")
    if not elements.meta_description:
        missing.append('meta[name="description"]')
    if not elements.has_viewport_meta:
        missing.append('meta[name="viewport"]')

    if missing:
        return TestResult(
            check_name="Meta Tags",
            status=TestStatus.failed,
            severity=Severity.medium,
            description=f"{len(missing)} required meta element(s) missing.",
            details={"missing": missing},
        )

    return TestResult(
        check_name="Meta Tags",
        status=TestStatus.passed,
        severity=Severity.info,
        description="All essential meta tags are present.",
        details={"missing": []},
    )
