"""Thread-safe in-memory result store.

In production this would be replaced with Redis or a database, but for the
MVP a simple dict protected by a lock is sufficient.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.models.schemas import AnalysisResult

_store: dict[str, AnalysisResult] = {}
_lock = asyncio.Lock()


async def save(result: AnalysisResult) -> None:
    async with _lock:
        _store[result.id] = result


async def get(result_id: str) -> Optional[AnalysisResult]:
    async with _lock:
        return _store.get(result_id)


async def list_all() -> list[AnalysisResult]:
    async with _lock:
        return list(_store.values())
