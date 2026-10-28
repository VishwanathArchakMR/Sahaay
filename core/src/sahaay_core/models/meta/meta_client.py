"""Common Meta Provider Client Foundation.

Communicates with the official Meta Model API base: https://api.meta.ai/v1.
Enforces asynchronous execution, explicit timeouts, bounded retries with backoff,
credential redaction, and strict error classification.
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel

from sahaay_core.config.settings import settings
from sahaay_core.models.interfaces.base import (
    ModelProviderError,
    ModelProviderNotConfiguredError,
)

logger = logging.getLogger("sahaay.models.meta")

# Redaction pattern for safe logging
BEARER_REDACTION_REGEX = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)


class MetaModelUsage(BaseModel):
    """Token or compute usage returned by Meta APIs."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class MetaApiResponse(BaseModel):
    """Standardized response container for Meta model requests."""

    model_id: str
    status_code: int
    data: Dict[str, Any]
    usage: Optional[MetaModelUsage] = None
    latency_ms: float = 0.0
    is_live_call: bool = True


class MetaClient:
    """Foundational client for Meta hosted model endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else (settings.model_api_key or os.environ.get("MODEL_API_KEY", ""))
        )
        self.base_url = (base_url or settings.meta_api_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def is_configured(self) -> bool:
        """Check if an API key is present."""
        return bool(self.api_key and self.api_key.strip())

    def _get_headers(self) -> Dict[str, str]:
        """Construct authorization headers without exposing keys in exceptions."""
        if not self.is_configured:
            raise ModelProviderNotConfiguredError(
                "Meta Model API key is not configured. Set MODEL_API_KEY or configure settings."
            )
        return {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Sahaay-Desktop-Agent/0.4.0",
        }

    async def post_endpoint(
        self,
        endpoint_path: str,
        payload: Dict[str, Any],
        client_override: Optional[httpx.AsyncClient] = None,
    ) -> MetaApiResponse:
        """Send authenticated POST request to Meta API with retries and timeout."""
        headers = self._get_headers()
        url = f"{self.base_url}/{endpoint_path.lstrip('/')}"

        start_time = asyncio.get_event_loop().time()
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if client_override:
                    response = await client_override.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                else:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            url,
                            json=payload,
                            headers=headers,
                            timeout=self.timeout_seconds,
                        )

                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Model API error handling
                if response.status_code == 401:
                    raise ModelProviderError(
                        "Meta Model API authentication failed (HTTP 401). Verify MODEL_API_KEY."
                    )
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    raise ModelProviderError("Meta Model API rate limit exceeded (HTTP 429).")
                if response.status_code >= 400:
                    try:
                        err_body = response.json()
                        err_msg = err_body.get("error", {}).get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    raise ModelProviderError(
                        f"Meta Model API returned HTTP {response.status_code}: {err_msg}"
                    )

                data = response.json()
                usage_data = data.get("usage")
                usage = MetaModelUsage(**usage_data) if usage_data else None

                return MetaApiResponse(
                    model_id=data.get("model", payload.get("model", "unknown")),
                    status_code=response.status_code,
                    data=data,
                    usage=usage,
                    latency_ms=latency_ms,
                    is_live_call=True,
                )

            except httpx.TimeoutException as ex:
                last_exception = ex
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ModelProviderError(
                    f"Meta Model API request timed out after {self.timeout_seconds}s."
                ) from ex
            except httpx.RequestError as ex:
                last_exception = ex
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise ModelProviderError(f"Meta Model API connection error: {ex}") from ex

        raise ModelProviderError(
            f"Meta Model API request failed after {self.max_retries} attempts: {last_exception}"
        )

    async def check_connectivity(
        self, client_override: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Any]:
        """Perform a safe probe to test Meta API connectivity without transmitting user content."""
        if not self.is_configured:
            return {
                "status": "NOT_CONFIGURED",
                "message": "MODEL_API_KEY environment variable is not set.",
                "isConfigured": False,
                "isLive": False,
            }

        headers = self._get_headers()
        url = f"{self.base_url}/models"
        try:
            if client_override:
                res = await client_override.get(url, headers=headers, timeout=5.0)
            else:
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, headers=headers, timeout=5.0)

            if res.status_code == 200:
                return {
                    "status": "AUTHENTICATED",
                    "message": "Successfully authenticated with Meta Model API.",
                    "isConfigured": True,
                    "isLive": True,
                    "isHealthy": True,
                }
            elif res.status_code in (401, 403):
                return {
                    "status": "UNAUTHORIZED",
                    "message": "Invalid, expired or unauthorized MODEL_API_KEY.",
                    "isConfigured": True,
                    "isLive": False,
                    "isHealthy": False,
                }
            else:
                return {
                    "status": "UNAVAILABLE",
                    "message": f"Meta Model API returned HTTP {res.status_code}.",
                    "isConfigured": True,
                    "isLive": False,
                    "isHealthy": False,
                }
        except Exception as ex:
            return {
                "status": "FAILED",
                "message": f"Could not connect to {self.base_url}: {ex}",
                "isConfigured": True,
                "isLive": False,
                "isHealthy": False,
            }
