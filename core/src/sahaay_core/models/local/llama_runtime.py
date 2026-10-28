"""Local Llama Runtime and Lifecycle Manager.

Manages Llama 3.2 3B Instruct (Q4_K_M quantized GGUF) via llama.cpp llama-server.
Handles binary discovery, model path validation, process startup/shutdown bound to loopback 127.0.0.1,
hardware detection (RAM, GPU/VRAM vs CPU fallback), and health probes.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from sahaay_core.config.settings import settings

logger = logging.getLogger("sahaay.models.local_llama")


class LocalLlamaStatusEnum(str, Enum):
    """Accurate lifecycle state for local Llama runtime."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    MODEL_FILE_MISSING = "MODEL_FILE_MISSING"
    RUNTIME_MISSING = "RUNTIME_MISSING"
    STARTING = "STARTING"
    READY = "READY"
    RUNNING_INFERENCE = "RUNNING_INFERENCE"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class LocalHardwareProfile(dict):
    """Hardware assessment for on-device inference."""


class LocalLlamaRuntimeManager:
    """Manages the local llama-server process lifecycle."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        server_path: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 8080,
        context_size: int = 4096,
    ) -> None:
        self.model_path = model_path or settings.local_llama_model_path
        self.server_path = server_path or settings.llama_server_path
        self.host = host
        self.port = port
        self.context_size = context_size
        self._process: Optional[subprocess.Popen] = None
        self._status = LocalLlamaStatusEnum.NOT_CONFIGURED
        self._status_message = "Local model not configured."
        self._inspect_environment()

    @property
    def status(self) -> LocalLlamaStatusEnum:
        """Current verified runtime status."""
        return self._status

    @property
    def status_message(self) -> str:
        """Explanatory status message for UI."""
        return self._status_message

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status report of local runtime."""
        hw = self.detect_hardware()
        return {
            "status": self._status.value,
            "message": self._status_message,
            "isReady": self._status == LocalLlamaStatusEnum.READY,
            "modelPath": self.model_path or "Not configured",
            "serverBinary": self._find_llama_server() or "Missing",
            "serverHost": self.host,
            "port": self.port,
            "hardwareProfile": hw,
        }

    def _inspect_environment(self) -> None:
        """Inspect environment for model weights and llama-server binary."""
        # 1. Check server binary
        resolved_server = self._find_llama_server()
        if not resolved_server:
            self._status = LocalLlamaStatusEnum.RUNTIME_MISSING
            self._status_message = (
                "llama.cpp runtime (llama-server.exe) not found on PATH or configured settings."
            )
            return

        # 2. Check model file
        if not self.model_path:
            self._status = LocalLlamaStatusEnum.NOT_CONFIGURED
            self._status_message = "Model path not configured. Set SAHAAY_LOCAL_LLAMA_MODEL_PATH."
            return

        p = Path(self.model_path)
        if not p.is_file():
            self._status = LocalLlamaStatusEnum.MODEL_FILE_MISSING
            self._status_message = f"Model file '{p.name}' does not exist at configured path."
            return

        self._status = LocalLlamaStatusEnum.STOPPED
        self._status_message = f"Llama 3.2 3B Instruct GGUF ready to start ({p.name})."

    def _find_llama_server(self) -> Optional[str]:
        """Locate llama-server executable."""
        if self.server_path and Path(self.server_path).is_file():
            return self.server_path
        which_server = shutil.which("llama-server") or shutil.which("llama-server.exe")
        if which_server:
            return which_server
        # Check standard user local directories
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "llama.cpp" / "llama-server.exe",
            Path("C:/llama.cpp/llama-server.exe"),
        ]
        for c in candidates:
            if c.is_file():
                return str(c)
        return None

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect available RAM, CPU cores, and GPU capabilities for inference sizing."""
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()

        # Fallback profile
        profile: Dict[str, Any] = {
            "cpuCores": cpu_count,
            "recommendedContextSize": self.context_size,
            "accelerationBackend": "CPU",
            "gpuDetected": False,
        }

        # Check for NVIDIA GPU via nvidia-smi if available
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                res = subprocess.run(
                    [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split(",")
                    profile["gpuDetected"] = True
                    profile["gpuName"] = parts[0].strip()
                    profile["vram"] = parts[1].strip() if len(parts) > 1 else "Unknown"
                    profile["accelerationBackend"] = "CUDA"
            except Exception:
                pass

        return profile

    async def start_server(self) -> bool:
        """Start local llama-server bound to loopback 127.0.0.1."""
        server_bin = self._find_llama_server()
        if not server_bin or not self.model_path or not Path(self.model_path).is_file():
            self._inspect_environment()
            return False

        if self._process and self._process.poll() is None:
            # Already running
            self._status = LocalLlamaStatusEnum.READY
            return True

        self._status = LocalLlamaStatusEnum.STARTING
        self._status_message = "Starting llama.cpp server..."

        # Hardware profiling
        hw = self.detect_hardware()
        ngl = 28 if hw.get("accelerationBackend") == "CUDA" else 0

        cmd = [
            server_bin,
            "-m",
            str(Path(self.model_path).resolve()),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "-c",
            str(self.context_size),
            "-ngl",
            str(ngl),
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # Wait for server /health probe
            for _ in range(15):  # 15 seconds max wait
                await asyncio.sleep(1.0)
                if await self.check_health():
                    self._status = LocalLlamaStatusEnum.READY
                    self._status_message = (
                        f"Local Llama 3.2 3B active on http://{self.host}:{self.port}."
                    )
                    return True

            self._status = LocalLlamaStatusEnum.FAILED
            self._status_message = "llama-server process started but failed health check."
            return False

        except Exception as ex:
            self._status = LocalLlamaStatusEnum.FAILED
            self._status_message = f"Failed to launch llama-server: {ex}"
            return False

    async def check_health(self) -> bool:
        """Probe llama-server endpoint on loopback."""
        url = f"http://{self.host}:{self.port}/health"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=1.5)
                return res.status_code == 200
        except Exception:
            # Check /v1/models as fallback
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(f"http://{self.host}:{self.port}/v1/models", timeout=1.5)
                    return res.status_code == 200
            except Exception:
                return False

    def stop_server(self) -> None:
        """Terminate the local inference process cleanly."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            finally:
                self._process = None

        self._status = LocalLlamaStatusEnum.STOPPED
        self._status_message = "Local Llama server stopped."


# Global singleton manager
local_llama_manager = LocalLlamaRuntimeManager()
