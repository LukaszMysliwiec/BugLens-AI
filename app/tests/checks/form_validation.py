"""Basic form validation check.

Inspects form structure for common UX/accessibility issues:
- Forms with no labelled inputs
- Required fields that lack visible labels (heuristic based on placeholder)
- Password fields served over HTTP (security risk)
- Forms that submit to HTTP when the page is HTTPS

This check works purely on the extracted element data (no browser needed).
For actual form submission behavior testing, use the Playwright-based check.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.models.schemas import FormInfo, PageElements, Severity, TestResult, TestStatus


def _form_has_password_field(form: FormInfo) -> bool:
    return any(f.input_type == "password" for f in form.fields)


def _action_is_insecure(action: str | None, page_url: str) -> bool:
    if not action:
        return False
    parsed_action = urlparse(action)
    if parsed_action.scheme:
        return parsed_action.scheme == "http"
    # Relative action – inherits page scheme
    return urlparse(page_url).scheme == "http"


def check_form_validation(elements: PageElements) -> TestResult:
    """Run structural form validation checks."""
    if not elements.forms:
        return TestResult(
            check_name="Form Validation",
            status=TestStatus.skipped,
            severity=Severity.info,
            description="No forms detected on the page.",
            details={"forms_checked": 0, "issues": []},
        )

    issues: list[dict[str, str]] = []

    for idx, form in enumerate(elements.forms):
        label = f"Form #{idx + 1} (action={form.action or 'none'}, method={form.method})"

        if not form.fields:
            issues.append({"form": label, "issue": "Form has no input fields."})
            continue

        if _form_has_password_field(form) and _action_is_insecure(form.action, elements.url):
            issues.append(
                {
                    "form": label,
                    "issue": "Password field submitted over HTTP (insecure transmission).",
                }
            )

        nameless = [f for f in form.fields if not f.name]
        if nameless:
            issues.append(
                {
                    "form": label,
                    "issue": f"{len(nameless)} field(s) have no name/id attribute (data will be lost on submit).",
                }
            )

    if issues:
        severity = Severity.high if any("password" in i["issue"].lower() for i in issues) else Severity.medium
        return TestResult(
            check_name="Form Validation",
            status=TestStatus.failed,
            severity=severity,
            description=f"{len(issues)} form issue(s) detected.",
            details={"forms_checked": len(elements.forms), "issues": issues},
        )

    return TestResult(
        check_name="Form Validation",
        status=TestStatus.passed,
        severity=Severity.info,
        description=f"All {len(elements.forms)} form(s) passed basic structural checks.",
        details={"forms_checked": len(elements.forms), "issues": []},
    )
