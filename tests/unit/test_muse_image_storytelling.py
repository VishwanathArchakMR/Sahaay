"""Unit tests for Meta Muse Image generation, visual storytelling, and vector fallback."""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sahaay_core.models.meta.muse_image import MuseImageClient


@pytest.fixture
def temp_artifacts_dir(tmp_path: Path) -> Path:
    img_dir = tmp_path / "artifacts" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    return img_dir


@pytest.mark.asyncio
async def test_muse_image_status_when_unconfigured():
    client = MuseImageClient(api_key="")
    assert client.is_configured is False
    status = await client.check_connectivity()
    assert status["configured"] is False
    assert status["status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_muse_image_local_vector_svg_fallback(temp_artifacts_dir):
    client = MuseImageClient(api_key="", artifacts_dir=temp_artifacts_dir)

    result = await client.generate_step_illustration(
        task_id="task-123",
        step_id="step-1",
        milestone_type="source_ingest",
        direction="Browser → Desktop",
    )

    assert result.is_ai_generated is False
    assert result.svg_fallback is not None
    assert "<svg" in result.svg_fallback
    assert "Source Ingestion" in result.svg_fallback
    assert result.image_url is None


@pytest.mark.asyncio
async def test_muse_image_prompt_minimization():
    client = MuseImageClient(api_key="meta-test-key")
    sensitive_context = (
        "User account Aarav Sharma password123 secret PIN 9988 balance 50,000"
    )

    prompt = client._build_minimized_prompt(
        milestone_type="transfer",
        direction="Browser → Desktop",
        context=sensitive_context,
    )

    # Prompt minimization invariant: NEVER include raw credentials, PII or sensitive text
    assert "password123" not in prompt
    assert "Aarav Sharma" not in prompt
    assert "9988" not in prompt
    assert "Browser → Desktop" in prompt
    assert "glassmorphic" in prompt.lower() or "pipeline" in prompt.lower()


@pytest.mark.asyncio
async def test_muse_image_mock_api_success(temp_artifacts_dir):
    client = MuseImageClient(api_key="meta-test-key", artifacts_dir=temp_artifacts_dir)

    # Minimal 1x1 valid PNG in base64
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    with patch.object(client.privacy_gateway, "evaluate_outbound_request") as mock_eval:
        from sahaay_core.contracts.models import DataClassificationEnum, PrivacyDecision

        mock_eval.return_value = PrivacyDecision(
            decisionId=uuid4(),
            allowTransmission=True,
            destination=client.base_url,
            dataClassification=DataClassificationEnum.INTERNAL,
            reason="Authorized",
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"data": [{"b64_json": tiny_png_b64}]},
            )

            result = await client.generate_step_illustration(
                task_id="task-art-1",
                step_id="step-art-1",
                milestone_type="verify",
                direction="Browser → Desktop",
            )

            assert result.is_ai_generated is True
            assert result.image_url is not None
            assert result.file_size_bytes > 0
            assert (temp_artifacts_dir / f"{result.artifact_id}.png").exists()


@pytest.mark.asyncio
async def test_muse_image_artifact_deletion(temp_artifacts_dir):
    client = MuseImageClient(api_key="test-key", artifacts_dir=temp_artifacts_dir)

    # Create dummy artifact files
    (temp_artifacts_dir / "art-abc123456789.png").write_bytes(b"dummy image data")
    (temp_artifacts_dir / "art-def123456789.png").write_bytes(b"dummy image data")

    assert len(list(temp_artifacts_dir.glob("art-*.png"))) == 2
    deleted = client.delete_task_artifacts("task-123")
    assert deleted == 2
    assert len(list(temp_artifacts_dir.glob("art-*.png"))) == 0
