"""Analysis orchestration service.

This module wires together the scanner, test runner, AI analyzer, and
result store into a single end-to-end pipeline:

  fetch page → extract elements → run QA checks → AI analysis → score → save
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.ai.analyzer import analyze as ai_analyze
from app.models.schemas import AnalysisResult, AnalysisStatus
from app.scanner.element_extractor import extract_elements
from app.scanner.html_parser import fetch_and_parse
from app.services.scoring import compute_score
from app.tests.test_runner import run_all_checks
from app.utils import storage

logger = logging.getLogger(__name__)


async def start_analysis(url: str, use_browser: bool = False) -> str:
    """Create a new analysis record and kick off the pipeline.

    Returns the analysis ID immediately so the caller can poll for results.
    The pipeline runs in the same async task – the API handler should
    call this via ``asyncio.create_task`` for true background execution.
    """
    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    result = AnalysisResult(
        id=analysis_id,
        url=url,
        status=AnalysisStatus.running,
        created_at=now,
    )
    await storage.save(result)
    return analysis_id


async def run_analysis(analysis_id: str, url: str, use_browser: bool = False) -> None:
    """Execute the full QA pipeline and persist the final result."""
    created_at: str | None = None
    existing = await storage.get(analysis_id)
    if existing:
        created_at = existing.created_at

    try:
        # 1. Fetch & parse
        logger.info("[%s] Fetching %s", analysis_id, url)
        soup, status_code = await fetch_and_parse(url, use_browser=use_browser)

        # 2. Extract structured elements
        elements = extract_elements(soup, url)

        # 3. Run QA checks
        logger.info("[%s] Running QA checks", analysis_id)
        test_results = await run_all_checks(elements, status_code)

        # 4. AI analysis
        logger.info("[%s] Running AI analysis", analysis_id)
        ai_analysis = await ai_analyze(elements, test_results)

        # 5. Score
        score = compute_score(test_results)

        # 6. Persist completed result
        completed_result = AnalysisResult(
            id=analysis_id,
            url=url,
            status=AnalysisStatus.completed,
            page_elements=elements,
            test_results=test_results,
            ai_analysis=ai_analysis,
            score=score,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        await storage.save(completed_result)
        logger.info("[%s] Analysis complete – score: %d/100", analysis_id, score.total)

    except Exception as exc:
        logger.error("[%s] Analysis failed: %s", analysis_id, exc, exc_info=True)
        failed_result = AnalysisResult(
            id=analysis_id,
            url=url,
            status=AnalysisStatus.failed,
            error=str(exc),
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        await storage.save(failed_result)
