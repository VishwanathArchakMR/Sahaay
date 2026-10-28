"""Internet Research Subsystem for Sahaay."""

from sahaay_core.research.citations import CitationEngine
from sahaay_core.research.models import (
    Citation,
    PageFetchResult,
    ResearchSearchResponse,
    SearchResult,
)
from sahaay_core.research.safe_fetcher import SafeWebFetcher, SSRFValidationError, safe_web_fetcher
from sahaay_core.research.search_adapter import (
    DDGSSearchProvider,
    InternetResearchManager,
    MockSearchProvider,
    SearchProviderInterface,
    internet_research_manager,
)

__all__ = [
    "SearchResult",
    "Citation",
    "PageFetchResult",
    "ResearchSearchResponse",
    "SafeWebFetcher",
    "SSRFValidationError",
    "safe_web_fetcher",
    "SearchProviderInterface",
    "DDGSSearchProvider",
    "MockSearchProvider",
    "InternetResearchManager",
    "internet_research_manager",
    "CitationEngine",
]
