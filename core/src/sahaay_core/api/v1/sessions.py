"""Session and Consent Management Endpoints."""

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.contracts.models import ConsentGrant, Session

router = APIRouter(prefix="/sessions", tags=["Sessions & Consent"])

# In-memory stores for fast testing & routing (backed by persistence layer)
active_sessions: dict[UUID, Session] = {}
active_grants: dict[UUID, list[ConsentGrant]] = {}


class CreateSessionRequest(BaseModel):
    localOnlyMode: bool = True
    metadata: Optional[dict] = None


class CreateGrantRequest(BaseModel):
    scope: str
    purpose: str
    targetDomainOrPath: Optional[str] = None


@router.post("", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session(req: CreateSessionRequest) -> Session:
    """Create a new Sahaay session."""
    session = Session(
        sessionId=uuid4(),
        localOnlyMode=req.localOnlyMode,
        metadata=req.metadata or {},
    )
    active_sessions[session.sessionId] = session
    active_grants[session.sessionId] = []
    return session


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: UUID) -> Session:
    """Fetch session details."""
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post(
    "/{session_id}/grants", response_model=ConsentGrant, status_code=status.HTTP_201_CREATED
)
async def grant_consent(session_id: UUID, req: CreateGrantRequest) -> ConsentGrant:
    """Grant explicit user consent within session."""
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    grant = ConsentGrant(
        grantId=uuid4(),
        sessionId=session_id,
        scope=req.scope,
        purpose=req.purpose,
        targetDomainOrPath=req.targetDomainOrPath,
    )
    active_grants[session_id].append(grant)
    return grant


@router.get("/{session_id}/grants", response_model=List[ConsentGrant])
async def list_grants(session_id: UUID) -> List[ConsentGrant]:
    """List all consent grants for a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return active_grants.get(session_id, [])
