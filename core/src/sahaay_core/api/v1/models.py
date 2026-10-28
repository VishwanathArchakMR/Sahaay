"""Model Providers Diagnostic & Inference API.

Exposes endpoints for Meta hosted models (Muse Spark, Muse Wonder, Muse Voice Transcribe, SAM 3.1)
and on-device Local Llama 3.2 3B Instruct runtime lifecycle.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from sahaay_core.config.settings import settings
from sahaay_core.contracts.models import TaskContract
from sahaay_core.models.baseten.baseten_client import BasetenClient
from sahaay_core.models.baseten.muse_spark_open import StructuredTaskPlan, muse_spark_open
from sahaay_core.models.local.client import LocalLlamaClient
from sahaay_core.models.local.llama_runtime import local_llama_manager
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.models.meta.muse_image import muse_image
from sahaay_core.models.meta.muse_spark import MuseSparkClient, MuseSparkPlan
from sahaay_core.models.meta.muse_voice import MuseVoiceClient, VoiceTranscriptionResult
from sahaay_core.models.meta.muse_wonder import MuseWonderClient
from sahaay_core.models.meta.sam_client import Sam31Client

router = APIRouter(prefix="/models", tags=["Models"])

meta_client = MetaClient()
baseten_client = BasetenClient()
muse_spark = MuseSparkClient(meta_client=meta_client)
muse_wonder = MuseWonderClient(meta_client=meta_client)
muse_voice = MuseVoiceClient(meta_client=meta_client)
sam_client = Sam31Client(meta_client=meta_client)
local_llama_client = LocalLlamaClient(manager=local_llama_manager)


class ModelPlanningRequest(BaseModel):
    """Request payload for Muse Spark task planning."""

    prompt: str
    contextFacts: Optional[List[Dict[str, Any]]] = None
    languageHint: Optional[str] = None


class BasetenPlanningRequest(BaseModel):
    """Request payload for Baseten Muse Spark Open structured planning."""

    goal: str
    workflowMode: str = "combined_retrieval_and_action"
    context: str = ""
    sourceFacts: Dict[str, Any] = {}


class VisualGroundingRequest(BaseModel):
    """Request payload for SAM 3.1 visual grounding."""

    targetPrompt: str
    viewportWidth: int = 1280
    viewportHeight: int = 800
    observationVersion: int = 1


@router.get("/status")
async def get_models_status() -> Dict[str, Any]:
    """Retrieve verified readiness status across all supported Meta, Baseten, and Local models."""
    local_status = local_llama_client.get_status()

    return {
        "baseten": {
            "isConfigured": baseten_client.is_configured,
            "baseUrl": baseten_client.base_url,
            "model": settings.baseten_muse_spark_model,
            "status": "READY" if baseten_client.is_configured else "NOT_CONFIGURED",
            "role": "Baseten Muse Spark Open Structured Task Planner",
        },
        "metaHosted": {
            "isConfigured": meta_client.is_configured,
            "baseUrl": meta_client.base_url,
            "models": {
                "museSpark": {
                    "id": settings.muse_spark_model_id,
                    "status": "READY" if meta_client.is_configured else "NOT_CONFIGURED",
                    "role": "Semantic Reasoning & Structured Planning",
                },
                "museWonder": {
                    "id": settings.muse_wonder_model_id,
                    "status": "READY" if meta_client.is_configured else "NOT_CONFIGURED",
                    "role": "Responses API Visual Computer-Use",
                },
                "museVoice": {
                    "id": settings.muse_voice_model_id,
                    "status": "READY" if meta_client.is_configured else "NOT_CONFIGURED",
                    "role": "Multilingual Speech-to-Text Transcription",
                },
                "museImage": {
                    "id": settings.muse_image_model,
                    "status": "READY" if muse_image.is_configured else "NOT_CONFIGURED",
                    "role": "Task Passport Visual Milestone Storytelling",
                },
                "sam": {
                    "id": settings.sam_model_id,
                    "status": "READY" if meta_client.is_configured else "NOT_CONFIGURED",
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
    }


@router.post("/test-connectivity")
async def test_model_connectivity() -> Dict[str, Any]:
    """Test live connectivity to Meta Model API, Baseten API, and check local runtime."""
    meta_result = await meta_client.check_connectivity()
    baseten_result = await baseten_client.check_connectivity()
    muse_image_result = await muse_image.check_connectivity()
    is_local_healthy = await local_llama_manager.check_health()

    return {
        "metaApi": meta_result,
        "basetenApi": baseten_result,
        "museImageApi": muse_image_result,
        "localLlama": {
            "isHealthy": is_local_healthy,
            "status": local_llama_manager.status.value,
            "message": local_llama_manager.status_message,
        },
    }


@router.post("/baseten/plan", response_model=StructuredTaskPlan)
async def plan_with_baseten_muse_spark(req: BasetenPlanningRequest) -> StructuredTaskPlan:
    """Invoke Muse Spark Open on Baseten for structured planning with local schema enforcement."""
    from uuid import uuid4

    task = TaskContract(
        taskId=uuid4(),
        sessionId=uuid4(),
        goal=req.goal,
        taskType=req.workflowMode or "combined_retrieval_and_action",
    )

    return await muse_spark_open.generate_plan(
        task=task,
        context=req.context,
        source_facts=req.sourceFacts,
    )


@router.post("/plan", response_model=MuseSparkPlan)
async def plan_with_muse_spark(req: ModelPlanningRequest) -> MuseSparkPlan:
    """Invoke Muse Spark for semantic reasoning, multilingual understanding, and structured action planning."""
    return await muse_spark.plan_and_reason(
        prompt=req.prompt,
        context_facts=req.contextFacts or [],
    )


@router.post("/transcribe", response_model=VoiceTranscriptionResult)
async def transcribe_audio(
    file: UploadFile = File(...),  # noqa: B008
    languageHints: str = Form("kn,hi,en"),  # noqa: B008
) -> VoiceTranscriptionResult:
    """Submit recorded audio chunk or file to Muse Voice Transcribe pipeline."""
    audio_bytes = await file.read()
    hints = [h.strip() for h in languageHints.split(",") if h.strip()]
    return await muse_voice.transcribe_audio_chunk(
        audio_bytes=audio_bytes,
        content_type=file.content_type or "audio/wav",
        language_hints=hints,
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
