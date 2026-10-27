"""Meta Provider Client (Deferred for Stage 01).

Explicitly unimplemented in this initial foundation stage.
Fails cleanly with ModelProviderNotConfiguredError.
"""

from typing import Optional

from sahaay_core.models.interfaces.base import BaseLanguageModel, ModelProviderNotConfiguredError


class MetaClient(BaseLanguageModel):
    """Client interface for Meta hosted models (e.g. Llama 3.3)."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        raise ModelProviderNotConfiguredError(
            "Meta inference provider is deferred in Build 01 foundation. No active external provider configured."
        )
