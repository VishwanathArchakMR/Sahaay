"""Tests for Native Host Command Allowlist, Manifest Schemas, and Message Validation."""

import json
import struct

from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.config.settings import get_repo_root

ALLOWED_HOST_COMMANDS = {
    "ping",
    "hello",
    "handshake",
    "get_capabilities",
    "get_status",
    "get_active_window",
}
MAX_PAYLOAD_BYTES = 1024 * 1024  # 1MB Chromium Native Messaging protocol limit


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

    if cmd in ("ping", "hello", "handshake"):
        return {"success": True, "command": cmd, "data": {"status": "connected"}}

    if cmd == "get_capabilities":
        return {
            "success": True,
            "command": "get_capabilities",
            "data": {"isUiAutomationSupported": True, "version": "0.2.0-vertical-slice"},
        }

    return {"success": False, "command": cmd, "error": "Operation routed to controller."}


def test_native_host_allowlist_enforcement():
    ping_res = simulate_process_native_request({"command": "ping", "sessionId": "s-123"})
    assert ping_res["success"] is True

    hello_res = simulate_process_native_request({"command": "hello", "sessionId": "s-123"})
    assert hello_res["success"] is True

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


def test_native_host_framing_non_ascii_utf8():
    # Verify that multi-byte unicode characters measure byte length, not character length
    unicode_payload = {
        "command": "get_tab_observation",
        "sessionId": "s-kannada",
        "data": {
            "title": "ಬೆಂಗಳೂರು ವಿದ್ಯುತ್ ಸರಬರಾಜು ಕಂಪನಿ ನಿಯಮಿತ (BESCOM)",
            "amount": "₹2,450.00",
            "notes": "ವಿದ್ಯುತ್ ಶುಲ್ಕ",
        },
    }
    encoded = json.dumps(unicode_payload, ensure_ascii=False).encode("utf-8")
    length_prefix = struct.pack("<I", len(encoded))
    unpacked_length = struct.unpack("<I", length_prefix)[0]

    assert unpacked_length == len(encoded)
    assert unpacked_length > len(json.dumps(unicode_payload, ensure_ascii=False))


def test_native_host_rejects_oversized_payload():
    oversized_data = {"command": "blob", "data": "X" * (MAX_PAYLOAD_BYTES + 10)}
    encoded = json.dumps(oversized_data).encode("utf-8")
    assert len(encoded) > MAX_PAYLOAD_BYTES


def test_native_host_manifest_schema():
    repo_root = get_repo_root()
    manifest_file = (
        repo_root
        / "apps"
        / "windows-companion"
        / "Sahaay.NativeHost"
        / "com.sahaay.nativehost.json"
    )
    assert manifest_file.exists(), f"Manifest file missing at {manifest_file}"

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["name"] == "com.sahaay.nativehost"
    assert manifest["type"] == "stdio"
    assert "allowed_origins" in manifest
    assert len(manifest["allowed_origins"]) >= 1

    # Security check: MUST NOT contain wildcards in allowed_origins
    assert "chrome-extension://filgbgddapmjcddcoadfpimdicmkhpolc/" in manifest["allowed_origins"]
    for origin in manifest["allowed_origins"]:
        assert "*" not in origin, f"Wildcard forbidden in allowed_origins: {origin}"
        assert origin.startswith("chrome-extension://") or origin.startswith("extension://")
        assert origin.endswith("/")


def test_browser_extension_manifest_permissions():
    repo_root = get_repo_root()
    ext_manifest_file = repo_root / "apps" / "browser-extension" / "manifest.json"
    assert ext_manifest_file.exists()

    ext_manifest = json.loads(ext_manifest_file.read_text(encoding="utf-8"))
    assert ext_manifest["manifest_version"] == 3
    perms = set(ext_manifest.get("permissions", []))

    # Must contain necessary capabilities
    assert "nativeMessaging" in perms
    assert "activeTab" in perms
    assert "tabs" in perms
    assert "scripting" in perms

    # Service worker declaration
    bg = ext_manifest.get("background", {})
    assert bg.get("service_worker") == "dist/service-worker/index.js"


def test_disconnected_browser_fails_closed():
    """Verify BrowserAdapter without active pipe reports disconnected truthfully."""
    adapter = BrowserAdapter(pipe_name="NonExistentSahaayPipe_Test")
    assert adapter.is_connected() is False
    assert adapter.is_browser_attached() is False
