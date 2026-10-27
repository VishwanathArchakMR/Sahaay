"""Local Model Client (Deferred for Stage 01).

Explicitly unimplemented in this initial foundation stage.
Fails cleanly with ModelProviderNotConfiguredError.
"""

from typing import Optional

from sahaay_core.models.interfaces.base import BaseLanguageModel, ModelProviderNotConfiguredError


class LocalLlamaClient(BaseLanguageModel):
    """Client interface for locally hosted Llama weights."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        raise ModelProviderNotConfiguredError(
            "Local model inference is deferred in Build 01 foundation. No weights loaded."
        )
