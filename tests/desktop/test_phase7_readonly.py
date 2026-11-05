import json
import os
import urllib.request
from pathlib import Path


def main():
    token_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Sahaay" / "auth.token"
    token = token_path.read_text(encoding="utf-8").strip() if token_path.is_file() else ""
    headers = {"Content-Type": "application/json", "X-Sahaay-Token": token}

    # 1. Create a session
    sess_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/sessions",
        data=json.dumps({"sessionName": "phase7-test"}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(sess_req) as resp:
        session = json.loads(resp.read().decode("utf-8"))
    session_id = session["sessionId"]
    print("Session created:", session_id)

    # 2. Ingest real webpage observation
    obs_data = {
        "url": "http://127.0.0.1:8000/fixtures/utility_bill.html",
        "title": "BESCOM Electricity Utility Bill - November 2026",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1280, "height": 800},
        "visibleTextExcerpt": "Consumer Name: Aarav Sharma\nAccount ID: BLR-UTIL-98421\nAmount Due: INR 2,450.00\nDue Date: Nov 15, 2026\nStatus: UNPAID",
        "sessionId": session_id,
    }
    obs_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/browser/observe",
        data=json.dumps(obs_data).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(obs_req) as resp:
        obs_res = json.loads(resp.read().decode("utf-8"))
    print("Observation ingested:", obs_res.get("success"), "Source ID:", obs_res.get("sourceId"))

    # 3. Test read-only goal: "Summarize the actual visible content of this webpage."
    goal_payload = {
        "goal": "Summarize the actual visible content of this webpage.",
        "sessionId": session_id,
        "sourceSurface": "browser",
        "workflowMode": "ask",
    }
    goal_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/workflows/execute-goal",
        data=json.dumps(goal_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(goal_req) as resp:
        goal_res = json.loads(resp.read().decode("utf-8"))
    print("\n--- Read-Only Goal Result ---")
    print("Status:", goal_res.get("status"))
    print("Is Verified:", goal_res.get("isVerified"))
    print("Task ID:", goal_res.get("taskId"))
    print("Summary:", goal_res.get("summary"))

    # 4. Check Task Passport for this task
    task_id = goal_res.get("taskId")
    pass_req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/v1/tasks/{task_id}/passport", headers=headers
    )
    with urllib.request.urlopen(pass_req) as resp:
        pass_res = json.loads(resp.read().decode("utf-8"))
    print("\n--- Task Passport ---")
    print("Total Milestones:", pass_res.get("totalMilestones"))
    for m in pass_res.get("milestones", []):
        print(f"  Milestone: {m.get('title')} [{m.get('status')}] - {m.get('description')[:60]}...")


if __name__ == "__main__":
    main()
