"""Tests for the scoring service."""

from __future__ import annotations

from app.models.schemas import Severity, TestResult, TestStatus
from app.services.scoring import compute_score


def _result(status: TestStatus, severity: Severity, name: str = "Check") -> TestResult:
    return TestResult(
        check_name=name,
        status=status,
        severity=severity,
        description="test",
    )


class TestComputeScore:
    def test_all_passed_is_100(self):
        results = [_result(TestStatus.passed, Severity.info)]
        score = compute_score(results)
        assert score.total == 100

    def test_critical_failure_deducts_30(self):
        results = [_result(TestStatus.failed, Severity.critical)]
        score = compute_score(results)
        assert score.total == 70

    def test_high_failure_deducts_20(self):
        results = [_result(TestStatus.failed, Severity.high)]
        score = compute_score(results)
        assert score.total == 80

    def test_medium_failure_deducts_10(self):
        results = [_result(TestStatus.failed, Severity.medium)]
        score = compute_score(results)
        assert score.total == 90

    def test_score_clamped_to_zero(self):
        results = [
            _result(TestStatus.failed, Severity.critical, "A"),
            _result(TestStatus.failed, Severity.critical, "B"),
            _result(TestStatus.failed, Severity.critical, "C"),
            _result(TestStatus.failed, Severity.critical, "D"),
        ]
        score = compute_score(results)
        assert score.total == 0

    def test_skipped_does_not_penalize(self):
        results = [_result(TestStatus.skipped, Severity.high)]
        score = compute_score(results)
        assert score.total == 100

    def test_breakdown_only_includes_penalties(self):
        results = [
            _result(TestStatus.failed, Severity.high, "Broken Links"),
            _result(TestStatus.passed, Severity.info, "Meta Tags"),
        ]
        score = compute_score(results)
        assert "Broken Links" in score.breakdown
        assert "Meta Tags" not in score.breakdown
