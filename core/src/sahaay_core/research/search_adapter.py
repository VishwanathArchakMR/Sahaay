"""Keyless Internet Research Search Adapter for Sahaay.

Coordinates public search query submission, result normalization, citation generation,
provenance tracking, and durable SQLite logging without requiring paid AI credentials.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.config.settings import settings
from sahaay_core.contracts.models import FactTypeEnum
from sahaay_core.privacy.privacy_gateway import PrivacyGateway
from sahaay_core.research.models import Citation, ResearchSearchResponse, SearchResult
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger(__name__)


class SearchProviderInterface(ABC):
    """Interface for search query providers."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Submit query and return normalized raw result dictionaries."""
        pass


class DDGSSearchProvider(SearchProviderInterface):
    """Keyless public search provider using the ddgs library."""

    def __init__(self) -> None:
        self.provider_name = "ddgs_keyless"

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        try:
            from ddgs import DDGS

            results = []
            with DDGS(timeout=settings.web_fetch_timeout_seconds) as ddgs_client:
                raw_results = list(ddgs_client.text(query, max_results=max_results))
                for item in raw_results:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("href", ""),
                            "snippet": item.get("body", ""),
                        }
                    )
            return results
        except Exception as exc:
            logger.warning("DDGS keyless search provider error: %s", exc)
            raise


class MockSearchProvider(SearchProviderInterface):
    """Deterministic fixture provider for unit and integration testing."""

    def __init__(self, predefined_results: Optional[List[Dict[str, Any]]] = None) -> None:
        self.predefined_results = predefined_results or [
            {
                "title": "BESCOM Electricity Tariff Rates 2026 - Official Notification",
                "url": "https://kerc.karnataka.gov.in/tariff_orders/bescom_2026.html",
                "snippet": "Karnataka Electricity Regulatory Commission approved BESCOM retail tariff of INR 4.75 per unit for domestic consumers in 2026.",
            },
            {
                "title": "Bangalore Water Supply and Sewerage Board (BWSSB) Payment Portal",
                "url": "https://bwssb.karnataka.gov.in/portal/pay",
                "snippet": "Official portal for online utility payment and bill status lookup across Bengaluru urban divisions.",
            },
        ]

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        return self.predefined_results[:max_results]


class InternetResearchManager:
    """Manages public internet research, result validation, provenance, and citations."""

    def __init__(
        self,
        provider: Optional[SearchProviderInterface] = None,
        privacy_gateway: Optional[PrivacyGateway] = None,
    ) -> None:
        self.provider = provider or DDGSSearchProvider()
        self.privacy_gateway = privacy_gateway or PrivacyGateway()

    async def search_and_cite(
        self,
        query: str,
        session_id: Optional[UUID] = None,
        max_results: int = 5,
        source_manager: Optional[Any] = None,
        context_store: Optional[Any] = None,
    ) -> ResearchSearchResponse:
        """Executes search, registers sources and facts, generates citations, and stores durable records."""
        research_id = f"rsch-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        # 1. Local-Only Mode / Privacy Check
        if settings.local_only_mode:
            logger.info("Internet research blocked: system is in localOnlyMode.")
            return ResearchSearchResponse(
                researchId=research_id,
                query=query,
                provider="local_policy_gate",
                resultsCount=0,
                results=[],
                citations=[],
                status="LOCAL_ONLY_BLOCKED",
                notice="Internet research is prohibited while Sahaay is running in local-only mode. Provide consent to enable outbound public research.",
            )

        # 2. Query Provider
        raw_results: List[Dict[str, Any]] = []
        try:
            raw_results = self.provider.search(query=query, max_results=max_results)
        except Exception as exc:
            logger.warning("Research provider unavailable: %s", exc)
            return ResearchSearchResponse(
                researchId=research_id,
                query=query,
                provider="keyless_metasearch",
                resultsCount=0,
                results=[],
                citations=[],
                status="UNAVAILABLE",
                notice=f"Keyless search provider is temporarily unavailable ({type(exc).__name__}). No fabricated search results returned.",
            )

        # 3. Normalize Results & Link Provenance
        results: List[SearchResult] = []
        citations: List[Citation] = []

        for item in raw_results:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            snippet = item.get("snippet", "").strip()

            if not url or not title:
                continue

            content_fingerprint = hashlib.sha256(snippet.encode("utf-8")).hexdigest()
            source_id = f"src-{uuid4().hex[:8]}"

            # Register with source manager if available
            if source_manager:
                try:
                    s_ref = source_manager.register_source(
                        source_type="internet_research",
                        uri=url,
                        title=title,
                        checksum=content_fingerprint,
                        metadata={"query": query, "snippet": snippet},
                    )
                    source_id = str(s_ref.sourceId)
                except Exception as ex:
                    logger.debug("Could not register source in SourceManager: %s", ex)

            # Record grounded fact in ContextStore if available
            if context_store and source_manager:
                try:
                    context_store.record_fact(
                        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                        content=snippet,
                        source_reference_id=UUID(source_id) if len(source_id) == 36 else uuid4(),
                        metadata={"url": url, "title": title},
                    )
                except Exception as ex:
                    logger.debug("Could not record fact in ContextStore: %s", ex)

            res = SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                provider="ddgs_keyless",
                retrievedAt=now,
                sourceId=source_id,
                sha256=content_fingerprint,
            )
            results.append(res)

            # Build Citation linking source to statement
            citations.append(
                Citation(
                    statement=snippet[:200],
                    sourceId=source_id,
                    url=url,
                    title=title,
                    retrievedAt=now,
                    confidenceScore=0.9,
                )
            )

        # 4. Save to Durable SQLite Persistence
        try:
            durable_storage.save_web_research(
                research_id=research_id,
                query=query,
                provider="ddgs_keyless",
                results=[r.model_dump(by_alias=True) for r in results],
                citations=[c.model_dump(by_alias=True) for c in citations],
            )
        except Exception as exc:
            logger.warning("Could not persist web research audit record: %s", exc)

        return ResearchSearchResponse(
            researchId=research_id,
            query=query,
            provider="ddgs_keyless",
            resultsCount=len(results),
            results=results,
            citations=citations,
            timestamp=now,
            status="COMPLETED",
            notice="Search snippets provide clues and citations. Primary documents can be safely retrieved via safe_fetch_page.",
        )


# Global research manager singleton
internet_research_manager = InternetResearchManager()
