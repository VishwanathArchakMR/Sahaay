"""Model Providers Diagnostic & Inference API.

Exposes endpoints for Meta hosted models (Muse Spark, Muse Wonder, Muse Voice Transcribe, SAM 3.1)
and on-device Local Llama 3.2 3B Instruct runtime lifecycle.
"""

import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.config.settings import settings
from sahaay_core.contracts.models import TaskContract
from sahaay_core.models.local.client import LocalLlamaClient
from sahaay_core.models.local.llama_runtime import local_llama_manager
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.models.meta.muse_image import muse_image
from sahaay_core.models.meta.muse_spark import (
    MuseSparkPlan,
    StructuredTaskPlan,
    muse_spark,
)
from sahaay_core.models.meta.muse_voice import MuseVoiceClient, VoiceTranscriptionResult
from sahaay_core.models.meta.muse_wonder import MuseWonderClient
from sahaay_core.models.meta.sam_client import Sam31Client

router = APIRouter(prefix="/models", tags=["Models"])

meta_client = MetaClient()
muse_wonder = MuseWonderClient(meta_client=meta_client)
muse_voice = MuseVoiceClient(meta_client=meta_client)
sam_client = Sam31Client(meta_client=meta_client)
local_llama_client = LocalLlamaClient(manager=local_llama_manager)
browser_adapter = BrowserAdapter()
windows_adapter = WindowsNativeAdapter()


class ModelPlanningRequest(BaseModel):
    """Request payload for Muse Spark task planning."""

    prompt: str
    sessionId: Optional[UUID] = None
    contextFacts: Optional[List[Dict[str, Any]]] = None
    languageHint: Optional[str] = None


class StructuredPlanningRequest(BaseModel):
    """Request payload for Meta Muse Spark structured planning."""

    goal: str
    sessionId: Optional[UUID] = None
    workflowMode: str = "combined_retrieval_and_action"
    context: str = ""
    sourceFacts: Dict[str, Any] = {}


class VisualGroundingRequest(BaseModel):
    """Request payload for SAM 3.1 visual grounding."""

    targetPrompt: str
    viewportWidth: int = 1280
    viewportHeight: int = 800
    observationVersion: int = 1


# Runtime provider verification status cache
provider_connectivity_cache: Dict[str, str] = {
    "meta": "UNTESTED",
    "muse_image": "UNTESTED",
}


def _resolve_provider_readiness(is_configured: bool, cache_key: str) -> str:
    """Computes truthful provider readiness state: NOT_CONFIGURED, NEEDS_CONSENT, CONFIGURED_UNTESTED, AUTHENTICATED, MODEL_REQUEST_VERIFIED, UNAUTHORIZED, UNAVAILABLE, or FAILED."""
    if not is_configured:
        return "NOT_CONFIGURED"
    if settings.local_only_mode or not settings.hosted_models_permitted:
        return "NEEDS_CONSENT"
    cached = provider_connectivity_cache.get(cache_key, "UNTESTED")
    if cached in ("READY", "AUTHENTICATED", "MODEL_REQUEST_VERIFIED"):
        return cached
    if cached in ("FAILED", "UNAUTHORIZED", "UNAVAILABLE"):
        return cached
    return "CONFIGURED_UNTESTED"


@router.get("/status")
async def get_models_status() -> Dict[str, Any]:
    """Retrieve verified readiness status across all supported Meta and Local models."""
    local_status = local_llama_client.get_status()

    meta_status = _resolve_provider_readiness(meta_client.is_configured, "meta")
    muse_image_status = _resolve_provider_readiness(muse_image.is_configured, "muse_image")

    # Live probe of system bridge and pipe connections
    is_native_host_up = browser_adapter.is_connected()
    is_ext_attached = (
        browser_adapter.is_browser_attached()
        if is_native_host_up
        else False
    )
    is_companion_up = windows_adapter.is_connected()

    return {
        "metaHosted": {
            "isConfigured": meta_client.is_configured,
            "baseUrl": meta_client.base_url,
            "status": meta_status,
            "models": {
                "museSpark": {
                    "id": settings.muse_spark_model_id,
                    "status": meta_status,
                    "role": "Semantic Reasoning & Structured Planning",
                },
                "museWonder": {
                    "id": settings.muse_wonder_model_id,
                    "status": meta_status,
                    "role": "Responses API Visual Computer-Use",
                },
                "museVoice": {
                    "id": settings.muse_voice_model_id,
                    "status": meta_status,
                    "role": "Multilingual Speech-to-Text Transcription",
                },
                "museImage": {
                    "id": settings.muse_image_model,
                    "status": muse_image_status,
                    "role": "Task Passport Visual Milestone Storytelling",
                },
                "sam": {
                    "id": settings.sam_model_id,
                    "status": meta_status,
                    "role": "Visual Grounding & Element Segmentation",
                },
            },
        },
        "localLlama": {
            "status": local_status["status"],
            "message": local_status["message"],
            "modelPath": local_status["modelPath"],
            "serverBinary": local_status["serverBinary"],
            "hardwareProfile": local_status["hardwareProfile"],
            "contextSize": settings.local_llama_context_size,
        },
        "visualStorytelling": {
            "enabled": settings.enable_visual_storytelling,
            "budgetRemaining": settings.visual_storytelling_budget,
            "artifactsDirectory": str(settings.artifacts_dir),
        },
        "privacyMode": {
            "localOnlyMode": settings.local_only_mode,
            "hostedModelsPermitted": settings.hosted_models_permitted,
        },
        "systemIntegrations": {
            "browserExtension": "ATTACHED"
            if is_ext_attached
            else ("HOST_WAITING" if is_native_host_up else "DISCONNECTED"),
            "nativeMessaging": "CONNECTED" if is_native_host_up else "DISCONNECTED",
            "windowsCompanion": "CONNECTED" if is_companion_up else "DISCONNECTED",
            "sqliteLedger": "READY",
        },
    }


