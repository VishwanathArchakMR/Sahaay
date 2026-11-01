"""Session and Consent Management Endpoints."""

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.contracts.consent_purposes import (
    ALL_META_CLOUD_PURPOSES,
    META_API_DESTINATION,
    MetaCloudConsentPurpose,
)
from sahaay_core.contracts.models import ConsentGrant, Session
from sahaay_core.storage.persistence import durable_storage

router = APIRouter(prefix="/sessions", tags=["Sessions & Consent"])

# Fast cache backed by SQLite durable persistence
active_sessions: dict[UUID, Session] = {}
active_grants: dict[UUID, list[ConsentGrant]] = {}


class CreateSessionRequest(BaseModel):
    localOnlyMode: bool = False
    autoAuthorizeMetaCloud: bool = True
    metadata: Optional[dict] = None


class CreateGrantRequest(BaseModel):
    scope: Optional[str] = None
    purpose: Optional[str] = None
    targetDomainOrPath: Optional[str] = None
    capability: Optional[str] = None
    justification: Optional[str] = None


def _apply_meta_cloud_grants(session_id: UUID) -> List[ConsentGrant]:
    """Helper to provision canonical Meta Cloud consent grants for a session."""
    grants = []
    if session_id not in active_grants:
        active_grants[session_id] = []

    existing_purposes = {g.purpose for g in active_grants[session_id] if not g.isRevoked}

    for p in ALL_META_CLOUD_PURPOSES:
        if p not in existing_purposes:
            grant = ConsentGrant(
                grantId=uuid4(),
                sessionId=session_id,
                scope="meta_cloud",
                purpose=p,
                targetDomainOrPath=META_API_DESTINATION,
            )
            durable_storage.save_consent_grant(grant)
            active_grants[session_id].append(grant)
            grants.append(grant)
    return grants


@router.post("", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session(req: CreateSessionRequest) -> Session:
    """Create a new Sahaay session and persist it durably."""
    session = Session(
        sessionId=uuid4(),
        localOnlyMode=req.localOnlyMode,
        metadata=req.metadata or {},
    )
    durable_storage.save_session(session)
    active_sessions[session.sessionId] = session
    active_grants[session.sessionId] = []

    if not req.localOnlyMode and req.autoAuthorizeMetaCloud:
        _apply_meta_cloud_grants(session.sessionId)

    return session


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: UUID) -> Session:
    """Fetch session details from cache or durable persistence."""
    session = active_sessions.get(session_id)
    if not session:
        session = durable_storage.get_session(session_id)
        if session:
            active_sessions[session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post(
    "/{session_id}/grants", response_model=ConsentGrant, status_code=status.HTTP_201_CREATED
)
async def grant_consent(session_id: UUID, req: CreateGrantRequest) -> ConsentGrant:
    # Verify session exists
    await get_session(session_id)

    scope = req.scope or req.capability or "general"
    purpose = req.purpose or req.justification or req.capability or "task_planning"
    target = req.targetDomainOrPath or META_API_DESTINATION

    grant = ConsentGrant(
        grantId=uuid4(),
        sessionId=session_id,
        scope=scope,
        purpose=purpose,
        targetDomainOrPath=target,
    )
    durable_storage.save_consent_grant(grant)
    if session_id not in active_grants:
        active_grants[session_id] = []
    active_grants[session_id].append(grant)
    return grant


@router.post(
    "/{session_id}/onboarding-consent",
    response_model=List[ConsentGrant],
    status_code=status.HTTP_201_CREATED,
)
async def grant_onboarding_consent(session_id: UUID) -> List[ConsentGrant]:
    """One-time authorization granting all canonical Meta Cloud processing purposes."""
    await get_session(session_id)
    return _apply_meta_cloud_grants(session_id)


@router.get("/{session_id}/grants", response_model=List[ConsentGrant])
async def list_grants(session_id: UUID) -> List[ConsentGrant]:
    """List all consent grants for a session from durable storage."""
    await get_session(session_id)  # Throws 404 if session doesn't exist
    grants = durable_storage.get_consent_grants_for_session(session_id)
    active_grants[session_id] = grants
    return grants


class SessionManager:
    """Helper wrapper for programmatic session and consent management."""

    @staticmethod
    def create_session(local_only_mode: bool = True, metadata: Optional[dict] = None) -> Session:
        session = Session(
            sessionId=uuid4(),
            localOnlyMode=local_only_mode,
            metadata=metadata or {},
        )
        durable_storage.save_session(session)
        active_sessions[session.sessionId] = session
        active_grants[session.sessionId] = []
        return session

    @staticmethod
    def get_session(session_id: UUID) -> Optional[Session]:
        session = active_sessions.get(session_id)
        if not session:
            session = durable_storage.get_session(session_id)
            if session:
                active_sessions[session_id] = session
        return session

    @staticmethod
    def grant_consent(
        session_id: UUID,
        scope: str,
        purpose: str,
        target_domain_or_path: Optional[str] = None,
    ) -> ConsentGrant:
        grant = ConsentGrant(
            grantId=uuid4(),
            sessionId=session_id,
            scope=scope,
            purpose=purpose,
            targetDomainOrPath=target_domain_or_path,
        )
        durable_storage.save_consent_grant(grant)
        if session_id not in active_grants:
            active_grants[session_id] = []
        active_grants[session_id].append(grant)
        return grant

    @staticmethod
    def list_consent_grants(session_id: UUID) -> List[ConsentGrant]:
        grants = durable_storage.get_consent_grants_for_session(session_id)
        active_grants[session_id] = grants
        return grants


session_manager = SessionManager()
