"""Controlled Project Code Execution Engine.

Executes Python scripts within authorized project workspaces using structured
process invocation (shell=False) to prevent arbitrary command injection.
Captures stdout, stderr, exit codes, execution duration, and cryptographic SHA-256
provenance hashes for the evidence ledger.
"""

import hashlib
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sahaay_core.config.settings import REPO_ROOT, settings

logger = logging.getLogger("sahaay.capabilities.code_runner")

# Permitted workspace root paths for code execution
ALLOWED_WORKSPACE_ROOTS = [
    Path(REPO_ROOT).resolve(),
    Path(settings.storage_dir).resolve(),
    Path(settings.artifacts_dir).resolve(),
    Path(os.path.expanduser("~")).resolve() / "Desktop",
    Path(os.path.expanduser("~")).resolve() / "Documents",
]


class CodeExecutionError(Exception):
    """Raised when code execution fails or violates safety boundaries."""


def is_path_in_allowed_workspace(target_path: Path) -> bool:
    """Check if target path is resolved within authorized workspace roots."""
    resolved = target_path.resolve()
    for root in ALLOWED_WORKSPACE_ROOTS:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def execute_python_script(
    script_path: Optional[str] = None,
    code: Optional[str] = None,
    workspace_path: Optional[str] = None,
    args: Optional[List[str]] = None,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Execute a Python script safely within an authorized workspace."""
    start_time = time.perf_counter()

    # 1. Resolve workspace root
    if workspace_path:
        ws_root = Path(workspace_path).resolve()
    else:
        ws_root = Path(REPO_ROOT) / "data" / "workspaces" / "default"
    ws_root.mkdir(parents=True, exist_ok=True)

    # 2. Determine target script file
    if code:
        # Write code to a managed script in the workspace
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]
        target_file = ws_root / f"script_{code_hash}.py"
        target_file.write_text(code, encoding="utf-8")
    elif script_path:
        target_file = Path(script_path)
        if not target_file.is_absolute():
            target_file = (ws_root / target_file).resolve()
        else:
            target_file = target_file.resolve()
    else:
        raise CodeExecutionError("Either 'code' or 'script_path' must be provided.")

    if not target_file.exists():
        raise CodeExecutionError(f"Script file does not exist: {target_file}")

    if not is_path_in_allowed_workspace(target_file):
        raise CodeExecutionError(
            f"Execution rejected: script path '{target_file}' is outside permitted project workspaces."
        )

    # 3. Compute cryptographic SHA-256 hash of script contents
    file_bytes = target_file.read_bytes()
    script_sha256 = hashlib.sha256(file_bytes).hexdigest()

    # 4. Structured invocation using current python runtime (zero shell injection)
    python_bin = sys.executable
    cmd: List[str] = [python_bin, str(target_file)]
    if args:
        cmd.extend(str(a) for a in args)

    bounded_timeout = max(1.0, min(float(timeout_seconds), 120.0))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(target_file.parent),
            capture_output=True,
            text=True,
            timeout=bounded_timeout,
            shell=False,
        )
        duration_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": proc.returncode == 0,
            "exitCode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "filePath": str(target_file),
            "scriptSha256": script_sha256,
            "durationMs": duration_ms,
            "driverProvenance": "real_python_subprocess",
        }
    except subprocess.TimeoutExpired as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": False,
            "exitCode": -1,
            "stdout": ex.stdout or "",
            "stderr": f"Execution timed out after {bounded_timeout:.1f}s",
            "filePath": str(target_file),
            "scriptSha256": script_sha256,
            "durationMs": duration_ms,
            "error": f"Script execution exceeded timeout of {bounded_timeout} seconds.",
            "driverProvenance": "real_python_subprocess",
        }
    except Exception as ex:
        duration_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": False,
            "exitCode": -1,
            "stdout": "",
            "stderr": str(ex),
            "filePath": str(target_file),
            "scriptSha256": script_sha256,
            "durationMs": duration_ms,
            "error": str(ex),
            "driverProvenance": "real_python_subprocess",
        }

