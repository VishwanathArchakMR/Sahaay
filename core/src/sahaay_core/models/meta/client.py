"""Meta Provider Client for Sahaay.

Unified interface re-exporting MetaClient, MuseSparkClient, MuseWonderClient,
MuseVoiceClient, and Sam31Client.
"""

from typing import Optional

from sahaay_core.models.interfaces.base import BaseLanguageModel
from sahaay_core.models.meta.meta_client import MetaApiResponse, MetaClient
from sahaay_core.models.meta.muse_spark import (
    GroundedSourceFact,
    MuseSparkClient,
    MuseSparkPlan,
)
from sahaay_core.models.meta.muse_voice import (
    MuseVoiceClient,
    VoiceTranscriptionResult,
)
from sahaay_core.models.meta.muse_wonder import (
    ComputerToolCall,
    ComputerUseProposal,
    MuseWonderClient,
)
from sahaay_core.models.meta.sam_client import Sam31Client, VisualGroundingResult


class MetaHostedModelClient(BaseLanguageModel):
    """Facade implementing BaseLanguageModel via Muse Spark."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.meta_client = MetaClient(api_key=api_key)
        self.spark = MuseSparkClient(meta_client=self.meta_client)

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        """Generate grounded response via Muse Spark."""
        plan = await self.spark.plan_and_reason(prompt=prompt, context_facts=context_facts or [])
        return plan.user_facing_response


__all__ = [
    "MetaClient",
    "MetaHostedModelClient",
    "MuseSparkClient",
    "MuseSparkPlan",
    "GroundedSourceFact",
    "MuseWonderClient",
    "ComputerUseProposal",
    "ComputerToolCall",
    "MuseVoiceClient",
    "VoiceTranscriptionResult",
    "Sam31Client",
    "VisualGroundingResult",
    "MetaApiResponse",
]
