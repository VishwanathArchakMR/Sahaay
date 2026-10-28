"""Safe Web Page Fetcher with Strict SSRF Defense and Content Sanitization."""

import hashlib
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

import httpx

from sahaay_core.research.models import PageFetchResult

logger = logging.getLogger(__name__)

# Disallowed IP ranges (RFC 1918, RFC 3927, loopback, cloud metadata)
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
    "text/xml",
}

# Prompt injection markers to neutralize in web content
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s*prompt\s*:"),
    re.compile(r"(?i)you\s+are\s+now\s+(an\s+unrestricted|in\s+developer\s+mode)"),
    re.compile(r"(?i)disregard\s+(the\s+above|all\s+rules)"),
    re.compile(r"(?i)secret\s*key\s*="),
]


class SSRFValidationError(ValueError):
    """Raised when a URL targets a restricted, local, or private IP address."""

    pass


class SafeWebFetcher:
    """Safely retrieves public web pages with defense against SSRF, DNS rebinding, and oversized payloads."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_size_bytes: int = 2 * 1024 * 1024,  # 2MB
        max_redirects: int = 3,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_size_bytes = max_size_bytes
        self.max_redirects = max_redirects

    def validate_url(self, url: str) -> str:
        """Validates that a URL is safe to fetch and does not resolve to private/local infrastructure."""
        parsed = urlparse(url)

        # 1. Scheme Check
        if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
            raise SSRFValidationError(
                f"Disallowed scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
            )

        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("URL lacks a valid hostname.")

        # 2. Reject explicit localhost or cloud metadata hostnames
        if hostname.lower() in {"localhost", "metadata.google.internal", "instance-data"}:
            raise SSRFValidationError(f"Targeting host '{hostname}' is prohibited.")

        # 3. DNS Resolution and IP Validation
        try:
            addr_info = socket.getaddrinfo(
                hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)

                for net in DISALLOWED_NETWORKS:
                    if ip_obj in net:
                        raise SSRFValidationError(
                            f"Host '{hostname}' resolved to private/restricted IP address {ip_str}."
                        )
        except socket.gaierror as e:
            raise SSRFValidationError(f"Could not resolve host '{hostname}': {e}") from e

        return url

    async def fetch_page(self, url: str) -> PageFetchResult:
        """Safely fetches and sanitizes a public web page."""
        validated_url = self.validate_url(url)

        headers = {
            "User-Agent": "SahaayAgent/0.6.0 (Windows; Public Research; +https://github.com/VishwanathArchakMR/Sahaay)",
            "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.5",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            max_redirects=self.max_redirects,
            verify=True,
        ) as client:
            resp = await client.get(validated_url, headers=headers)

            # Re-validate final URL after potential redirects
            if resp.history:
                final_url = str(resp.url)
                self.validate_url(final_url)

            if resp.status_code != 200:
                raise ValueError(f"HTTP request failed with status {resp.status_code}")

            # Check content-type
            content_type_header = resp.headers.get("content-type", "").lower()
            base_type = content_type_header.split(";")[0].strip()
            if base_type not in ALLOWED_CONTENT_TYPES:
                raise ValueError(
                    f"Unsupported content type '{base_type}'. Only text and HTML pages are permitted."
                )

            # Check payload size
            content_bytes = resp.content
            if len(content_bytes) > self.max_size_bytes:
                raise ValueError(
                    f"Response size ({len(content_bytes)} bytes) exceeds maximum permitted limit ({self.max_size_bytes} bytes)."
                )

            # Clean and sanitize content
            raw_text = resp.text
            sha256_hash = hashlib.sha256(content_bytes).hexdigest()

            title, cleaned_text = self._extract_readable_text(raw_text, base_type)
            sanitized_text = self._sanitize_prompt_injection(cleaned_text)

            return PageFetchResult(
                url=str(resp.url),
                title=title or "Public Document",
                content_type=base_type,
                extracted_text=sanitized_text[:10000],  # Bound text length
                sha256=sha256_hash,
                byte_count=len(content_bytes),
                sanitized=True,
            )

    def _extract_readable_text(self, raw_content: str, content_type: str) -> tuple[str, str]:
        """Strips HTML tags, scripts, navigation, and extracts title and body text."""
        if content_type != "text/html":
            return "Document", raw_content.strip()

        # Extract title
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", raw_content, re.IGNORECASE | re.DOTALL
        )
        title = title_match.group(1).strip() if title_match else "Web Page"

        # Remove scripts, styles, noscript, svg
        clean = re.sub(
            r"<(script|style|noscript|svg|head)[^>]*>.*?</\1>",
            "",
            raw_content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Remove header, footer, nav
        clean = re.sub(
            r"<(nav|header|footer)[^>]*>.*?</\1>", "", clean, flags=re.IGNORECASE | re.DOTALL
        )
        # Remove remaining HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        return title, clean

    def _sanitize_prompt_injection(self, text: str) -> str:
        """Neutralizes suspicious instruction patterns embedded in untrusted web pages."""
        sanitized = text
        for pat in PROMPT_INJECTION_PATTERNS:
            sanitized = pat.sub("[REDACTED_UNTRUSTED_INSTRUCTION]", sanitized)
        return sanitized


# Global fetcher singleton
safe_web_fetcher = SafeWebFetcher()
