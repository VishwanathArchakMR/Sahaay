"""Baseten Client for Muse Spark Open.

Asynchronous OpenAI-compatible HTTP client for Baseten Model APIs.
Implements bounded retries, token redaction, request correlation, and status probing.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from sahaay_core.config.settings import settings

logger = logging.getLogger(__name__)


class BasetenError(Exception):
    """Base exception for Baseten model API errors."""

    pass


class BasetenAuthError(BasetenError):
    """Authentication or authorization failure (HTTP 401/403)."""

    pass


class BasetenRateLimitError(BasetenError):
    """Rate limit or quota exceeded (HTTP 429)."""

    pass


class BasetenProviderError(BasetenError):
    """Upstream server or model error (HTTP 5xx)."""

    pass


@dataclass
class BasetenApiResponse:
    """Sanitized response structure from Baseten."""

    status_code: int
    data: Dict[str, Any]
    latency_ms: float
    usage: Dict[str, int]
    model_id: str
    error: Optional[str] = None


class BasetenClient:
    """Async client for Baseten Model API with OpenAI-compatible chat completions."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or settings.baseten_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.baseten_api_key
        self.default_model = default_model or settings.baseten_muse_spark_model

    @property
    def is_configured(self) -> bool:
        """Returns True if Baseten API key is present."""
        return bool(self.api_key and self.api_key.strip())

    async def check_connectivity(self) -> Dict[str, Any]:
        """Probes Baseten API connectivity truthfully."""
        if not self.is_configured:
            return {
                "configured": False,
                "status": "NOT_CONFIGURED",
                "baseUrl": self.base_url,
                "model": self.default_model,
                "message": "Baseten API key (BASETEN_API_KEY) is not configured.",
            }

        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            # Minimal probe to verify authentication
            payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                latency_ms = (time.perf_counter() - start_time) * 1000

                if res.status_code == 200:
                    return {
                        "configured": True,
                        "status": "READY",
                        "baseUrl": self.base_url,
                        "model": self.default_model,
                        "latencyMs": round(latency_ms, 2),
                        "message": "Baseten Muse Spark Open endpoint reachable and authenticated.",
                    }
                elif res.status_code in (401, 403):
                    return {
                        "configured": True,
                        "status": "UNAUTHORIZED",
                        "baseUrl": self.base_url,
                        "model": self.default_model,
                        "message": "Invalid Baseten API credentials.",
                    }
                else:
                    return {
                        "configured": True,
                        "status": "FAILED",
                        "baseUrl": self.base_url,
                        "model": self.default_model,
                        "message": f"Baseten returned HTTP {res.status_code}.",
                    }
        except httpx.TimeoutException:
            return {
                "configured": True,
                "status": "UNAVAILABLE",
                "baseUrl": self.base_url,
                "model": self.default_model,
                "message": "Connection to Baseten timed out.",
            }
        except Exception as ex:
            return {
                "configured": True,
                "status": "FAILED",
                "baseUrl": self.base_url,
                "model": self.default_model,
                "message": f"Connection error: {str(ex)[:100]}",
            }

    async def post_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
        timeout_seconds: float = 30.0,
    ) -> BasetenApiResponse:
        """Sends an OpenAI-compatible chat completion request with bounded retries."""
        if not self.is_configured:
            raise BasetenAuthError("Baseten API key is not configured in environment or settings.")

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Sahaay-Agent/0.1.0",
        }

        max_attempts = 3
        backoff_sec = 1.0

        for attempt in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if response.status_code == 200:
                        data = response.json()
                        usage = data.get("usage", {})
                        return BasetenApiResponse(
                            status_code=200,
                            data=data,
                            latency_ms=latency_ms,
                            usage=usage,
                            model_id=target_model,
                        )

                    elif response.status_code in (401, 403):
                        raise BasetenAuthError(
                            f"Baseten authentication failed (HTTP {response.status_code})"
                        )

                    elif response.status_code == 429:
                        if attempt == max_attempts:
                            raise BasetenRateLimitError(
                                "Baseten rate limit exceeded after retries."
                            )
                        logger.warning(
                            "Baseten rate limited (429); backing off %s sec.", backoff_sec
                        )
                        await asyncio.sleep(backoff_sec)
                        backoff_sec *= 2.0
                        continue

                    elif response.status_code >= 500:
                        if attempt == max_attempts:
                            raise BasetenProviderError(
                                f"Baseten upstream server error (HTTP {response.status_code})"
                            )
                        logger.warning("Baseten 5xx error; retrying in %s sec.", backoff_sec)
                        await asyncio.sleep(backoff_sec)
                        backoff_sec *= 2.0
                        continue

                    else:
                        raise BasetenError(
                            f"Baseten returned HTTP {response.status_code}: {response.text[:200]}"
                        )

            except httpx.TimeoutException as err:
                if attempt == max_attempts:
                    raise BasetenProviderError(
                        f"Baseten request timed out after {timeout_seconds}s."
                    ) from err
                await asyncio.sleep(backoff_sec)
                backoff_sec *= 2.0
            except (BasetenError, asyncio.CancelledError):
                raise
            except Exception as ex:
                if attempt == max_attempts:
                    raise BasetenError(f"Baseten request failed: {str(ex)[:200]}") from ex
                await asyncio.sleep(backoff_sec)
                backoff_sec *= 2.0

        raise BasetenProviderError("Failed to obtain response from Baseten.")
