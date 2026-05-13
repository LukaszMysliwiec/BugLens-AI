"""Pydantic request/response schemas for the BugLens AI API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class TestStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


class AnalysisStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Scanner data models
# ---------------------------------------------------------------------------


class FormField(BaseModel):
    name: str | None = None
    input_type: str = "text"
    required: bool = False
    placeholder: str | None = None


class FormInfo(BaseModel):
    action: str | None = None
    method: str = "get"
    fields: list[FormField] = Field(default_factory=list)


class LinkInfo(BaseModel):
    href: str
    text: str | None = None
    is_external: bool = False


class PageElements(BaseModel):
    """Structured page data extracted by the scanner."""

    url: str
    title: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None
    forms: list[FormInfo] = Field(default_factory=list)
    inputs: list[FormField] = Field(default_factory=list)
    buttons: list[str] = Field(default_factory=list)
    links: list[LinkInfo] = Field(default_factory=list)
    images_without_alt: list[str] = Field(default_factory=list)
    heading_structure: list[str] = Field(default_factory=list)
    has_viewport_meta: bool = False


# ---------------------------------------------------------------------------
# Test result models
# ---------------------------------------------------------------------------


class TestResult(BaseModel):
    check_name: str
    status: TestStatus
    severity: Severity = Severity.info
    description: str
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# AI insight models
# ---------------------------------------------------------------------------


class AIInsight(BaseModel):
    category: str
    severity: Severity
    issue: str
    recommendation: str
    affected_element: str | None = None


class AIAnalysis(BaseModel):
    summary: str
    insights: list[AIInsight] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)
    ux_recommendations: list[str] = Field(default_factory=list)
    ai_model_used: str | None = None
    fallback_used: bool = False


# ---------------------------------------------------------------------------
# Aggregated result
# ---------------------------------------------------------------------------


class QAScore(BaseModel):
    total: int = Field(ge=0, le=100)
    breakdown: dict[str, int] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    id: str
    url: str
    status: AnalysisStatus = AnalysisStatus.pending
    page_elements: PageElements | None = None
    test_results: list[TestResult] = Field(default_factory=list)
    ai_analysis: AIAnalysis | None = None
    score: QAScore | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# API request / response shapes
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    url: AnyHttpUrl
    use_browser: bool = Field(
        default=False,
        description=(
            "When True, Playwright headless browser is used to fetch the page, "
            "enabling JavaScript-rendered content and basic form interaction checks."
        ),
    )


class AnalyzeResponse(BaseModel):
    id: str
    status: AnalysisStatus
    message: str = "Analysis started"
