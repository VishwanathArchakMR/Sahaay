"""Unit Tests for Meta Transport, SSL Validation, Truthful Reporting, and Secret Redaction."""

import io
import ssl
import wave
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sahaay_core.models.meta.meta_client import MetaClient
from sahaay_core.models.meta.muse_voice import (
    detect_audio_format,
    normalize_wav_for_meta,
)
from sahaay_core.models.meta.transport import (
    classify_meta_exception,
    create_meta_http_client,
    get_meta_ssl_context,
)


def test_meta_ssl_context_strict_security():
    """Verify get_meta_ssl_context enforces strict TLS verification and hostname checks."""
    ctx = get_meta_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_create_meta_http_client_factory():
    """Verify create_meta_http_client attaches the secure SSL context."""
    client = create_meta_http_client(timeout=15.0)
    assert isinstance(client, httpx.AsyncClient)
    assert client.timeout.connect == 15.0


def test_classify_meta_exception_tls_error():
    """Verify SSLCertVerificationError and CERTIFICATE_VERIFY_FAILED map to TLS_ERROR."""
    err = ssl.SSLCertVerificationError(
        "certificate verify failed: unable to get local issuer certificate"
    )
    category, msg = classify_meta_exception(err)
    assert category == "TLS_ERROR"
    assert "TLS certificate verification failed" in msg

    httpx_err = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)"
    )
    category, msg = classify_meta_exception(httpx_err)
    assert category == "TLS_ERROR"
    assert "TLS certificate verification failed" in msg


def test_classify_meta_exception_network_and_timeout():
    """Verify timeout and network disconnect errors are categorized truthfully."""
    timeout_err = httpx.ReadTimeout("The read operation timed out")
    cat, msg = classify_meta_exception(timeout_err)
    assert cat == "TIMEOUT_ERROR"

    net_err = httpx.ConnectError("[Errno 11001] getaddrinfo failed")
    cat, msg = classify_meta_exception(net_err)
    assert cat == "NETWORK_ERROR"


@pytest.mark.asyncio
async def test_meta_client_not_configured_truthful():
    """Verify check_connectivity truthfully returns NOT_CONFIGURED when API key is empty."""
    client = MetaClient(api_key="", base_url="https://api.meta.ai/v1")
    res = await client.check_connectivity()
    assert res["status"] == "NOT_CONFIGURED"
    assert res["isConfigured"] is False
    assert res["isHealthy"] is False
    assert res["diagnostics"]["credential"] == "Not Configured"
    assert "MODEL_API_KEY" in res["message"]


@pytest.mark.asyncio
async def test_meta_client_unauthorized_truthful():
    """Verify check_connectivity returns UNAUTHORIZED on HTTP 401 without exposing secret."""
    secret_key = "secret_meta_api_key_12345"
    client = MetaClient(api_key=secret_key, base_url="https://api.meta.ai/v1")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"message": f"Invalid key: {secret_key}"}}

    mock_http = AsyncMock()
    mock_http.get.return_value = mock_response

    res = await client.check_connectivity(client_override=mock_http)
    assert res["status"] == "UNAUTHORIZED"
    assert res["isHealthy"] is False
    assert res["tlsVerified"] is True
    # Secret redaction check
    assert secret_key not in res["message"]
    assert secret_key not in str(res)


@pytest.mark.asyncio
async def test_meta_client_model_unavailable_truthful():
    """Verify check_connectivity detects when requested model is missing from account catalogue."""
    client = MetaClient(api_key="valid_key", base_url="https://api.meta.ai/v1")

    # Catalogue returns other models but not muse-spark-1.3
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "some-other-model"}]}

    mock_http = AsyncMock()
    mock_http.get.return_value = mock_response

    res = await client.check_connectivity(client_override=mock_http)
    assert res["status"] == "MODEL_UNAVAILABLE"
    assert res["isHealthy"] is False
    assert res["catalogueVerified"] is True
    assert res["generationVerified"] is False


@pytest.mark.asyncio
async def test_meta_client_generation_verified():
    """Verify check_connectivity returns GENERATION_VERIFIED when all multi-stage probes succeed."""
    client = MetaClient(api_key="valid_key", base_url="https://api.meta.ai/v1")

    cat_resp = MagicMock(spec=httpx.Response)
    cat_resp.status_code = 200
    cat_resp.json.return_value = {
        "data": [
            {"id": "muse-spark-1.3"},
            {"id": "muse-wonder-1.0"},
            {"id": "muse-voice-transcribe-1.0"},
            {"id": "sam-3.1"},
        ]
    }

    gen_resp = MagicMock(spec=httpx.Response)
    gen_resp.status_code = 200
    gen_resp.json.return_value = {"choices": [{"message": {"content": "pong"}}]}

    asr_resp = MagicMock(spec=httpx.Response)
    asr_resp.status_code = 200
    asr_resp.json.return_value = {"transcript": "hello", "audioDurationMs": 200}

    sam_resp = MagicMock(spec=httpx.Response)
    sam_resp.status_code = 200
    sam_resp.json.return_value = {"status": "completed"}

    mock_http = AsyncMock()
    mock_http.get.return_value = cat_resp
    mock_http.post.side_effect = [gen_resp, gen_resp, gen_resp, asr_resp, sam_resp]

    res = await client.check_connectivity(client_override=mock_http)
    assert res["status"] == "GENERATION_VERIFIED"
    assert res["isHealthy"] is True
    assert res["generationVerified"] is True
    assert res["toolCallingVerified"] is True
    assert res["wonderVerified"] is True
    assert res["voiceVerified"] is True
    assert res["samVerified"] is True
    assert res["diagnostics"]["museSpark"] == "Generation Verified"


def test_audio_format_detection_and_wav_normalization():
    """Verify audio format detection and 16kHz mono WAV normalization."""
    # Test non-WAV detection
    webm_magic = b"\x1a\x45\xdf\xa3fake_webm"
    encoding, fname, mime = detect_audio_format(webm_magic)
    assert encoding == "WEBM_OPUS"

    # Create synthetic stereo 44.1kHz WAV buffer
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)  # stereo
        w.setsampwidth(2)  # 16-bit
        w.setframerate(44100)
        # 4410 frames = 0.1s
        w.writeframes(b"\x00\x00\x00\x00" * 4410)
    stereo_wav = buf.getvalue()

    encoding, fname, mime = detect_audio_format(stereo_wav)
    assert encoding == "WAV"

    # Normalize to 16kHz mono s16le
    mono_16k_wav = normalize_wav_for_meta(stereo_wav)
    with wave.open(io.BytesIO(mono_16k_wav), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
