"""Model Capability Router Unit Tests.

Verifies the layered model capability routing hierarchy:
    Deterministic Logic -> Local Llama -> Meta Muse Spark / Wonder -> Specialized Models
And strict proposal validation against the Central Capability Registry.
"""

from unittest.mock import MagicMock

import pytest
from sahaay_core.capabilities.models import CapabilityDescriptor
from sahaay_core.capabilities.registry import capability_registry
from sahaay_core.contracts.models import ActionTypeEnum
from sahaay_core.models.router import (
    ModelCapabilityRouter,
    ModelTier,
)


@pytest.fixture
def mock_router():
    meta_mock = MagicMock()
    meta_mock.is_configured = True

    spark_mock = MagicMock()
    wonder_mock = MagicMock()
    voice_mock = MagicMock()
    sam_mock = MagicMock()
    image_mock = MagicMock()
    local_mock = MagicMock()

    router = ModelCapabilityRouter(
        meta_client=meta_mock,
        spark_client=spark_mock,
        wonder_client=wonder_mock,
        voice_client=voice_mock,
        sam_client=sam_mock,
        image_client=image_mock,
        local_client=local_mock,
    )
    return router


def test_route_voice_transcription(mock_router):
    decision = mock_router.route_task("Please transcribe audio recording from mic")
    assert decision.selected_tier == ModelTier.META_MUSE_VOICE
    assert decision.is_live_call is True
    assert decision.requires_network is True


def test_route_sam_grounding(mock_router):
    decision = mock_router.route_task("Find bounding box and segment the submit button on screen")
    assert decision.selected_tier == ModelTier.META_SAM_GROUNDING
    assert decision.is_live_call is True


def test_route_creative_image_generation(mock_router):
    decision = mock_router.route_task("Generate illustration in retro style")
    assert decision.selected_tier == ModelTier.META_MUSE_IMAGE
    assert decision.is_live_call is True


def test_route_desktop_computer_use(mock_router):
    decision = mock_router.route_task("Control desktop window and click save button in UIA")
    assert decision.selected_tier == ModelTier.META_MUSE_WONDER
    assert decision.is_live_call is True


def test_route_general_semantic_planning(mock_router):
    decision = mock_router.route_task("Search for latest updates on project and summarize findings")
    assert decision.selected_tier == ModelTier.META_MUSE_SPARK
    assert decision.is_live_call is True


def test_route_local_only_enforcement(mock_router):
    decision = mock_router.route_task(
        "Analyze confidential source file",
        local_only_override=True,
    )
    assert decision.selected_tier in (ModelTier.LOCAL_LLAMA, ModelTier.DETERMINISTIC_LOGIC)
    assert decision.requires_network is False


def test_proposal_validation_registered_tool(mock_router):
    # Register temporary test capability
    test_cap = CapabilityDescriptor(
        capability_id="test_calculator_add",
        name="Calculator Addition",
        description="Adds two numbers",
        supported_surfaces=["desktop"],
        adapter="system",
        verification_method="return_value",
        action_type=ActionTypeEnum.DETERMINISTIC_RETRIEVAL.value,
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        executor="test_executor",
    )
    capability_registry.register(test_cap)

    # Valid proposal
    is_valid, err = mock_router.validate_model_proposal("test_calculator_add", {"a": 5, "b": 10})
    assert is_valid is True
    assert err is None

    # Missing required argument
    is_valid, err = mock_router.validate_model_proposal("test_calculator_add", {"a": 5})
    assert is_valid is False
    assert "missing required parameters" in err.lower()


def test_proposal_validation_unregistered_tool_rejected(mock_router):
    is_valid, err = mock_router.validate_model_proposal(
        "completely_hallucinated_tool_xyz", {"foo": "bar"}
    )
    assert is_valid is False
    assert "unregistered" in err.lower()