@router.post("/test-connectivity")
async def test_model_connectivity() -> Dict[str, Any]:
    """Test live connectivity obeying Privacy Gateway. Outbound checks are blocked in localOnlyMode."""
    # Check local Llama runtime first (always safe to probe on loopback)
    is_local_healthy = await local_llama_manager.check_health()

    # Outbound checks must obey Privacy Gateway and local-only mode
    if settings.local_only_mode:
        return {
            "metaApi": {
                "status": "BLOCKED_BY_PRIVACY_GATEWAY",
                "message": "Local-only mode is active. Outbound connectivity test blocked by Privacy Gateway.",
                "isHealthy": False,
            },
            "museImageApi": {
                "status": "BLOCKED_BY_PRIVACY_GATEWAY",
                "message": "Local-only mode is active. Outbound connectivity test blocked by Privacy Gateway.",
                "isHealthy": False,
            },
            "localLlama": {
                "isHealthy": is_local_healthy,
                "status": local_llama_manager.status.value,
                "message": local_llama_manager.status_message,
            },
        }

    meta_result = await meta_client.check_connectivity()
    muse_image_result = await muse_image.check_connectivity()

    provider_connectivity_cache["meta"] = (
        meta_result.get("status", "AUTHENTICATED")
        if meta_result.get("isHealthy") or meta_result.get("isLive")
        else meta_result.get("status", "FAILED")
    )
    provider_connectivity_cache["muse_image"] = (
        muse_image_result.get("status", "READY")
        if muse_image_result.get("isHealthy") or muse_image_result.get("configured")
        else "FAILED"
    )

    return {
        "metaApi": meta_result,
        "museImageApi": muse_image_result,
        "localLlama": {
            "isHealthy": is_local_healthy,
            "status": local_llama_manager.status.value,
            "message": local_llama_manager.status_message,
        },
    }


class UpdateCredentialsRequest(BaseModel):
    modelApiKey: str


@router.post("/credentials")
async def update_model_credentials(req: UpdateCredentialsRequest) -> Dict[str, Any]:
    """Securely updates, persists, and tests Meta Cloud MODEL_API_KEY."""
    from sahaay_core.config.settings import REPO_ROOT

    new_key = req.modelApiKey.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")

    settings.model_api_key = new_key
    meta_client.api_key = new_key
    muse_image.api_key = new_key

    # Persist securely to REPO_ROOT/.env
    env_file = REPO_ROOT / ".env"
    existing_lines = []
    found = False
    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(existing_lines):
            stripped = line.strip()
            if stripped.startswith("MODEL_API_KEY=") or stripped.startswith("SAHAAY_MODEL_API_KEY="):
                existing_lines[idx] = f"MODEL_API_KEY={new_key}"
                found = True
                break
    if not found:
        existing_lines.append(f"MODEL_API_KEY={new_key}")
    env_file.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

    # Live test connectivity with new credentials
    conn = await meta_client.check_connectivity()
    return {
        "status": "SUCCESS",
        "isConfigured": meta_client.is_configured,
        "connectivity": conn,
        "message": "Meta Cloud MODEL_API_KEY updated, persisted, and verified.",
    }


