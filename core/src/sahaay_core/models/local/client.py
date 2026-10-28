"""Local Llama Model Client.

Interacts with Llama 3.2 3B Instruct Q4_K_M GGUF running via llama-server on loopback (127.0.0.1).
Provides on-device reasoning, intent classification, and text synthesis under local-only mode.
"""

from typing import Any, Dict, Optional

import httpx

from sahaay_core.models.interfaces.base import (
    BaseLanguageModel,
    ModelProviderError,
    ModelProviderNotConfiguredError,
)
from sahaay_core.models.local.llama_runtime import (
    LocalLlamaStatusEnum,
    local_llama_manager,
)


class LocalLlamaClient(BaseLanguageModel):
    """Client for locally hosted Llama 3.2 3B Instruct model."""

    def __init__(self, manager=None) -> None:
        self.manager = manager or local_llama_manager

    def get_status(self) -> Dict[str, Any]:
        """Return real diagnostic status of local model and hardware profile."""
        hw = self.manager.detect_hardware()
        return {
            "status": self.manager.status.value,
            "message": self.manager.status_message,
            "isReady": self.manager.status == LocalLlamaStatusEnum.READY,
            "modelPath": self.manager.model_path or "Not configured",
            "serverBinary": self.manager._find_llama_server() or "Missing",
            "host": self.manager.host,
            "port": self.manager.port,
            "hardwareProfile": hw,
        }

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        context_facts: Optional[list] = None,
    ) -> str:
        """Execute local on-device inference via llama-server on 127.0.0.1."""
        if self.manager.status != LocalLlamaStatusEnum.READY:
            # Check if server is reachable
            is_healthy = await self.manager.check_health()
            if not is_healthy:
                raise ModelProviderNotConfiguredError(
                    f"Local Llama model runtime is not ready ({self.manager.status.value}): {self.manager.status_message}"
                )

        system_msg = (
            system_instruction
            or "You are Sahaay, an on-device local assistant. Be concise and accurate."
        )
        messages = [{"role": "system", "content": system_msg}]

        if context_facts:
            facts_text = "\n".join(f"- {f}" for f in context_facts)
            messages.append({"role": "system", "content": f"Context facts:\n{facts_text}"})

        messages.append({"role": "user", "content": prompt})

        url = f"http://{self.manager.host}:{self.manager.port}/v1/chat/completions"
        payload = {
            "model": "llama-3.2-3b-instruct",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 512,
        }

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, timeout=30.0)
                if res.status_code != 200:
                    raise ModelProviderError(
                        f"Local llama-server returned HTTP {res.status_code}: {res.text}"
                    )
                data = res.json()
                return data["choices"][0]["message"]["content"]
        except httpx.RequestError as ex:
            raise ModelProviderError(f"Failed to communicate with local llama-server: {ex}") from ex
