"""Alt attribute check.

Images that lack an `alt` attribute are inaccessible to screen-reader users
and hurt SEO.  This check flags every <img> that has no alt text.
"""

from __future__ import annotations

from app.models.schemas import PageElements, Severity, TestResult, TestStatus


def check_alt_attributes(elements: PageElements) -> TestResult:
    """Return a TestResult indicating how many images are missing alt text."""
    missing = elements.images_without_alt

    if not missing:
        return TestResult(
            check_name="Image Alt Attributes",
            status=TestStatus.passed,
            severity=Severity.info,
            description="All images have alt attributes.",
            details={"images_without_alt": []},
        )

    severity = Severity.high if len(missing) > 3 else Severity.medium
    return TestResult(
        check_name="Image Alt Attributes",
        status=TestStatus.failed,
        severity=severity,
        description=f"{len(missing)} image(s) are missing alt attributes.",
        details={"images_without_alt": missing[:20]},  # cap list to avoid bloat
    )
