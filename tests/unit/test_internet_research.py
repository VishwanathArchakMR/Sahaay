"""Unit and integration tests for the Keyless Internet Research subsystem."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sahaay_core.api.v1.sessions import session_manager
from sahaay_core.config.settings import settings
from sahaay_core.main import app
from sahaay_core.research.citations import CitationEngine
from sahaay_core.research.models import Citation
from sahaay_core.research.safe_fetcher import SafeWebFetcher, SSRFValidationError
from sahaay_core.research.search_adapter import InternetResearchManager, MockSearchProvider


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-Sahaay-Token": settings.api_token}


def test_ssrf_protection_blocks_private_and_metadata_addresses():
    """SafeWebFetcher must reject private IPs, loopback, cloud metadata, and unsupported schemes."""
    fetcher = SafeWebFetcher()

    unsafe_targets = [
        "http://localhost:8000/secrets",
        "http://127.0.0.1:8000/env",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.1.5/admin",
        "http://192.168.1.1/router",
        "http://172.16.0.1/internal",
        "file:///C:/Windows/win.ini",
        "ftp://example.com/file",
        "data:text/html,<script>alert(1)</script>",
    ]

    for target in unsafe_targets:
        with pytest.raises(SSRFValidationError):
            fetcher.validate_url(target)


def test_mock_search_provider_normalizes_results():
    """Mock search provider returns standard result structures."""
    provider = MockSearchProvider()
    results = provider.search("BESCOM electricity bill payment guidelines", max_results=2)

    assert len(results) == 2
    for r in results:
        assert r["title"]
        assert r["url"].startswith("https://")
        assert r["snippet"]


def test_citation_formatting_and_conflict_detection():
    """CitationEngine renders standard markdown footnotes and flags contradictory claims."""
    engine = CitationEngine()

    citations = [
        Citation(
            citation_id="cite-1",
            statement="Tariff rate is Rs 4.50 per unit.",
            source_id="src-1",
            url="https://bescom.karnataka.gov.in/rules",
            title="Karnataka Utility Guidelines 2026",
            retrieved_at="2026-10-28T12:00:00Z",
        ),
        Citation(
            citation_id="cite-2",
            statement="Tariff rate is Rs 5.25 per unit.",
            source_id="src-2",
            url="https://bangalore.gov.in/billing",
            title="Bangalore Consumer Portal",
            retrieved_at="2026-10-28T12:00:00Z",
        ),
    ]

    markdown = engine.format_citations_markdown(citations)
    assert "[1]" in markdown
    assert "https://bescom.karnataka.gov.in/rules" in markdown
    assert "Verified Source ID" in markdown

    # Detect conflicts between differing tariffs
    conflicts = engine.detect_conflicts(
        [
            {
                "field": "tariff",
                "value": "Rs 4.50",
                "sourceUrl": "https://bescom.karnataka.gov.in/rules",
            },
            {
                "field": "tariff",
                "value": "Rs 5.25",
                "sourceUrl": "https://bangalore.gov.in/billing",
            },
        ]
    )
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "tariff"
    assert len(conflicts[0]["divergentValues"]) == 2


@pytest.mark.asyncio
async def test_research_manager_local_only_mode_blocks_search():
    """When local_only_mode is active, search requests must be blocked with an honest status."""
    manager = InternetResearchManager()
    session = session_manager.create_session(local_only_mode=True)

    with patch.object(settings, "local_only_mode", True):
        resp = await manager.search_and_cite(
            query="Karnataka government solar subsidy",
            session_id=session.sessionId,
        )

        assert resp.status == "LOCAL_ONLY_BLOCKED"
        assert resp.results_count == 0
        assert resp.notice is not None and "local-only" in resp.notice.lower()


def test_research_api_search_endpoint(test_client, auth_headers):
    """POST /api/v1/research/search returns structured results and citations."""
    session = session_manager.create_session(local_only_mode=False)

    payload = {
        "sessionId": str(session.sessionId),
        "query": "Karnataka electricity bill",
        "maxResults": 2,
    }

    # Patch settings and provider to guarantee deterministic offline testing
    with patch.object(settings, "local_only_mode", False):
        with patch("sahaay_core.research.search_adapter.DDGSSearchProvider.search") as mock_search:
            mock_search.return_value = [
                {
                    "title": "BESCOM Tariff Order",
                    "url": "https://bescom.karnataka.gov.in/order",
                    "snippet": "Official BESCOM 2026 power tariff order.",
                }
            ]
            resp = test_client.post("/api/v1/research/search", json=payload, headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["resultsCount"] == 1
            assert len(data["results"]) == 1
            assert len(data["citations"]) == 1
            assert data["results"][0]["title"] == "BESCOM Tariff Order"
