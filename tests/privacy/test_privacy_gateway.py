"""Tests for Privacy Gateway Fail-Closed Behavior."""

from sahaay_core.contracts.models import DataClassificationEnum
from sahaay_core.privacy.privacy_gateway import PrivacyGateway


def test_privacy_gateway_local_only_mode_fails_closed():
    gateway = PrivacyGateway(local_only_mode=True)
    decision = gateway.evaluate_outbound_request(
        destination="https://api.external-ai.com/v1/chat",
        purpose="Text summarization",
        content="Summarize this innocuous meeting note.",
        active_grants=[],
    )
    assert decision.allowTransmission is False
    assert "local-only mode is active" in decision.reason.lower()


def test_privacy_gateway_data_classification():
    gateway = PrivacyGateway()
    # Credential classification
    assert (
        gateway.classify_data("Authorization: Bearer sk-1234567890abcdef")
        == DataClassificationEnum.CREDENTIAL
    )
    assert (
        gateway.classify_data("my db password is SecretPass123!")
        == DataClassificationEnum.CREDENTIAL
    )

    # PII classification
    assert (
        gateway.classify_data("contact patient at test.user@hospital.org")
        == DataClassificationEnum.SENSITIVE_PII
    )
    assert (
        gateway.classify_data("call emergency contact at 555-123-4567")
        == DataClassificationEnum.SENSITIVE_PII
    )

    # Public / Internal
    assert (
        gateway.classify_data("The quick brown fox jumps over the lazy dog.")
        == DataClassificationEnum.INTERNAL
    )
    assert gateway.classify_data("") == DataClassificationEnum.PUBLIC


def test_privacy_gateway_blocks_credentials_even_with_consent():
    gateway = PrivacyGateway(local_only_mode=False)
    # Even if destination were allowlisted, credentials must fail closed
    decision = gateway.evaluate_outbound_request(
        destination="https://api.baseten.co/v1",
        purpose="Inference",
        content="api_key=secret_live_key_xyz",
        active_grants=[],
    )
    assert decision.allowTransmission is False
    assert decision.dataClassification == DataClassificationEnum.CREDENTIAL
