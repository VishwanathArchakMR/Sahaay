"""Model Capability Router for Sahaay.

Implements the layered model routing hierarchy:
    Deterministic Logic
            ↓
    Local / Lightweight Model (Llama 3.2 3B)
            ↓
    Meta API Reasoning Model (Muse Spark 1.3 / Muse Wonder 1.0)
            ↓
    Specialized Visual / Voice Model (SAM 3.1 / Muse Voice / Muse Image)

Ensures every model invocation has a clear purpose, input provenance, output validation,
timeout, and fallback. Model proposals are strictly validated against the Capability Registry
before authorization or execution.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel

from sahaay_core.capabilities.registry import capability_registry
from sahaay_core.config.settings import settings
from sahaay_core.models.local.client import LocalLlamaClient
from sahaay_core.models.local.llama_runtime import local_llama_manager
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.models.meta.muse_image import MuseImageClient, muse_image
from sahaay_core.models.meta.muse_spark import MuseSparkClient, muse_spark
from sahaay_core.models.meta.muse_voice import MuseVoiceClient
from sahaay_core.models.meta.muse_wonder import MuseWonderClient
from sahaay_core.models.meta.sam_client import Sam31Client

logger = logging.getLogger("sahaay.models.router")


class ModelTier(str, Enum):
    DETERMINISTIC_LOGIC = "deterministic_logic"
    LOCAL_LLAMA = "local_llama_3_2"
    META_MUSE_SPARK = "meta_muse_spark_1_3"
    META_MUSE_WONDER = "meta_muse_wonder_1_0"
    META_MUSE_VOICE = "meta_muse_voice_1_0"
    META_SAM_GROUNDING = "meta_sam_3_1"
    META_MUSE_IMAGE = "meta_muse_image_1_0"


class ModelRouteDecision(BaseModel):
    """Routing decision for a task or sub-task."""

    selected_tier: ModelTier
    model_id: str
    purpose: str
    is_live_call: bool
    requires_network: bool
    timeout_seconds: float
    fallback_tier: Optional[ModelTier] = None
    reasoning: str = ""


class ModelCapabilityRouter:
    """Intelligent router selecting the minimum required model intelligence for task quality and privacy."""

    def __init__(
        self,
        meta_client: Optional[MetaClient] = None,
        spark_client: Optional[MuseSparkClient] = None,
        wonder_client: Optional[MuseWonderClient] = None,
        voice_client: Optional[MuseVoiceClient] = None,
        sam_client: Optional[Sam31Client] = None,
        image_client: Optional[MuseImageClient] = None,
        local_client: Optional[LocalLlamaClient] = None,
    ) -> None:
        self.meta_client = meta_client or MetaClient()
        self.spark_client = spark_client or muse_spark
        self.wonder_client = wonder_client or MuseWonderClient(meta_client=self.meta_client)
        self.voice_client = voice_client or MuseVoiceClient(meta_client=self.meta_client)
        self.sam_client = sam_client or Sam31Client(meta_client=self.meta_client)
        self.image_client = image_client or muse_image
        self.local_client = local_client or LocalLlamaClient(manager=local_llama_manager)

    def route_task(
        self,
        goal: str,
        context: Optional[str] = None,
        local_only_override: bool = False,
    ) -> ModelRouteDecision:
        """Determines the appropriate model tier based on task type, privacy tier, and live model availability."""
        is_local_only = local_only_override or settings.local_only_mode
        goal_lower = goal.lower().strip()
        combined = f"{goal_lower} {(context or '').lower()}"

        # 1. Specialized: Voice Transcription
        if any(w in combined for w in ("transcribe audio", "speech to text", "voice record")):
            if is_local_only or not self.meta_client.is_configured:
                return ModelRouteDecision(
                    selected_tier=ModelTier.DETERMINISTIC_LOGIC,
                    model_id="local_transcription_fallback",
                    purpose="Offline deterministic voice transcription fallback",
                    is_live_call=False,
                    requires_network=False,
                    timeout_seconds=5.0,
                    reasoning="Local-only mode active or Meta unconfigured; using local audio processing.",
                )
            return ModelRouteDecision(
                selected_tier=ModelTier.META_MUSE_VOICE,
                model_id=settings.muse_voice_model_id,
                purpose="Multilingual speech-to-text transcription",
                is_live_call=True,
                requires_network=True,
                timeout_seconds=60.0,
                fallback_tier=ModelTier.DETERMINISTIC_LOGIC,
                reasoning="Hosted Meta Voyager ASR selected for high-accuracy multilingual transcription.",
            )

        # 2. Specialized: Visual Grounding / SAM 3.1
        if any(
            w in combined
            for w in (
                "locate button",
                "find element coordinates",
                "visual grounding",
                "segment",
                "bounding box",
                "sam 3.1",
            )
        ):
            if is_local_only or not self.meta_client.is_configured:
                return ModelRouteDecision(
                    selected_tier=ModelTier.DETERMINISTIC_LOGIC,
                    model_id="deterministic_grounding",
                    purpose="Deterministic coordinate bounding box resolution",
                    is_live_call=False,
                    requires_network=False,
                    timeout_seconds=5.0,
                    reasoning="Visual grounding in local mode using UIA coordinate lookup.",
                )
            return ModelRouteDecision(
                selected_tier=ModelTier.META_SAM_GROUNDING,
                model_id=settings.sam_model_id,
                purpose="Visual segmentation and coordinate localization on desktop screenshot",
                is_live_call=True,
                requires_network=True,
                timeout_seconds=20.0,
                fallback_tier=ModelTier.DETERMINISTIC_LOGIC,
                reasoning="SAM 3.1 selected for pixel-accurate UI segmentation.",
            )

        # 3. Specialized: Creative Image Editing / Styling
        if any(
            w in combined
            for w in (
                "edit image",
                "style image",
                "retro style",
                "vintage style",
                "synthwave",
                "generate image",
            )
        ):
            if is_local_only or not self.meta_client.is_configured:
                return ModelRouteDecision(
                    selected_tier=ModelTier.DETERMINISTIC_LOGIC,
                    model_id="local_vector_svg",
                    purpose="Local vector SVG styling and art generation",
                    is_live_call=False,
                    requires_network=False,
                    timeout_seconds=10.0,
                    reasoning="Local vector SVG fallback selected for offline privacy-preserving creative output.",
                )
            return ModelRouteDecision(
                selected_tier=ModelTier.META_MUSE_IMAGE,
                model_id=settings.muse_image_model,
                purpose="Milestone illustration and artistic image styling",
                is_live_call=True,
                requires_network=True,
                timeout_seconds=30.0,
                fallback_tier=ModelTier.DETERMINISTIC_LOGIC,
                reasoning="Muse Image selected for hosted AI generative styling.",
            )

        # 4. Strict Local-Only Mode -> Local Llama 3.2 3B Instruct
        if is_local_only:
            return ModelRouteDecision(
                selected_tier=ModelTier.LOCAL_LLAMA,
                model_id=settings.local_llama_model_path.name
                if settings.local_llama_model_path
                else "Llama-3.2-3B-Instruct",
                purpose="On-device local LLM reasoning and intent classification",
                is_live_call=False,
                requires_network=False,
                timeout_seconds=60.0,
                fallback_tier=ModelTier.DETERMINISTIC_LOGIC,
                reasoning="Privacy Gateway enforced Local-Only Mode. Outbound network disabled.",
            )

        # 5. Online Meta Cloud Reasoning (Muse Spark 1.3 or Muse Wonder 1.0)
        if self.meta_client.is_configured:
            # For direct computer control tasks, Muse Wonder can be paired; default to Spark 1.3 for general reasoning
            if any(w in combined for w in ("computer", "click", "desktop window", "uia")):
                return ModelRouteDecision(
                    selected_tier=ModelTier.META_MUSE_WONDER,
                    model_id=settings.muse_wonder_model_id,
                    purpose="Computer-use action formulation and visual UI guidance",
                    is_live_call=True,
                    requires_network=True,
                    timeout_seconds=90.0,
                    fallback_tier=ModelTier.META_MUSE_SPARK,
                    reasoning="Muse Wonder selected for desktop computer control context.",
                )

            return ModelRouteDecision(
                selected_tier=ModelTier.META_MUSE_SPARK,
                model_id=settings.muse_spark_model_id,
                purpose="Multi-turn semantic reasoning, tool calling, and structured task planning",
                is_live_call=True,
                requires_network=True,
                timeout_seconds=180.0,
                fallback_tier=ModelTier.DETERMINISTIC_LOGIC,
                reasoning="Muse Spark 1.3 selected as primary reasoning and planning model.",
            )

        # 6. Default Fallback when unconfigured
        return ModelRouteDecision(
            selected_tier=ModelTier.DETERMINISTIC_LOGIC,
            model_id="deterministic_dag_engine",
            purpose="Deterministic capability execution via DAG engine",
            is_live_call=False,
            requires_network=False,
            timeout_seconds=30.0,
            reasoning="Meta credentials not configured; using deterministic capability execution.",
        )

    def validate_model_proposal(
        self, tool_name: str, tool_args: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validates that a tool proposal from model reasoning matches an executable registered capability."""
        if not capability_registry.is_registered(tool_name):
            return False, f"Model proposed unregistered capability '{tool_name}'."

        cap = capability_registry.get(tool_name)
        if not cap:
            return False, f"Capability '{tool_name}' not found."

        # Validate required parameters
        if cap.input_schema and "required" in cap.input_schema:
            missing = [
                p
                for p in cap.input_schema["required"]
                if p not in tool_args or tool_args[p] is None
            ]
            if missing:
                return False, f"Model call to '{tool_name}' missing required parameters: {missing}"

        return True, None


# Global singleton router
model_router = ModelCapabilityRouter()
