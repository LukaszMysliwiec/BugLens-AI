"""Unit tests for the individual QA check functions."""

from __future__ import annotations

import pytest

from app.models.schemas import (
    FormField,
    FormInfo,
    LinkInfo,
    PageElements,
    Severity,
    TestStatus,
)
from app.tests.checks.alt_attributes import check_alt_attributes
from app.tests.checks.form_validation import check_form_validation
from app.tests.checks.meta_tags import check_meta_tags
from app.tests.checks.status_check import check_status_code


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _base_elements(**kwargs) -> PageElements:
    defaults = dict(
        url="https://example.com",
        title="Example",
        meta_description="A sample page",
        has_viewport_meta=True,
        forms=[],
        inputs=[],
        buttons=[],
        links=[],
        images_without_alt=[],
        heading_structure=[],
    )
    defaults.update(kwargs)
    return PageElements(**defaults)


# ──────────────────────────────────────────────────────────────────
# status_check
# ──────────────────────────────────────────────────────────────────

class TestStatusCheck:
    def test_200_passes(self):
        result = check_status_code("https://example.com", 200)
        assert result.status == TestStatus.passed

    def test_301_fails_as_high(self):
        result = check_status_code("https://example.com", 301)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.high

    def test_404_fails_as_high(self):
        result = check_status_code("https://example.com", 404)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.high

    def test_500_fails_as_critical(self):
        result = check_status_code("https://example.com", 500)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.critical

    def test_0_fails_as_critical(self):
        result = check_status_code("https://example.com", 0)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.critical

    def test_details_include_status_code(self):
        result = check_status_code("https://example.com", 403)
        assert result.details["status_code"] == 403


# ──────────────────────────────────────────────────────────────────
# meta_tags
# ──────────────────────────────────────────────────────────────────

class TestMetaTags:
    def test_all_present_passes(self):
        elements = _base_elements()
        result = check_meta_tags(elements)
        assert result.status == TestStatus.passed

    def test_missing_title_fails(self):
        elements = _base_elements(title=None)
        result = check_meta_tags(elements)
        assert result.status == TestStatus.failed
        assert "<title>" in result.details["missing"]

    def test_missing_description_fails(self):
        elements = _base_elements(meta_description=None)
        result = check_meta_tags(elements)
        assert result.status == TestStatus.failed

    def test_missing_viewport_fails(self):
        elements = _base_elements(has_viewport_meta=False)
        result = check_meta_tags(elements)
        assert result.status == TestStatus.failed
        assert 'meta[name="viewport"]' in result.details["missing"]

    def test_all_missing_reports_three(self):
        elements = _base_elements(title=None, meta_description=None, has_viewport_meta=False)
        result = check_meta_tags(elements)
        assert len(result.details["missing"]) == 3


# ──────────────────────────────────────────────────────────────────
# alt_attributes
# ──────────────────────────────────────────────────────────────────

class TestAltAttributes:
    def test_no_images_passes(self):
        elements = _base_elements(images_without_alt=[])
        result = check_alt_attributes(elements)
        assert result.status == TestStatus.passed

    def test_one_missing_medium(self):
        elements = _base_elements(images_without_alt=["logo.png"])
        result = check_alt_attributes(elements)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.medium

    def test_four_or_more_missing_high(self):
        elements = _base_elements(images_without_alt=["a.png", "b.png", "c.png", "d.png"])
        result = check_alt_attributes(elements)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.high

    def test_details_include_list(self):
        elements = _base_elements(images_without_alt=["x.png"])
        result = check_alt_attributes(elements)
        assert "x.png" in result.details["images_without_alt"]


# ──────────────────────────────────────────────────────────────────
# form_validation
# ──────────────────────────────────────────────────────────────────

class TestFormValidation:
    def test_no_forms_skipped(self):
        elements = _base_elements(forms=[])
        result = check_form_validation(elements)
        assert result.status == TestStatus.skipped

    def test_valid_form_passes(self):
        form = FormInfo(
            action="/submit",
            method="post",
            fields=[FormField(name="email", input_type="email", required=True)],
        )
        elements = _base_elements(forms=[form])
        result = check_form_validation(elements)
        assert result.status == TestStatus.passed

    def test_empty_form_fails(self):
        form = FormInfo(action="/submit", method="post", fields=[])
        elements = _base_elements(forms=[form])
        result = check_form_validation(elements)
        assert result.status == TestStatus.failed

    def test_password_over_http_fails_high(self):
        form = FormInfo(
            action="http://evil.example.com/login",
            method="post",
            fields=[FormField(name="password", input_type="password")],
        )
        elements = _base_elements(url="https://example.com", forms=[form])
        result = check_form_validation(elements)
        assert result.status == TestStatus.failed
        assert result.severity == Severity.high

    def test_nameless_fields_detected(self):
        form = FormInfo(
            action="/submit",
            method="post",
            fields=[FormField(name=None, input_type="text")],
        )
        elements = _base_elements(forms=[form])
        result = check_form_validation(elements)
        assert result.status == TestStatus.failed
        assert any("name/id" in i["issue"] for i in result.details["issues"])
