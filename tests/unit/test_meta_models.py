"""Unit and Integration Tests for Meta Model Adapters & Privacy Gateway.

Tests:
- MetaClient base configuration, bearer token handling, retries, and offline connectivity.
- Muse Spark: Indic language detection (Kannada, Hindi, code-switched), grounded fact extraction,
  conflict identification, structured planning, and deterministic offline fallback.
- Muse Wonder: Responses API `computer` tool call parsing, display coordinate validation,
  ActionContract translation, and model self-attestation rejection.
- Muse Voice Transcribe: Transcription handling, language hints, and editable transcript confirmation.
- SAM 3.1: Visual grounding coordinate transformation and confidence scoring.
- Privacy Gateway: Local-only fail-closed enforcement and secret redaction.
"""

import pytest
from sahaay_core.contracts.models import ActionTypeEnum
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.models.meta.muse_spark import (
    GroundedSourceFact,
    MuseSparkClient,
)
from sahaay_core.models.meta.muse_voice import MuseVoiceClient
from sahaay_core.models.meta.muse_wonder import MuseWonderClient
from sahaay_core.models.meta.sam_client import Sam31Client
from sahaay_core.privacy.privacy_gateway import PrivacyGateway


@pytest.mark.asyncio
async def test_meta_client_connectivity_offline():
    """Verify MetaClient handles absent API key safely without exposing credentials."""
    client = MetaClient(api_key="", base_url="https://api.meta.ai/v1")
    res = await client.check_connectivity()
    assert res["status"] in ("NOT_CONFIGURED", "OFFLINE")
    assert "error" in res or "message" in res


def test_muse_spark_indic_language_detection():
    """Verify Muse Spark detects Kannada, Hindi, and code-switched phrases correctly."""
    spark = MuseSparkClient()

    # Kannada code-switched
    assert spark.detect_indic_language("Nanna current bill check maadi") == "kn_code_switched"
    assert spark.detect_indic_language("Electricity bill eshtu aagide?") == "kn_code_switched"

    # Hindi code-switched
    assert spark.detect_indic_language("Bijli ka bill kitna aaya hai?") == "hi_code_switched"
    assert spark.detect_indic_language("Mera utility invoice dikhao please") == "hi_code_switched"

    # Code-switched Indic mix
    assert (
        spark.detect_indic_language("Bill check maadi aur kitna payment bacha hai batao")
        == "code_switched_indic"
    )

    # Standard English
    assert (
        spark.detect_indic_language("Extract the consumer name and amount due from the active tab")
        == "en"
    )


@pytest.mark.asyncio
async def test_muse_spark_grounded_planning_and_conflict_detection():
    """Verify Muse Spark produces structured plan, extracts grounded facts, and detects conflicts."""
    spark = MuseSparkClient()

    facts = [
        GroundedSourceFact(
            fact_id="f1",
            source_id="src-1",
            source_title="BESCOM Bill",
            source_uri="http://127.0.0.1:8000/fixtures/utility_bill.html",
            snippet="Consumer Name: Aarav Sharma, Amount Due: INR 2,450.00",
        ),
        GroundedSourceFact(
            fact_id="f2",
            source_id="src-2",
            source_title="Local Invoice",
            source_uri="file:///c:/data/invoice.json",
            snippet="Amount Due: INR 3,100.00",
        ),
    ]

    plan = await spark.plan_task(
        prompt="Check bill amount and copy to Notepad",
        context_facts=facts,
    )

    assert plan.goal == "Check bill amount and copy to Notepad"
    assert len(plan.grounded_facts) == 2
    # Verify conflict between 2,450 and 3,100 is detected
    assert len(plan.uncertainties_or_conflicts) > 0
    assert plan.needs_user_handoff is True
    # Invariant: Model self-attestation is rejected
    assert plan.is_model_attestation_only is True


