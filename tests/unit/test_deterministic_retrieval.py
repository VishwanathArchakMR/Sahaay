"""Unit tests for deterministic source-grounded information retrieval."""

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.api.v1.sources import source_manager
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_deterministic_keyword_search():
    """Verify local text search extracts snippet, provenance, and does not use AI models."""
    transport = ASGITransport(app=app)

    # Ingest test tab observation
    tab_data = {
        "url": "https://docs.python.org/3/library/asyncio.html",
        "title": "asyncio — Asynchronous I/O",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1200, "height": 4500},
        "visibleTextExcerpt": (
            "asyncio is a library to write concurrent code using the async/await syntax. "
            "asyncio is used as a foundation for multiple Python asynchronous frameworks."
        ),
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        # 1. Observe tab
        obs_res = await client.post("/api/v1/browser/observe", json=tab_data)
        assert obs_res.status_code == 200
        source_id = obs_res.json()["sourceId"]

        # 2. Search for exact keyword
        search_req = {"query": "concurrent code"}
        search_res = await client.post("/api/v1/sources/search", json=search_req)
        assert search_res.status_code == 200
        data = search_res.json()

        assert data["count"] >= 1
        assert data["isModelInference"] is False

        matched = [r for r in data["results"] if r["sourceId"] == source_id]
        assert len(matched) >= 1
        assert "concurrent code" in matched[0]["matchedSnippet"].lower()
        assert matched[0]["sourceUri"] == tab_data["url"]
        assert matched[0]["sourceTitle"] == tab_data["title"]


@pytest.mark.asyncio
async def test_search_respects_source_revocation():
    """Verify that revoked sources are strictly excluded from search results."""
    transport = ASGITransport(app=app)

    tab_data = {
        "url": "https://confidential-portal.local/records",
        "title": "Confidential Internal Records",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1000, "height": 2000},
        "visibleTextExcerpt": "Top secret project quantum leap documentation and plans.",
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        # Ingest
        obs_res = await client.post("/api/v1/browser/observe", json=tab_data)
        source_id = obs_res.json()["sourceId"]

        # Verify it can be found before revocation
        s1 = await client.post("/api/v1/sources/search", json={"query": "quantum leap"})
        matches1 = [r for r in s1.json()["results"] if r["sourceId"] == source_id]
        assert len(matches1) == 1

        # Revoke source
        from uuid import UUID

        source_manager.revoke_source(UUID(source_id))

        # Verify it cannot be found after revocation
        s2 = await client.post("/api/v1/sources/search", json={"query": "quantum leap"})
        matches2 = [r for r in s2.json()["results"] if r["sourceId"] == source_id]
        assert len(matches2) == 0
