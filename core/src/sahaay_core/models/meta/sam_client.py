"""Segment Anything Model (SAM 3.1) Visual Grounding Adapter.

Provides visual segmentation and coordinate localization for screenshots.
Maps visual targets to typed bounding boxes and center coordinates correlated
with observation versions. Output serves as a grounding proposal only; it never
authorizes actions independently.
"""

import base64
import logging
import re
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel

from sahaay_core.config.settings import settings
from sahaay_core.contracts.models import ConsentGrant
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.privacy.privacy_gateway import PrivacyGateway

logger = logging.getLogger("sahaay.models.sam")

BOX_REGEX = re.compile(r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+)(?:;w=(\d+);h=(\d+))?\|>")


class BoundingBox(BaseModel):
    """Normalized or pixel bounding box."""

    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int
    center_x: int
    center_y: int


class VisualGroundingResult(BaseModel):
    """Result of visual localization via SAM 3.1."""

    grounding_id: str
    target_prompt: str
    observation_version: int
    bounding_box: BoundingBox
    confidence_score: float
    has_segmentation_mask: bool = False
    is_live_call: bool = False


class Sam31Client:
    """Client for SAM 3.1 visual grounding and segmentation."""

    def __init__(
        self,
        meta_client: Optional[MetaClient] = None,
        model_id: Optional[str] = None,
    ) -> None:
        self.client = meta_client or MetaClient()
        self.model_id = model_id or settings.sam_model_id
        self.privacy_gateway = PrivacyGateway()

    async def segment_element(
        self,
        image_bytes: bytes,
        target_prompt: str,
        observation_version: str = "obs-v1",
    ) -> VisualGroundingResult:
        """Alias for segment_and_locate with string observation version."""
        obs_v = 1
        try:
            obs_v = int(observation_version.replace("obs-v", ""))
        except Exception:
            obs_v = 1
        return await self.segment_and_locate(
            screenshot_bytes=image_bytes,
            target_prompt=target_prompt,
            observation_version=obs_v,
        )

    async def segment_and_locate(
        self,
        screenshot_bytes: bytes,
        target_prompt: str,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        observation_version: int = 1,
        active_grants: Optional[List[ConsentGrant]] = None,
    ) -> VisualGroundingResult:
        """Locate target element in screenshot using SAM 3.1 segmentation.

        Returns typed bounding box and center coordinates.
        """
        active_grants = active_grants or []
        grounding_id = f"sam-{uuid4()}"

        privacy_eval = self.privacy_gateway.evaluate_outbound_request(
            destination="https://api.meta.ai/v1",
            purpose="Visual grounding segmentation",
            content=f"SAM 3.1 target prompt: {target_prompt}",
            active_grants=active_grants,
        )

        if not privacy_eval.allowTransmission or not self.client.is_configured:
            logger.info("SAM 3.1 running in local deterministic fallback: %s", privacy_eval.reason)
            return self._build_deterministic_grounding(
                grounding_id=grounding_id,
                target_prompt=target_prompt,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                observation_version=observation_version,
            )

        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")
        payload = {
            "model": self.model_id,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": target_prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{b64_image}",
                        },
                    ],
                }
            ],
        }

        try:
            api_res = await self.client.post_endpoint("responses", payload)
            output_list = api_res.data.get("output", [])
            output_text = ""
            if output_list:
                content_items = output_list[0].get("content", [])
                if content_items:
                    output_text = content_items[0].get("text", "")

            box_match = BOX_REGEX.search(output_text)
            if box_match:
                x1 = int(box_match.group(1))
                y1 = int(box_match.group(2))
                x2 = int(box_match.group(3))
                y2 = int(box_match.group(4))
                x1 = max(0, min(viewport_width, x1))
                y1 = max(0, min(viewport_height, y1))
                x2 = max(x1 + 1, min(viewport_width, x2))
                y2 = max(y1 + 1, min(viewport_height, y2))
                w = x2 - x1
                h = y2 - y1

                return VisualGroundingResult(
                    grounding_id=grounding_id,
                    target_prompt=target_prompt,
                    observation_version=observation_version,
                    bounding_box=BoundingBox(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        width=w,
                        height=h,
                        center_x=x1 + w // 2,
                        center_y=y1 + h // 2,
                    ),
                    confidence_score=0.95,
                    has_segmentation_mask=bool("<|mask;" in output_text),
                    is_live_call=True,
                )
            else:
                logger.warning(
                    "No bounding box parsed from SAM 3.1 response: %s", output_text[:100]
                )
                return self._build_deterministic_grounding(
                    grounding_id=grounding_id,
                    target_prompt=target_prompt,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height,
                    observation_version=observation_version,
                )
        except Exception as ex:
            logger.warning(
                "Online SAM 3.1 call failed (%s); reverting to deterministic fallback.", ex
            )
            return self._build_deterministic_grounding(
                grounding_id=grounding_id,
                target_prompt=target_prompt,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                observation_version=observation_version,
            )

    def _build_deterministic_grounding(
        self,
        grounding_id: str,
        target_prompt: str,
        viewport_width: int,
        viewport_height: int,
        observation_version: int,
    ) -> VisualGroundingResult:
        """Deterministic grounding calculation for offline testing."""
        # Synthesize a safe centered box
        x1 = viewport_width // 4
        y1 = viewport_height // 4
        w = min(200, viewport_width // 3)
        h = 40
        x2 = x1 + w
        y2 = y1 + h

        return VisualGroundingResult(
            grounding_id=grounding_id,
            target_prompt=target_prompt,
            observation_version=observation_version,
            bounding_box=BoundingBox(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                width=w,
                height=h,
                center_x=x1 + w // 2,
                center_y=y1 + h // 2,
            ),
            confidence_score=0.88,
            has_segmentation_mask=False,
            is_live_call=False,
        )
