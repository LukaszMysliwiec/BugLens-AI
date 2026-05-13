"""HTTP status code check.

Verifies that the target URL returns a 2xx response.  Any non-2xx status is
flagged as a failure with the appropriate severity.
"""

from __future__ import annotations

from app.models.schemas import Severity, TestResult, TestStatus


def check_status_code(url: str, status_code: int) -> TestResult:
    """Return a TestResult based on the HTTP status code received for *url*."""
    if status_code == 0:
        return TestResult(
            check_name="HTTP Status Code",
            status=TestStatus.failed,
            severity=Severity.critical,
            description="Page could not be reached – connection failed or timed out.",
            details={"url": url, "status_code": status_code},
        )

    if 200 <= status_code < 300:
        return TestResult(
            check_name="HTTP Status Code",
            status=TestStatus.passed,
            severity=Severity.info,
            description=f"Page returned HTTP {status_code} – OK.",
            details={"url": url, "status_code": status_code},
        )

    severity = Severity.critical if status_code >= 500 else Severity.high
    label = "server error" if status_code >= 500 else "client error / redirect"
    return TestResult(
        check_name="HTTP Status Code",
        status=TestStatus.failed,
        severity=severity,
        description=f"Page returned HTTP {status_code} ({label}).",
        details={"url": url, "status_code": status_code},
    )