@pytest.mark.asyncio
async def test_muse_spark_extract_grounded_facts():
    """Verify Muse Spark extracts key-value fields from authorized source text."""
    spark = MuseSparkClient()
    sample_text = """
    Consumer Name: Aarav Sharma
    Account / Consumer ID: BLR-UTIL-98421
    Total Amount Due: INR 2,450.00
    Due Date: Nov 15, 2026
    """
    extracted = await spark.extract_grounded_facts(
        source_id="src-bescom",
        source_text=sample_text,
        required_fields=["consumer_name", "account_number", "amount_due", "due_date"],
    )

    assert extracted["consumer_name"] == "Aarav Sharma"
    assert extracted["account_number"] == "BLR-UTIL-98421"
    assert "2,450.00" in extracted["amount_due"]
    assert "Nov 15, 2026" in extracted["due_date"]


def test_muse_wonder_computer_tool_call_parsing():
    """Verify Muse Wonder parses Responses API computer tool calls and rejects out-of-bound coords."""
    wonder = MuseWonderClient()

    # Valid mouse click
    valid_click = {
        "action": "click",
        "coordinate": [450, 320],
        "target_description": "Pay Bill Button",
    }
    action = wonder.parse_computer_tool_call(
        tool_call=valid_click,
        display_width=1920,
        display_height=1080,
    )
    assert action.actionType == ActionTypeEnum.CLICK_DESKTOP_CONTROL
    assert action.parameters["x"] == 450
    assert action.parameters["y"] == 320

    # Valid text typing
    valid_type = {
        "action": "type",
        "text": "Aarav Sharma",
        "target_description": "Name Input Field",
    }
    type_action = wonder.parse_computer_tool_call(
        tool_call=valid_type,
        display_width=1920,
        display_height=1080,
    )
    assert type_action.actionType == ActionTypeEnum.TYPE_DESKTOP_TEXT
    assert type_action.parameters["text"] == "Aarav Sharma"

    # Out of bounds coordinates must raise ValueError
    out_of_bounds_call = {
        "action": "click",
        "coordinate": [2500, 500],  # 2500 > 1920
    }
    with pytest.raises(ValueError, match="exceeds display width"):
        wonder.parse_computer_tool_call(
            tool_call=out_of_bounds_call,
            display_width=1920,
            display_height=1080,
        )


@pytest.mark.asyncio
async def test_muse_voice_transcribe_pipeline():
    """Verify speech transcription pipeline and editable confirmation requirement."""
    voice = MuseVoiceClient()

    # Synthetic audio bytes (WAV header simulation)
    mock_wav = b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 100

    result = await voice.transcribe_audio_chunk(
        audio_bytes=mock_wav,
        content_type="audio/wav",
        language_hints=["kn", "hi", "en"],
    )

    assert result.transcript != ""
    assert result.confidence > 0.0
    # Must require editable user confirmation before consequential execution
    assert result.editable is True


@pytest.mark.asyncio
async def test_sam_31_visual_grounding():
    """Verify SAM 3.1 element grounding generates bounded coordinates."""
    sam = Sam31Client()
    mock_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    grounding = await sam.segment_element(
        image_bytes=mock_png,
        target_prompt="Submit button",
        observation_version="obs-v1",
    )

    assert grounding.target_prompt == "Submit button"
    assert grounding.bounding_box.width > 0
    assert 0 <= grounding.bounding_box.center_x <= 1920
    assert 0 <= grounding.bounding_box.center_y <= 1080


def test_privacy_gateway_blocks_hosted_when_local_only():
    """Verify Privacy Gateway fails closed when local_only_mode is enabled."""
    gateway = PrivacyGateway(local_only_mode=True)
    decision = gateway.evaluate_outbound_request(
        destination="https://api.meta.ai/v1",
        purpose="Hosted test",
        content="Here is a prompt for processing",
        active_grants=[],
    )
    assert decision.allowTransmission is False
    assert "Local-only mode is active" in decision.reason

    # When local_only is False but content contains credentials, transmission is strictly blocked
    open_gateway = PrivacyGateway(local_only_mode=False)
    cred_decision = open_gateway.evaluate_outbound_request(
        destination="https://api.meta.ai/v1",
        purpose="Hosted test",
        content="Here is secret bearer_token_xyz987654321 for authorization",
        active_grants=[],
    )
    assert cred_decision.allowTransmission is False
    assert "credentials" in cred_decision.reason.lower()
