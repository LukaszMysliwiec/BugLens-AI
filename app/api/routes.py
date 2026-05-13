"""FastAPI route definitions.

POST /analyze  – submit a URL for analysis (non-blocking)
GET  /results/{id} – poll for analysis results
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.schemas import AnalysisStatus, AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import run_analysis, start_analysis
from app.utils import storage

router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a URL for QA analysis",
    description=(
        "Accepts a URL and optional browser flag. "
        "Returns an analysis ID immediately. "
        "Poll GET /results/{id} for the final report."
    ),
)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    url_str = str(request.url)
    analysis_id = await start_analysis(url_str, use_browser=request.use_browser)

    # Run the pipeline in the background so this endpoint returns quickly
    asyncio.create_task(run_analysis(analysis_id, url_str, use_browser=request.use_browser))

    return AnalyzeResponse(
        id=analysis_id,
        status=AnalysisStatus.running,
        message="Analysis started. Poll GET /results/{id} for results.",
    )


@router.get(
    "/results/{analysis_id}",
    summary="Retrieve analysis results",
    description="Returns the full analysis report once completed, or current status while running.",
)
async def get_results(analysis_id: str) -> JSONResponse:
    result = await storage.get(analysis_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found.",
        )
    return JSONResponse(content=result.model_dump())
