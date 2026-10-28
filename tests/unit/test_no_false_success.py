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
