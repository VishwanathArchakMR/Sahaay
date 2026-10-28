"""Internet Research API Endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from sahaay_core.api.v1.sources import context_store, source_manager
from sahaay_core.research.models import PageFetchResult, ResearchSearchResponse
from sahaay_core.research.safe_fetcher import SSRFValidationError, safe_web_fetcher
from sahaay_core.research.search_adapter import internet_research_manager

router = APIRouter(prefix="/research", tags=["Internet Research"])


class ResearchSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Search query string")
    sessionId: Optional[UUID] = None
    maxResults: int = Field(default=5, ge=1, le=20)


class PageFetchRequest(BaseModel):
    url: str = Field(..., description="Public HTTP/HTTPS URL to fetch")
    sessionId: Optional[UUID] = None


@router.post("/search", response_model=ResearchSearchResponse, status_code=status.HTTP_200_OK)
async def search_internet(req: ResearchSearchRequest) -> ResearchSearchResponse:
    """Execute public internet search using keyless search provider with citation generation."""
    response = await internet_research_manager.search_and_cite(
        query=req.query,
        session_id=req.sessionId,
        max_results=req.maxResults,
        source_manager=source_manager,
        context_store=context_store,
    )
    return response


@router.post("/fetch", response_model=PageFetchResult, status_code=status.HTTP_200_OK)
async def fetch_web_page(req: PageFetchRequest) -> PageFetchResult:
    """Safely fetch and sanitize a public web page with strict SSRF defense."""
    try:
        result = await safe_web_fetcher.fetch_page(req.url)

        # Register in source manager
        source_ref = source_manager.register_source(
            source_type="public_web_page",
            uri=req.url,
            title=result.title,
            checksum=result.sha256,
            metadata={"byteCount": result.byte_count, "contentType": result.content_type},
        )
        result.source_id = str(source_ref.sourceId)
        return result
    except SSRFValidationError as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Security Violation: {ssrf_err}",
        ) from ssrf_err
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve web page: {exc}",
        ) from exc