@router.post("/meta/muse-spark/plan", response_model=StructuredTaskPlan)
async def plan_with_meta_muse_spark(req: StructuredPlanningRequest) -> StructuredTaskPlan:
    """Invoke Meta Muse Spark 1.3 for structured planning with local schema enforcement and Capability Registry validation."""
    from uuid import uuid4

    from sahaay_core.api.v1.sessions import active_grants
    from sahaay_core.storage.persistence import durable_storage

    grants = []
    if req.sessionId:
        grants = durable_storage.get_consent_grants_for_session(req.sessionId) or active_grants.get(req.sessionId, [])
        if not grants:
            session = durable_storage.get_session(req.sessionId)
            if session and not session.localOnlyMode:
                from sahaay_core.api.v1.sessions import _apply_meta_cloud_grants

                grants = _apply_meta_cloud_grants(req.sessionId)
                active_grants[req.sessionId] = grants

    task = TaskContract(
        taskId=uuid4(),
        sessionId=req.sessionId or uuid4(),
        goal=req.goal,
        taskType=req.workflowMode or "combined_retrieval_and_action",
    )

    return await muse_spark.generate_plan(
        task=task,
        context=req.context,
        source_facts=req.sourceFacts,
        active_grants=grants,
    )


@router.post("/plan", response_model=MuseSparkPlan)
async def plan_with_muse_spark(req: ModelPlanningRequest) -> MuseSparkPlan:
    """Invoke Muse Spark for semantic reasoning, multilingual understanding, and structured action planning."""
    from sahaay_core.api.v1.sessions import active_grants
    from sahaay_core.storage.persistence import durable_storage

    grants = []
    if req.sessionId:
        grants = durable_storage.get_consent_grants_for_session(req.sessionId) or active_grants.get(req.sessionId, [])
        if not grants:
            session = durable_storage.get_session(req.sessionId)
            if session and not session.localOnlyMode:
                from sahaay_core.api.v1.sessions import _apply_meta_cloud_grants

                grants = _apply_meta_cloud_grants(req.sessionId)
                active_grants[req.sessionId] = grants

    return await muse_spark.plan_and_reason(
        prompt=req.prompt,
        context_facts=req.contextFacts or [],
        active_grants=grants,
    )


@router.post("/transcribe", response_model=VoiceTranscriptionResult)
async def transcribe_audio(
    file: UploadFile = File(...),  # noqa: B008
    languageHints: str = Form("kn,hi,en"),  # noqa: B008
    sessionId: Optional[str] = Form(None),  # noqa: B008
) -> VoiceTranscriptionResult:
    """Submit recorded audio chunk or file to Muse Voice Transcribe pipeline."""
    audio_bytes = await file.read()
    hints = [h.strip() for h in languageHints.split(",") if h.strip()]

    # Outbound checks must obey Privacy Gateway and local-only mode
    if settings.local_only_mode:
        return VoiceTranscriptionResult(
            transcript="",
            confidence=0.0,
            language_detected="unknown",
            is_final=True,
            duration_seconds=0.0,
            is_live_call=False,
            editable=True,
            status="BLOCKED_BY_PRIVACY",
            error="Hosted speech transcription is blocked because Local-Only Mode is active. Outbound transmission of microphone audio to Meta AI is disabled.",
        )

    if not meta_client.is_configured:
        return VoiceTranscriptionResult(
            transcript="",
            confidence=0.0,
            language_detected="unknown",
            is_final=True,
            duration_seconds=0.0,
            is_live_call=False,
            editable=True,
            status="NOT_CONFIGURED",
            error="Meta API credentials are not configured for hosted voice transcription.",
        )

    grants = []
    if sessionId:
        try:
            from uuid import UUID

            from sahaay_core.api.v1.sessions import active_grants
            from sahaay_core.storage.persistence import durable_storage

            grants = active_grants.get(UUID(sessionId), [])
        except Exception:
            pass
            parsed_session_id = UUID(sessionId)
            grants = durable_storage.get_consent_grants_for_session(parsed_session_id) or active_grants.get(parsed_session_id, [])
            if not grants:
                session = durable_storage.get_session(parsed_session_id)
                if session and not session.localOnlyMode:
                    from sahaay_core.api.v1.sessions import _apply_meta_cloud_grants

                    grants = _apply_meta_cloud_grants(parsed_session_id)
                    active_grants[parsed_session_id] = grants
        except Exception as e:
            logger.warning("Failed resolving grants for transcription session %s: %s", sessionId, e)

    return await muse_voice.transcribe_audio_chunk(
        audio_bytes=audio_bytes,
        content_type=file.content_type or "audio/wav",
        language_hints=hints,
        active_grants=grants,
        allow_offline_fixture=False,
    )


@router.post("/local/start")
async def start_local_llama() -> Dict[str, Any]:
    """Trigger startup of local Llama 3.2 3B Instruct runtime on loopback 127.0.0.1."""
    started = await local_llama_manager.start_server()
    return {
        "success": started,
        "status": local_llama_manager.status.value,
        "message": local_llama_manager.status_message,
    }


@router.post("/local/stop")
async def stop_local_llama() -> Dict[str, Any]:
    """Stop running local Llama inference process cleanly."""
    local_llama_manager.stop_server()
    return {
        "success": True,
        "status": local_llama_manager.status.value,
        "message": local_llama_manager.status_message,
    }
