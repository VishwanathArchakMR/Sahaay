"""Session and Consent Management Endpoints."""

import json
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from sahaay_core.config.settings import settings
from sahaay_core.contracts.consent_purposes import (
    ALL_META_CLOUD_PURPOSES,
    LOCAL_AUTOMATION_SCOPES,
    META_API_DESTINATION,
)
from sahaay_core.contracts.models import ConsentGrant, Session
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger(__name__)

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


class OnboardingConsentRequest(BaseModel):
    accepted: bool = True
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


def _apply_onboarding_grants(session_id: UUID) -> List[ConsentGrant]:
    """Helper to provision both Meta Cloud and local automation consent grants upon user onboarding."""
    _apply_meta_cloud_grants(session_id)

    existing_scopes = {g.scope for g in active_grants[session_id] if not g.isRevoked}
    for s in LOCAL_AUTOMATION_SCOPES:
        if s not in existing_scopes:
            grant = ConsentGrant(
                grantId=uuid4(),
                sessionId=session_id,
                scope=s,
                purpose=s,
                targetDomainOrPath="local",
            )
            durable_storage.save_consent_grant(grant)
            active_grants[session_id].append(grant)

    return [g for g in active_grants[session_id] if not g.isRevoked]


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

    if req.autoAuthorizeMetaCloud and not req.localOnlyMode:
        _apply_onboarding_grants(session.sessionId)
    else:
        # In local-only mode, provision local computer automation grants
        existing_scopes = {g.scope for g in active_grants[session.sessionId] if not g.isRevoked}
        for s in LOCAL_AUTOMATION_SCOPES:
            if s not in existing_scopes:
                grant = ConsentGrant(
                    grantId=uuid4(),
                    sessionId=session.sessionId,
                    scope=s,
                    purpose=s,
                    targetDomainOrPath="local",
                )
                durable_storage.save_consent_grant(grant)
                active_grants[session.sessionId].append(grant)

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

    # Ensure persisted grants are synchronized into active_grants
    grants = durable_storage.get_consent_grants_for_session(session_id)
    if not grants:
        grants = active_grants.get(session_id, [])
    active_grants[session_id] = grants
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
async def grant_onboarding_consent(
    session_id: UUID, req: Optional[OnboardingConsentRequest] = None
) -> List[ConsentGrant]:
    """One-time authorization granting all canonical Meta Cloud processing and local automation purposes."""
    await get_session(session_id)
    return _apply_onboarding_grants(session_id)


@router.get("/active/latest", response_model=Session)
async def get_latest_active_session() -> Session:
    """Returns the most recent active session for cross-surface sync."""
    from sahaay_core.storage.persistence import get_sqlite_conn

    conn = get_sqlite_conn()
    row = conn.execute(
        "SELECT * FROM sessions WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        sess = Session(
            sessionId=UUID(row["session_id"]),
            createdAt=datetime.fromisoformat(row["created_at"]),
            expiresAt=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            isActive=bool(row["is_active"]),
            localOnlyMode=bool(row["local_only_mode"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
        active_sessions[sess.sessionId] = sess
        return sess

    # Fallback create session
    sess = Session(localOnlyMode=settings.local_only_mode)
    durable_storage.save_session(sess)
    _apply_meta_cloud_grants(sess.sessionId)
    active_sessions[sess.sessionId] = sess
    return sess


@router.get("/{session_id}/messages")
async def list_conversation_messages(session_id: UUID, limit: int = 100) -> List[dict]:
    """Retrieve chronologically ordered shared conversation messages for this session."""
    return durable_storage.list_conversation_messages(str(session_id), limit=limit)


class PostMessageRequest(BaseModel):
    role: str
    content: str
    taskId: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_conversation_message(session_id: UUID, req: PostMessageRequest) -> dict:
    """Post a user or assistant message to the shared conversation transcript."""
    return durable_storage.save_conversation_message(
        session_id=str(session_id),
        role=req.role,
        content=req.content,
        task_id=req.taskId,
        metadata=req.metadata,
    )


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


@router.post("/{session_id}/chat")
async def chat_with_assistant(session_id: UUID, req: ChatRequest) -> dict:
    """Conversational ChatGPT-style Help assistant.
    Answers user questions directly using Meta Muse Spark with conversation history,
    without creating task executions, DAGs, or background automation steps.
    """
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 1. Save user message to durable conversation storage
    durable_storage.save_conversation_message(
        session_id=str(session_id),
        role="user",
        content=user_text,
    )

    # 2. Retrieve recent conversation history for conversational context
    history_records = durable_storage.list_conversation_messages(str(session_id), limit=10)
    messages_payload = [
        {
            "role": "system",
            "content": (
                "You are Sahaay Help, a conversational, helpful, privacy-preserving Windows AI assistant. "
                "You answer user questions, explain concepts, provide clear step-by-step guidance, and clarify system capabilities. "
                "Communicate naturally and directly in clean markdown. Do not generate code tool calls or task JSON structures."
            ),
        }
    ]
    for r in history_records[-6:]:
        messages_payload.append(
            {
                "role": r.get("role", "user"),
                "content": r.get("content", ""),
            }
        )

    # 3. Request completion from Meta Muse Spark model
    reply_text = ""
    try:
        from sahaay_core.models.meta_client import muse_spark

        if muse_spark.client.is_configured:
            resp = await muse_spark.client.post_endpoint(
                "chat/completions",
                {
                    "model": muse_spark.model_id,
                    "messages": messages_payload,
                    "temperature": 0.4,
                    "max_tokens": 800,
                },
            )
            choices = resp.data.get("choices", [])
            if choices:
                reply_text = choices[0].get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("Meta Muse Spark chat call failed, utilizing local guide: %s", exc)

    if not reply_text:
        # Conversational fallback guide
        reply_text = (
            f"I'm here to help with your computer, software, and browser queries. "
            f"Regarding '{user_text}':\n\n"
            f"If you'd like me to perform this action directly on your computer (open apps, browse sites, type text, or inspect files), "
            f"switch to the **Automate** tab at the top and click Execute! "
            f"In **Help** mode, feel free to ask questions about Windows shortcuts, browser navigation, or application features."
        )

    # 4. Save assistant reply to durable storage
    saved_msg = durable_storage.save_conversation_message(
        session_id=str(session_id),
        role="assistant",
        content=reply_text,
    )

    return {
        "reply": reply_text,
        "sessionId": str(session_id),
        "role": "assistant",
        "messageId": saved_msg.get("messageId"),
        "createdAt": saved_msg.get("createdAt"),
    }


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
        if session:
            grants = durable_storage.get_consent_grants_for_session(session_id)
            if not grants:
                grants = active_grants.get(session_id, [])
            active_grants[session_id] = grants
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
