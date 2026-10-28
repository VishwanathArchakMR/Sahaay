"""Unit Tests for Local Llama 3.2 3B Instruct Q4_K_M GGUF Runtime."""

import pytest
from sahaay_core.models.local.client import LocalLlamaClient
from sahaay_core.models.local.llama_runtime import LocalLlamaRuntimeManager


def test_hardware_profiling_and_backend_detection():
    """Verify hardware profiler inspects real host specs and selects appropriate backend."""
    manager = LocalLlamaRuntimeManager()
    profile = manager.detect_hardware()

    assert profile["cpuCores"] > 0
    assert profile["accelerationBackend"] in ("CUDA", "CPU")
    assert "recommendedContextSize" in profile


def test_local_llama_status_reporting():
    """Verify Local Llama runtime truthfully reports model/runtime missing states."""
    manager = LocalLlamaRuntimeManager(
        model_path="C:/nonexistent/path/llama-3.2-3b-instruct-q4_k_m.gguf",
        server_path="C:/nonexistent/path/llama-server.exe",
    )
    status_report = manager.get_status()

    # Truthful reporting requirement: Must report missing weights/runtime, not simulated success
    assert status_report["status"] in (
        "MODEL_FILE_MISSING",
        "RUNTIME_MISSING",
        "NOT_CONFIGURED",
    )
    assert status_report["isReady"] is False
    assert status_report["serverHost"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_local_llama_client_status_and_contracts():
    """Verify LocalLlamaClient exposes typed status and handles unavailable server safely."""
    client = LocalLlamaClient()
    status_info = client.get_status()

    assert "status" in status_info
    assert "hardwareProfile" in status_info
    assert status_info["isReady"] is False
