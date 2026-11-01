import json
import os
import urllib.request
from pathlib import Path


def main():
    token = "dev-local-sahaay-token"
    try:
        token_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Sahaay" / "auth.token"
        if token_path.is_file():
            token = token_path.read_text(encoding="utf-8").strip() or token
    except Exception:
        pass
    headers = {"Content-Type": "application/json", "X-Sahaay-Token": token}

    # 1. Create a session
    sess_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/sessions",
        data=json.dumps({"sessionName": "phase7-notepad-live"}).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(sess_req) as resp:
        session = json.loads(resp.read().decode("utf-8"))
    session_id = session["sessionId"]
    print("Session created:", session_id)

    # 2. Grant consent for Windows set_control_text & launch_application
    for scope in ["set_control_text", "launch_application", "windows_native"]:
        grant_req = urllib.request.Request(
            f"http://127.0.0.1:8000/api/v1/sessions/{session_id}/grants",
            data=json.dumps({"scope": scope, "purpose": "Live Phase 7 acceptance test"}).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(grant_req) as resp:
                print(f"Granted consent for: {scope}")
        except Exception as e:
            print(f"Grant {scope} result: {e}")

    # 3. Ingest active tab observation
    obs_payload = {
        "url": "http://127.0.0.1:8000/fixtures/utility_bill.html",
        "title": "BESCOM Electricity Utility Bill - November 2026",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1280, "height": 800},
        "visibleTextExcerpt": "Consumer Name: Aarav Sharma\nAccount: BLR-UTIL-98421\nAmount Due: INR 2,450.00\nDue Date: Nov 15, 2026",
        "sessionId": session_id
    }
    obs_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/browser/observe",
        data=json.dumps(obs_payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(obs_req) as resp:
        print("Observation ingested:", resp.getcode())

    # 4. Execute Browser -> Desktop Workflow in Live Mode (isFixtureMode=False)
    b2d_payload = {
        "sessionId": session_id,
        "instruction": "Write the webpage summary into Notepad and verify the content.",
        "browserObservationExcerpt": obs_payload["visibleTextExcerpt"],
        "isFixtureMode": False
    }
    b2d_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/workflows/browser-to-desktop",
        data=json.dumps(b2d_payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    print("\n--- Executing Browser -> Desktop Cross-Surface Action ---")
    with urllib.request.urlopen(b2d_req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    print("Result Status:", result.get("status"))
    print("Is Verified:", result.get("isVerified"))
    print("Target HWND:", result.get("targetHwnd"))
    print("Task ID:", result.get("taskId"))
    print("Verification Details:", result.get("verification"))
    print("Evidence ID:", result.get("evidenceId"))
    if result.get("error"):
        print("Error:", result.get("error"))

    # 5. Retrieve Task Passport
    task_id = result.get("taskId")
    if task_id:
        pass_req = urllib.request.Request(f"http://127.0.0.1:8000/api/v1/tasks/{task_id}/passport", headers=headers)
        with urllib.request.urlopen(pass_req) as resp:
            passport = json.loads(resp.read().decode("utf-8"))
        print("\n--- Task Passport ---")
        print(f"Goal: {passport.get('goal')}")
        print(f"Total Milestones: {passport.get('totalMilestones')}")
        for m in passport.get("milestones", []):
            print(f"  [{m.get('status')}] {m.get('title')}: {m.get('description')}")

if __name__ == "__main__":
    main()
