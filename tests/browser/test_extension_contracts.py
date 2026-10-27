"""Tests for Browser Extension Message Schemas and Validation."""

import json

ALLOWED_COMMANDS = {
    "ping",
    "get_tab_metadata",
    "get_sanitized_dom",
    "check_authorization",
}
MAX_MESSAGE_BYTES = 1024 * 1024


def validate_message(raw_msg: dict) -> tuple[bool, str]:
    msg_str = json.dumps(raw_msg)
    if len(msg_str.encode("utf-8")) > MAX_MESSAGE_BYTES:
        return False, "Payload exceeds size limit."

    if "command" not in raw_msg or not isinstance(raw_msg["command"], str):
        return False, "Command required."

    if raw_msg["command"] not in ALLOWED_COMMANDS:
        return False, f"Command '{raw_msg['command']}' not allowed."

    if "sessionId" not in raw_msg or not isinstance(raw_msg["sessionId"], str):
        return False, "SessionId required."

    return True, "Valid"


def test_extension_message_allowlist():
    valid_msg = {"command": "ping", "sessionId": "sess-123"}
    ok, _ = validate_message(valid_msg)
    assert ok is True

    unknown_msg = {"command": "eval_arbitrary_js", "sessionId": "sess-123"}
    ok, err = validate_message(unknown_msg)
    assert ok is False
    assert "not allowed" in err


def test_extension_rejects_oversized_payload():
    oversized = {
        "command": "get_sanitized_dom",
        "sessionId": "sess-123",
        "large_blob": "A" * (MAX_MESSAGE_BYTES + 100),
    }
    ok, err = validate_message(oversized)
    assert ok is False
    assert "exceeds" in err
