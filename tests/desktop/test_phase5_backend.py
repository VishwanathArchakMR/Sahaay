import json
import urllib.error
import urllib.request

__test__ = False


def _send_request(name, method, url, headers=None, data=None):
    print(f"\n--- Testing: {name} ---")
    print(f"Request: {method} {url}")
    req_headers = headers or {}
    print(f"Headers: {req_headers}")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            resp_headers = dict(response.info())
            print(f"Status: {status_code}")
            print(f"Response: {body[:300]}")
            return status_code, body, resp_headers
    except urllib.error.HTTPError as he:
        status_code = he.code
        body = he.read().decode("utf-8")
        resp_headers = dict(he.info())
        print(f"HTTP Error {status_code}: {body}")
        return status_code, body, resp_headers
    except Exception as exc:
        print(f"Network/Connection Exception: {exc}")
        return 0, str(exc), {}


def main():
    # 1. Health request
    code, body, _ = _send_request(
        "1. Health Endpoint", "GET", "http://127.0.0.1:8000/api/v1/health"
    )
    assert code == 200, f"Expected 200, got {code}"

    # Read the token written to disk
    import os
    from pathlib import Path

    token_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Sahaay" / "auth.token"
    token = token_path.read_text(encoding="utf-8").strip() if token_path.is_file() else ""
    print(f"\n[Auth] Discovered auth token from disk: {token[:8]}... (length: {len(token)})")

    # 2. Session creation (with token)
    sess_payload = json.dumps({"sessionName": "test-live-session"}).encode("utf-8")
    code, body, _ = _send_request(
        "2. Session Creation",
        "POST",
        "http://127.0.0.1:8000/api/v1/sessions",
        headers={"Content-Type": "application/json", "X-Sahaay-Token": token},
        data=sess_payload,
    )
    assert code in (200, 201), f"Expected 200/201, got {code}"
    sess_data = json.loads(body)
    session_id = sess_data.get("sessionId")
    print(f"Created Session ID: {session_id}")

    # 3. Extension-origin CORS preflight
    ext_origin = "chrome-extension://fnlhiookeiehboleaohdmpigdiodheda"
    code, body, cors_headers = _send_request(
        "3. Extension-Origin CORS Preflight",
        "OPTIONS",
        "http://127.0.0.1:8000/api/v1/health",
        headers={
            "Origin": ext_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Sahaay-Token",
        },
    )
    print(
        "CORS Allow-Origin:",
        cors_headers.get("access-control-allow-origin")
        or cors_headers.get("Access-Control-Allow-Origin"),
    )

    # 4. Authenticated browser request from extension origin
    code, body, _ = _send_request(
        "4. Authenticated Browser Request (Models Status)",
        "GET",
        "http://127.0.0.1:8000/api/v1/models/status",
        headers={"Origin": ext_origin, "X-Sahaay-Token": token},
    )
    assert code == 200, f"Expected 200, got {code}"

    # 5. Browser observation endpoint
    code, body, _ = _send_request(
        "5. Browser Active Observation Endpoint",
        "GET",
        "http://127.0.0.1:8000/api/v1/browser/active-observation",
        headers={"Origin": ext_origin, "X-Sahaay-Token": token},
    )
    assert code == 200, f"Expected 200, got {code}"
    print(f"Browser active-observation: {body}")

    # 6. Browser ingest observation endpoint
    obs_payload = json.dumps(
        {
            "url": "https://example.com/live-test",
            "title": "Example Live Webpage",
            "scrollPosition": {"x": 0, "y": 0},
            "documentDimensions": {"width": 1280, "height": 800},
            "visibleTextExcerpt": "This is a real live browser observation captured by the Sahaay test agent.",
        }
    ).encode("utf-8")
    code, body, _ = _send_request(
        "6. Ingest Tab Observation Endpoint",
        "POST",
        "http://127.0.0.1:8000/api/v1/browser/observe",
        headers={"Content-Type": "application/json", "Origin": ext_origin, "X-Sahaay-Token": token},
        data=obs_payload,
    )
    assert code == 200, f"Expected 200, got {code}"
    print(f"Ingested observation result: {body}")


if __name__ == "__main__":
    main()
