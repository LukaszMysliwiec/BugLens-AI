"""Result aggregation and scoring.

Scoring formula:
  Start at 100. Subtract points based on the severity of failed tests:
    critical → -30
    high     → -20
    medium   → -10
    low      → -5
    info     →  0

  Score is clamped to [0, 100].
"""

from __future__ import annotations

from app.models.schemas import QAScore, Severity, TestResult, TestStatus

_SEVERITY_PENALTY: dict[Severity, int] = {
    Severity.critical: 30,
    Severity.high: 20,
    Severity.medium: 10,
    Severity.low: 5,
    Severity.info: 0,
}


def compute_score(test_results: list[TestResult]) -> QAScore:
    """Calculate an overall quality score from the test results."""
    score = 100
    breakdown: dict[str, int] = {}

    for result in test_results:
        if result.status != TestStatus.failed:
            continue
        penalty = _SEVERITY_PENALTY.get(result.severity, 0)
        score -= penalty
        if penalty:
            breakdown[result.check_name] = -penalty

    score = max(0, min(100, score))
    return QAScore(total=score, breakdown=breakdown)
