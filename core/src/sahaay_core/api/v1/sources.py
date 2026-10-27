"""Sources and Context Retrieval Endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import ContextFact, FactTypeEnum, SourceReference
from sahaay_core.retrieval.retriever import ScopedRetriever
from sahaay_core.sources.manager import SourceManager

router = APIRouter(prefix="/sources", tags=["Sources & Retrieval"])

source_manager = SourceManager()
context_store = ContextStore()
scoped_retriever = ScopedRetriever(source_manager=source_manager, context_store=context_store)


class RegisterSourceRequest(BaseModel):
    sourceType: str
    uri: str
    title: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Optional[dict] = None


class RecordFactRequest(BaseModel):
    sourceReferenceId: UUID
    factType: FactTypeEnum
    content: str
    derivationIds: Optional[List[UUID]] = None
    confidenceScore: float = 1.0


class QueryContextRequest(BaseModel):
    query: str
    permittedSourceIds: Optional[List[UUID]] = None


@router.post("", response_model=SourceReference, status_code=status.HTTP_201_CREATED)
async def register_source(req: RegisterSourceRequest) -> SourceReference:
    """Register permitted source (file, browser tab, or window)."""
    return source_manager.register_source(
        source_type=req.sourceType,
        uri=req.uri,
        title=req.title,
        checksum=req.checksum,
        metadata=req.metadata,
    )


@router.get("", response_model=List[SourceReference])
async def list_sources() -> List[SourceReference]:
    """List active, non-revoked sources."""
    return source_manager.list_active_sources()


@router.delete("/{source_id}")
async def revoke_source(source_id: UUID) -> dict:
    """Revoke authorization for a source; all subsequent queries fail closed."""
    success = source_manager.revoke_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "revoked", "sourceId": str(source_id)}


@router.post("/facts", response_model=ContextFact, status_code=status.HTTP_201_CREATED)
async def record_fact(req: RecordFactRequest) -> ContextFact:
    """Record an extracted fact linked to a registered source."""
    if not source_manager.is_source_permitted(req.sourceReferenceId):
        raise HTTPException(status_code=403, detail="Source is revoked or unauthorized.")

    return context_store.record_fact(
        fact_type=req.factType,
        content=req.content,
        source_reference_id=req.sourceReferenceId,
        derivation_ids=req.derivationIds,
        confidence_score=req.confidenceScore,
    )


@router.post("/query", response_model=List[ContextFact])
async def query_context(req: QueryContextRequest) -> List[ContextFact]:
    """Retrieve facts within permitted authorization scope."""
    return scoped_retriever.retrieve_context_for_query(
        query=req.query,
        permitted_source_ids=req.permittedSourceIds,
    )
