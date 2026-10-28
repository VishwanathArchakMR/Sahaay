"""Sources and Context Retrieval Endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import ContextFact, FactTypeEnum, SourceReference
from sahaay_core.retrieval.retriever import ScopedRetriever
from sahaay_core.sources.document_ingestion import (
    DocumentIngestionError,
    DocumentIngestionService,
)
from sahaay_core.sources.manager import SourceManager

router = APIRouter(prefix="/sources", tags=["Sources & Retrieval"])

source_manager = SourceManager()
context_store = ContextStore()
scoped_retriever = ScopedRetriever(source_manager=source_manager, context_store=context_store)
doc_ingestion_service = DocumentIngestionService(
    source_manager=source_manager,
    context_store=context_store,
)


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


class IngestFileRequest(BaseModel):
    filePath: str
    customTitle: Optional[str] = None
    taskId: Optional[UUID] = None


@router.post("/ingest", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@router.post("/ingest-file", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def ingest_file(req: IngestFileRequest) -> Dict[str, Any]:
    """Ingest user-authorized local file (txt, md, json, csv, pdf) and record structured facts."""
    try:
        return doc_ingestion_service.ingest_file(
            file_path_str=req.filePath,
            custom_title=req.customTitle,
            task_id=req.taskId,
        )
    except DocumentIngestionError as die:
        raise HTTPException(status_code=400, detail=str(die)) from die
    except Exception as ex:
        raise HTTPException(
            status_code=500, detail=f"Unexpected error ingesting file: {str(ex)}"
        ) from ex


class SearchSourcesRequest(BaseModel):
    query: str
    sourceType: Optional[str] = None
    sourceId: Optional[UUID] = None


@router.post("/search")
async def search_sources(req: SearchSourcesRequest) -> Dict[str, Any]:
    """Perform deterministic local text search over permitted sources without AI models.

    Returns source-linked excerpts, timestamps, confidence metrics, and location metadata.
    """
    query_lower = req.query.strip().lower()
    if not query_lower:
        return {
            "query": req.query,
            "results": [],
            "count": 0,
            "isModelInference": False,
            "notice": "Empty query provided.",
        }

    results = []
    active_sources = source_manager.list_active_sources()

    for src in active_sources:
        if req.sourceType and src.sourceType != req.sourceType:
            continue
        if req.sourceId and src.sourceId != req.sourceId:
            continue

        facts = context_store.get_facts_for_source(src.sourceId)
        for f in facts:
            content_lower = f.content.lower()
            idx = content_lower.find(query_lower)
            if idx != -1:
                # Extract surrounding window (80 chars before & 120 chars after)
                start = max(0, idx - 80)
                end = min(len(f.content), idx + len(query_lower) + 120)
                snippet = f.content[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(f.content):
                    snippet = snippet + "..."

                # Classify source representation
                source_kind = "source_text"
                if f.factType == FactTypeEnum.NORMALIZED:
                    source_kind = "normalized"
                elif f.factType in (FactTypeEnum.INFERRED, FactTypeEnum.UNCERTAIN):
                    source_kind = "application_description"

                page_num = f.metadata.get("pageNumber")
                char_offset = f.metadata.get("charOffset", idx)

                results.append(
                    {
                        "factId": str(f.factId),
                        "factType": f.factType.value,
                        "content": snippet,
                        "sourceKind": source_kind,
                        "sourceId": str(src.sourceId),
                        "sourceType": src.sourceType,
                        "sourceUri": src.uri,
                        "sourceTitle": src.title or src.uri,
                        "observedAt": src.observedAt.isoformat(),
                        "matchedSnippet": snippet,
                        "matchLocation": f"page {page_num}"
                        if page_num
                        else f"offset {char_offset}",
                        "confidenceScore": f.confidenceScore,
                        "isUntrustedContent": f.metadata.get("isUntrusted", True),
                    }
                )

    notice = None
    if len(results) == 0:
        notice = (
            "Deterministic keyword search found 0 exact matches. "
            "Natural-language synthesis, semantic inference, and conceptual queries are deferred to Milestone 04 (Meta model integration)."
        )

    return {
        "query": req.query,
        "results": results,
        "count": len(results),
        "isModelInference": False,
        "notice": notice,
    }
