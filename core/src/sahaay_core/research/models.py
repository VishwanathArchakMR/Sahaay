"""Internet Research Models and Contracts."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class SearchResult(BaseModel):
    """Normalized search result metadata with source provenance."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    result_id: str = Field(default_factory=lambda: f"res-{uuid4().hex[:8]}")
    title: str
    url: str
    snippet: str
    provider: str = "ddgs_keyless"
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_id: Optional[str] = None
    sha256: Optional[str] = None


class Citation(BaseModel):
    """Citation linking a claim or extracted statement to a verified research source."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    citation_id: str = Field(default_factory=lambda: f"cite-{uuid4().hex[:8]}")
    statement: str
    source_id: str
    url: str
    title: str
    retrieved_at: str
    confidence_score: float = 1.0


class PageFetchResult(BaseModel):
    """Outcome of a safe web page fetch operation."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    url: str
    title: str
    content_type: str
    extracted_text: str
    sha256: str
    byte_count: int
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_id: Optional[str] = None
    sanitized: bool = True


class ResearchSearchResponse(BaseModel):
    """Structured response from an internet research search."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    research_id: str = Field(default_factory=lambda: f"rsch-{uuid4().hex[:8]}")
    query: str
    provider: str
    results_count: int
    results: List[SearchResult]
    citations: List[Citation]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "COMPLETED"  # COMPLETED | UNAVAILABLE | RATE_LIMITED | LOCAL_ONLY_BLOCKED
    notice: Optional[str] = None
