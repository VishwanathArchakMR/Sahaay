"""Centralized TLS Transport and HTTP Client Factory for Meta Model APIs.

Provides a robust, secure SSL context that:
1. Loads the Mozilla CA bundle via certifi.
2. Enumerates and loads Windows enterprise/intermediate certificates from the Windows
   Certificate Store (ROOT and CA stores).
3. Preserves strict TLS certificate verification (CERT_REQUIRED) and hostname checks.
4. Never disables verification or hostname validation (no verify=False).
5. Provides safe error classification for TLS and network errors.
"""

import os
import ssl
import sys
from typing import Any, Optional, Tuple

import certifi
import httpx


def get_meta_ssl_context(ca_file: Optional[str] = None) -> ssl.SSLContext:
    """Construct an authoritative SSLContext with certifi bundle and Windows system certificates.

    Preserves strict certificate validation (verify_mode=CERT_REQUIRED) and hostname
    verification (check_hostname=True).
    """
    bundle_path = ca_file or os.environ.get("SSL_CERT_FILE") or certifi.where()
    ctx = ssl.create_default_context(cafile=bundle_path)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    # Also load enterprise / local root & intermediate CA certificates on Windows
    if sys.platform == "win32":
        for store_name in ("ROOT", "CA"):
            try:
                for cert_bytes, encoding_type, _ in ssl.enum_certificates(store_name):
                    if encoding_type == "x509_asn":
                        try:
                            ctx.load_verify_locations(cadata=cert_bytes)
                        except Exception:
                            pass
            except Exception:
                pass

    return ctx


def create_meta_http_client(
    timeout: float = 30.0,
    ca_file: Optional[str] = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create a configured httpx.AsyncClient using the authoritative Meta SSL context."""
    ctx = get_meta_ssl_context(ca_file=ca_file)
    return httpx.AsyncClient(verify=ctx, timeout=timeout, **kwargs)


def classify_meta_exception(ex: Exception) -> Tuple[str, str]:
    """Classify an exception into a truthful status category and safe narrative.

    Returns (status_category, user_safe_message).
    Categories:
    - TLS_ERROR
    - NETWORK_ERROR
    - TIMEOUT_ERROR
    - API_ERROR
    """
    err_str = str(ex)

    if (
        isinstance(ex, ssl.SSLCertVerificationError)
        or "CERTIFICATE_VERIFY_FAILED" in err_str
        or "certificate verify failed" in err_str.lower()
    ):
        return (
            "TLS_ERROR",
            f"TLS certificate verification failed: {err_str}. Ensure the server presents a valid certificate chain and system root certificates are up to date.",
        )

    if (
        isinstance(ex, (httpx.ConnectTimeout, httpx.ReadTimeout, TimeoutError))
        or "timed out" in err_str.lower()
    ):
        return (
            "TIMEOUT_ERROR",
            f"Connection timed out contacting Meta API: {err_str}",
        )

    if (
        isinstance(ex, (httpx.ConnectError, ConnectionError, OSError))
        or "getaddrinfo failed" in err_str.lower()
        or "connection refused" in err_str.lower()
    ):
        return (
            "NETWORK_ERROR",
            f"Network connection to Meta API failed: {err_str}. Check your internet connection or proxy settings.",
        )

    return ("API_ERROR", err_str)
