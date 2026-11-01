import json
import os
import struct
import subprocess
import sys


def main():
    exe = os.path.expandvars(r"%LOCALAPPDATA%\Sahaay\native-host\Sahaay.NativeHost.exe")
    print(f"Testing executable: {exe}")
    if not os.path.isfile(exe):
        print(f"FAIL: File does not exist at {exe}")
        sys.exit(1)

    req = {
        "id": "test-req-12345",
        "command": "hello",
        "sessionId": "test-session",
        "payload": {"extensionId": "fnlhiookeiehboleaohdmpigdiodheda"},
    }
    body = json.dumps(req).encode("utf-8")
    frame = struct.pack("<I", len(body)) + body

    proc = subprocess.Popen(
        [exe, "chrome-extension://fnlhiookeiehboleaohdmpigdiodheda/"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        out, err = proc.communicate(input=frame, timeout=5)
        print(f"Exit code: {proc.returncode}")
        print(f"Stderr: {err.decode('utf-8', errors='replace').strip()}")
        print(f"Raw stdout length: {len(out)} bytes")

        if len(out) < 4:
            print("FAIL: stdout received fewer than 4 bytes.")
            sys.exit(1)

        resp_len = struct.unpack("<I", out[:4])[0]
        print(f"Framed response length: {resp_len}")
        resp_body = out[4 : 4 + resp_len].decode("utf-8")
        print(f"Response JSON: {resp_body}")

        parsed = json.loads(resp_body)
        print(f"Parsed keys: {list(parsed.keys())}")

        assert parsed.get("id") == "test-req-12345", f"ID mismatch: got {parsed.get('id')}"
        assert parsed.get("success") is True, f"Success is false: {parsed}"
        assert parsed.get("command") == "hello", f"Command mismatch: {parsed.get('command')}"
        data = parsed.get("data", {})
        assert data.get("status") == "connected", f"Status not connected: {data}"
        print("PASS: NativeHost protocol verified successfully in isolation!")
        sys.exit(0)
    except Exception as exc:
        print(f"FAIL: Exception during test: {exc}")
        if proc.poll() is None:
            proc.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()

