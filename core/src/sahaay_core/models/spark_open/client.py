"""Muse Spark Open Provider Client (Deferred for Stage 01).

Explicitly unimplemented in this initial foundation stage.
Fails cleanly with ModelProviderNotConfiguredError.
"""

from typing import Optional

from sahaay_core.models.interfaces.base import BaseLanguageModel, ModelProviderNotConfiguredError


class SparkOpenClient(BaseLanguageModel):
    """Client interface for Muse Spark Open models."""

    def __init__(self, endpoint_url: Optional[str] = None) -> None:
        self.endpoint_url = endpoint_url

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        raise ModelProviderNotConfiguredError(
            "Muse Spark Open inference provider is deferred in Build 01 foundation."
        )
