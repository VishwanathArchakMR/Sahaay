"""Regression tests ensuring no false-success paths exist in Sahaay workflows."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sahaay_core.api.v1.sessions import session_manager
from sahaay_core.api.v1.storytelling import register_or_update_passport
from sahaay_core.config.settings import settings
from sahaay_core.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-Sahaay-Token": settings.api_token}


def test_missing_task_passport_returns_404(test_client, auth_headers):
    """An unknown task ID must return 404 rather than fabricating a synthetic verified passport."""
    bogus_task_id = f"nonexistent-task-{uuid.uuid4()}"
    resp = test_client.get(f"/api/v1/tasks/{bogus_task_id}/passport", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_browser_to_desktop_live_mode_rejects_zero_hwnd(test_client, auth_headers):
    """In live execution (isFixtureMode=False), targetHwnd=0 must be rejected and fail verification."""
    session = session_manager.create_session()

    payload = {
        "sessionId": str(session.sessionId),
        "instruction": "Transfer bill to desktop",
        "targetHwnd": 0,
        "targetControlId": "Edit",
        "browserObservationExcerpt": "Consumer Name: Aarav Sharma\nAccount: BLR-UTIL-98421\nAmount: INR 2,450.00\nDue: Nov 15, 2026",
        "isFixtureMode": False,
    }
    resp = test_client.post(
        "/api/v1/workflows/browser-to-desktop", json=payload, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["isVerified"] is False
    assert "handle" in data.get("error", "").lower() or "target" in data.get("error", "").lower()


def test_browser_to_desktop_live_mode_requires_active_browser_observation(
    test_client, auth_headers
):
    """In live execution, if no browser observation exists for the session/tab, workflow must fail."""
    session = session_manager.create_session()

    payload = {
        "sessionId": str(session.sessionId),
        "instruction": "Transfer bill to desktop",
        "targetHwnd": 12345,
        "targetControlId": "Edit",
        "isFixtureMode": False,
    }
    resp = test_client.post(
        "/api/v1/workflows/browser-to-desktop", json=payload, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["isVerified"] is False
    assert "observation" in data.get("error", "").lower()


def test_action_gate_denial_does_not_auto_grant_wildcard(test_client, auth_headers):
    """Action Gate denial must stop execution, return HANDOFF, and NOT insert a wildcard grant."""
    session = session_manager.create_session()

    with patch("sahaay_core.policy.action_gate.ActionGate.evaluate") as mock_eval:
        from sahaay_core.contracts.models import PolicyDecision, PolicyDecisionEnum

        # Simulate policy denial
        mock_eval.return_value = PolicyDecision(
            decision=PolicyDecisionEnum.DENY,
            reason="Unapproved high risk operation without user consent",
            requiredGrantScope="desktop.form_fill",
            actionId=uuid.uuid4(),
        )

        payload = {
            "sessionId": str(session.sessionId),
            "instruction": "Populate form without permission",
            "isFixtureMode": True,
        }
        resp = test_client.post(
            "/api/v1/workflows/desktop-to-browser", json=payload, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "HANDOFF"

        # Verify no wildcard consent was added
        grants = session_manager.list_consent_grants(session.sessionId)
        assert not any(g.scope == "*" for g in grants)


def test_windows_companion_exception_produces_failed_status(test_client, auth_headers):
    """If the Windows driver throws an exception, workflow must fail and never simulate success."""
    session = session_manager.create_session()
    session_manager.grant_consent(
        session_id=session.sessionId,
        scope="set_control_text",
        purpose="Test Windows companion exception handling",
    )

    with patch(
        "sahaay_core.adapters.windows.adapter.WindowsNativeAdapter.set_control_text"
    ) as mock_write:
        mock_write.side_effect = RuntimeError("Windows UIA Driver Connection Severed")

        payload = {
            "sessionId": str(session.sessionId),
            "instruction": "Write to notepad",
            "targetHwnd": 99999,
            "browserObservationExcerpt": "Consumer Name: Aarav Sharma\nAccount: BLR-UTIL-98421\nAmount: INR 2,450.00\nDue: Nov 15, 2026",
            "isFixtureMode": False,
        }
        resp = test_client.post(
            "/api/v1/workflows/browser-to-desktop", json=payload, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAILED"
        assert data["isVerified"] is False


def test_generated_illustration_does_not_mutate_task_status(test_client, auth_headers):
    """Generating an illustration for a failed task step must never change the underlying task status."""
    task_id = f"task-failed-{uuid.uuid4().hex[:8]}"
    passport = register_or_update_passport(
        task_id=task_id,
        goal="Demonstrate failed step illustration",
        workflow_mode="combined_retrieval_and_action",
        direction="Browser → Desktop",
        extracted_fields={"amount": "2450.00"},
        verification_status="FAILED",
        evidence_id="ev-fail-123",
        target_app_or_url="notepad.exe",
        source_ref="https://example.com/bill",
    )
    assert passport.verification_status == "FAILED"

    # Illustrate a step
    payload = {
        "milestone_type": "source_ingest",
        "direction": "Browser → Desktop",
        "abstract_context": "Electricity bill",
        "session_id": "default",
    }
    resp = test_client.post(
        f"/api/v1/tasks/{task_id}/steps/ms-{task_id}-1/illustrate",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Retrieve passport and verify verification_status is still FAILED
    get_resp = test_client.get(f"/api/v1/tasks/{task_id}/passport", headers=auth_headers)
    assert get_resp.status_code == 200
    reloaded_passport = get_resp.json()
    assert reloaded_passport["verificationStatus"] == "FAILED"


def test_executor_resolves_downloads_folder_alias():
    """file_list_directory must resolve 'Downloads' alias to user's real Downloads directory."""
    import asyncio
    from pathlib import Path
    from sahaay_core.capabilities.executor import CapabilityExecutor
    from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
    from sahaay_core.adapters.browser.adapter import BrowserAdapter

    executor = CapabilityExecutor(
        windows_adapter=WindowsNativeAdapter(allow_simulation=True),
        browser_adapter=BrowserAdapter(allow_simulation=True),
    )
    res = asyncio.run(executor.execute("file_list_directory", {"path": "Downloads", "limit": 5}))
    assert res.get("success") is True
    downloads_path = str(Path.home() / "Downloads")
    assert res.get("directory") == downloads_path
    assert "summary" in res
    assert "items" in res
    assert "count" in res


def test_task_passport_preserves_summary_and_target_surface(test_client, auth_headers):
    """Task passport must persist and return exact summary and target without generic illustration notice."""
    task_id = f"task-passport-test-{uuid.uuid4().hex[:8]}"
    summary_text = "I opened YouTube and started playing jazz."
    passport = register_or_update_passport(
        task_id=task_id,
        goal="Play jazz on YouTube",
        workflow_mode="combined_retrieval_and_action",
        direction="Meta Muse Spark Function Calling",
        extracted_fields={"media_playback": True},
        verification_status="VERIFIED",
        evidence_id="ev-youtube-123",
        target_app_or_url="https://www.youtube.com",
        source_ref="Meta muse-spark-1.3",
        summary=summary_text,
    )
    assert passport.summary == summary_text
    assert passport.target_app_or_url == "https://www.youtube.com"

    # Fetch from API
    get_resp = test_client.get(f"/api/v1/tasks/{task_id}/passport", headers=auth_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["summary"] == summary_text
    assert data["targetAppOrUrl"] == "https://www.youtube.com"
    # Ensure no generic vector illustration text
    assert "Illustrations are generated as visual metaphors" not in str(data)
