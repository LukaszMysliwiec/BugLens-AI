"""AI analyzer – calls OpenAI to generate insights from QA results.

Design decisions:
- Input is always structured JSON (never raw HTML) to stay within token limits.
- temperature=0.2 for near-deterministic output while allowing some flexibility.
- A fallback analysis is returned when the API key is absent or the call fails,
  so the rest of the pipeline continues to work without AI.
- JSON parsing is strict: if the model output is not valid JSON we log the
  raw text and fall back to the static fallback.
"""

from __future__ import annotations

import json
import logging

from app.ai.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from app.models.schemas import AIAnalysis, AIInsight, PageElements, Severity, TestResult
from app.utils.settings import settings

logger = logging.getLogger(__name__)


def _fallback_analysis(reason: str) -> AIAnalysis:
    """Return a safe fallback when AI is unavailable."""
    return AIAnalysis(
        summary=(
            "AI analysis is currently unavailable. "
            "Please review the automated test results below for detected issues."
        ),
        insights=[
            AIInsight(
                category="info",
                severity=Severity.info,
                issue=f"AI analysis skipped: {reason}",
                recommendation="Configure OPENAI_API_KEY to enable AI-powered insights.",
            )
        ],
        test_suggestions=[],
        ux_recommendations=[],
        fallback_used=True,
    )


def _parse_ai_response(raw: str, model: str) -> AIAnalysis:
    """Parse the model's JSON output into an AIAnalysis object."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("AI response was not valid JSON: %s", exc)
        raise

    insights = [
        AIInsight(
            category=i.get("category", "info"),
            severity=Severity(i.get("severity", "info")),
            issue=i.get("issue", ""),
            recommendation=i.get("recommendation", ""),
            affected_element=i.get("affected_element"),
        )
        for i in data.get("insights", [])
    ]

    return AIAnalysis(
        summary=data.get("summary", ""),
        insights=insights,
        test_suggestions=data.get("test_suggestions", []),
        ux_recommendations=data.get("ux_recommendations", []),
        ai_model_used=model,
        fallback_used=False,
    )


async def analyze(elements: PageElements, test_results: list[TestResult]) -> AIAnalysis:
    """Run AI analysis and return structured insights.

    Falls back gracefully on configuration errors or API failures.
    """
    if not settings.openai_api_key:
        return _fallback_analysis("OPENAI_API_KEY not configured")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        user_prompt = build_user_prompt(elements, test_results)

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=settings.openai_max_tokens,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or ""
        return _parse_ai_response(raw_content, settings.openai_model)

    except Exception as exc:
        logger.error("AI analysis failed: %s", exc, exc_info=True)
        return _fallback_analysis(str(exc))
