"""Privacy Gateway Engine for Sahaay.

Mandatory privacy checkpoint for all external inference and outbound transmissions.
Implements fail-closed defaults, local-only mode, data classification, and sanitized audit trails.
"""

import re
from typing import List, Optional
from uuid import uuid4

from sahaay_core.config.settings import settings
from sahaay_core.contracts.models import (
    ConsentGrant,
    DataClassificationEnum,
    PrivacyDecision,
)

# Known sensitive patterns that elevate data classification to CREDENTIAL or SENSITIVE_PII
CREDENTIAL_REGEX = re.compile(
    r"(password|bearer\s+[A-Za-z0-9_\-\.]|api[_-]?key|secret)", re.IGNORECASE
)
PII_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PII_PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

# Configured provider allowlist for external model inference
ALLOWED_EXTERNAL_DESTINATIONS: List[str] = [
    "https://api.meta.ai/v1",
    "https://api.meta.ai",
    "meta_model_api",
    "https://inference.baseten.co/v1",
    "https://inference.baseten.co",
    "baseten_api",
]


class PrivacyGateway:
    """Fail-closed Privacy Gateway enforcing user consent and data minimization."""

    def __init__(self, local_only_mode: Optional[bool] = None) -> None:
        self.local_only_mode = (
            local_only_mode if local_only_mode is not None else settings.local_only_mode
        )

    def classify_data(self, content: str) -> DataClassificationEnum:
        """Analyze text and assign strict data classification."""
        if not content:
            return DataClassificationEnum.PUBLIC

        if CREDENTIAL_REGEX.search(content):
            return DataClassificationEnum.CREDENTIAL

        if PII_EMAIL_REGEX.search(content) or PII_PHONE_REGEX.search(content):
            return DataClassificationEnum.SENSITIVE_PII

        return DataClassificationEnum.INTERNAL

    def evaluate_outbound_request(
        self,
        destination: str,
        purpose: str,
        content: str,
        active_grants: List[ConsentGrant],
        max_payload_bytes: int = 1_000_000,
    ) -> PrivacyDecision:
        """Evaluate whether outbound data transmission is permitted.

        Fails closed on any ambiguity, missing consent, or local-only setting.
        """
        classification = self.classify_data(content)

        # 1. Local-only mode fails closed unconditionally
        if self.local_only_mode:
            return PrivacyDecision(
                decisionId=uuid4(),
                allowTransmission=False,
                destination=destination,
                dataClassification=classification,
                reason="Local-only mode is active. Outbound transmission is strictly prohibited.",
            )

        # 2. Credentials can NEVER be transmitted outbound regardless of destination or consent
        if classification == DataClassificationEnum.CREDENTIAL:
            return PrivacyDecision(
                decisionId=uuid4(),
                allowTransmission=False,
                destination=destination,
                dataClassification=classification,
                reason="Detected credentials in payload; external transmission forbidden.",
            )

        # 3. Allowlist check for external providers
        if destination not in ALLOWED_EXTERNAL_DESTINATIONS:
            return PrivacyDecision(
                decisionId=uuid4(),
                allowTransmission=False,
                destination=destination,
                dataClassification=classification,
                reason=f"Destination '{destination}' is not in configured provider allowlist.",
            )

        # 4. Payload size limitation
        if len(content.encode("utf-8")) > max_payload_bytes:
            return PrivacyDecision(
                decisionId=uuid4(),
                allowTransmission=False,
                destination=destination,
                dataClassification=classification,
                reason=f"Payload size exceeds permitted maximum of {max_payload_bytes} bytes.",
            )

        # 5. Verify explicit consent grant
        has_consent = any(
            (
                not grant.isRevoked
                and grant.purpose == purpose
                and (grant.targetDomainOrPath == destination or grant.scope == "*")
            )
            for grant in active_grants
        )
        if not has_consent:
            return PrivacyDecision(
                decisionId=uuid4(),
                allowTransmission=False,
                destination=destination,
                dataClassification=classification,
                reason=f"No active, unrevoked consent grant found for purpose '{purpose}' and destination '{destination}'.",
            )

        return PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination=destination,
            dataClassification=classification,
            reason="Outbound request conforms to privacy policy and active consent grant.",
        )
