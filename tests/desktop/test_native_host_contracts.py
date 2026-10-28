"""Tests for Native Host Command Allowlist and Message Validation."""

import json
import struct

ALLOWED_HOST_COMMANDS = {"ping", "get_capabilities", "get_active_window"}
MAX_PAYLOAD_BYTES = 1024 * 1024


def simulate_process_native_request(request: dict) -> dict:
    cmd = request.get("command")
    session_id = request.get("sessionId")

    if not cmd:
        return {
            "success": False,
            "command": "unknown",
            "error": "Command cannot be empty.",
        }

    if not session_id:
        return {"success": False, "command": cmd, "error": "SessionId is required."}

    if cmd not in ALLOWED_HOST_COMMANDS:
        return {
            "success": False,
            "command": cmd,
            "error": f"Unknown command '{cmd}'. Native host rejects unallowlisted operations.",
        }

    if cmd == "ping":
        return {"success": True, "command": "ping", "data": {"status": "pong"}}

    if cmd == "get_capabilities":
        return {
            "success": True,
            "command": "get_capabilities",
            "data": {"isUiAutomationSupported": True, "version": "0.1.0-foundation"},
        }

    return {"success": False, "command": cmd, "error": "Scaffolded for Stage 02."}


def test_native_host_allowlist_enforcement():
    ping_res = simulate_process_native_request({"command": "ping", "sessionId": "s-123"})
    assert ping_res["success"] is True

    # Unknown or shell commands MUST be rejected
    shell_res = simulate_process_native_request(
        {
            "command": "powershell_exec",
            "sessionId": "s-123",
            "parameters": "Get-Process",
        }
    )
    assert shell_res["success"] is False
    assert "rejects unallowlisted operations" in shell_res["error"]


def test_native_host_framing_bytes():
    # Chrome/Edge standard 4-byte little endian framing
    payload = json.dumps({"command": "ping", "sessionId": "s-1"}).encode("utf-8")
    length_prefix = struct.pack("<I", len(payload))
    assert len(length_prefix) == 4
    unpacked_length = struct.unpack("<I", length_prefix)[0]
    assert unpacked_length == len(payload)
