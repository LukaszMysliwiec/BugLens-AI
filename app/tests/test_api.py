"""Integration tests for the FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import AnalysisStatus, AnalysisResult
from app.utils import storage


@pytest.fixture(autouse=True)
def clear_storage():
    """Wipe the in-memory store before each test."""
    storage._store.clear()
    yield
    storage._store.clear()


class TestAnalyzeEndpoint:
    def test_returns_202_with_id(self):
        client = TestClient(app)
        resp = client.post("/api/analyze", json={"url": "https://example.com"})
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == AnalysisStatus.running.value

    def test_invalid_url_returns_422(self):
        client = TestClient(app)
        resp = client.post("/api/analyze", json={"url": "not-a-url"})
        assert resp.status_code == 422

    def test_missing_url_returns_422(self):
        client = TestClient(app)
        resp = client.post("/api/analyze", json={})
        assert resp.status_code == 422


class TestResultsEndpoint:
    def test_unknown_id_returns_404(self):
        client = TestClient(app)
        resp = client.get("/api/results/nonexistent-id")
        assert resp.status_code == 404

    def test_known_id_returns_result(self):
        import asyncio
        result = AnalysisResult(id="test-123", url="https://example.com", status=AnalysisStatus.running)
        asyncio.run(storage.save(result))

        client = TestClient(app)
        resp = client.get("/api/results/test-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "test-123"
        assert data["url"] == "https://example.com"
