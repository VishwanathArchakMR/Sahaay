"""Abstract Interfaces for Model Providers in Sahaay."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ModelProviderError(Exception):
    """Raised when a model provider operation fails or is unconfigured."""

    pass


class ModelProviderNotConfiguredError(ModelProviderError):
    """Raised when a model is invoked before required credentials or local runtime are present."""

    pass


class BaseLanguageModel(ABC):
    """Base interface for multimodal and language models."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        """Generate response from model through Privacy Gateway."""
        pass


class BaseVisionModel(ABC):
    """Base interface for vision / UI grounding models (e.g. SAM 3.1, Muse Image)."""

    @abstractmethod
    async def segment_or_locate(
        self,
        image_bytes: bytes,
        target_description: str,
    ) -> Dict[str, Any]:
        """Locate element in screenshot."""
        pass
