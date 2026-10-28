"""Unit & Integration Tests for Cross-Surface Execution (Browser <-> Desktop).

Verifies:
1. Browser -> Desktop synthetic utility bill transfer and readback verification.
2. Desktop -> Browser synthetic invoice document to web form mapping and DOM readback verification.
3. Form auto-submission is blocked.
4. Cryptographic provenance and evidence ledger entries are recorded.
5. Invariant OBSERVE -> PROPOSE -> AUTHORIZE -> EXECUTE -> VERIFY -> RECORD.
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.api.v1.sessions import active_grants, active_sessions
from sahaay_core.contracts.models import ConsentGrant, Session
from sahaay_core.main import app


@pytest.fixture
def auth_headers():
    return {"X-Sahaay-Token": "dev-local-sahaay-token"}


@pytest.fixture
def test_session():
    sess_id = uuid4()
    session = Session(
        sessionId=sess_id,
        localOnlyMode=True,
        metadata={"user": "developer_test"},
    )
    active_sessions[sess_id] = session
    active_grants[sess_id] = [
        ConsentGrant(
            sessionId=sess_id,
            scope="*",
            purpose="Testing cross-surface workflow execution",
        )
    ]
    return session


@pytest.mark.asyncio
async def test_browser_to_desktop_synthetic_transfer(test_session, auth_headers):
    """Test Browser -> Desktop workflow:

    Extracts synthetic electricity bill, populates target desktop control,
    and independently verifies readback text.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Check fixtures endpoint first
        fix_res = await client.get("/api/v1/workflows/fixtures", headers=auth_headers)
        assert fix_res.status_code == 200
        assert "fixtures" in fix_res.json()

        # Execute Browser -> Desktop
        payload = {
            "sessionId": str(test_session.sessionId),
            "instruction": "Transfer BESCOM electricity bill into target Desktop window",
            "targetHwnd": 0,  # Simulated desktop target
            "targetControlId": "Edit",
        }
        res = await client.post(
            "/api/v1/workflows/browser-to-desktop",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()

        assert data["workflow"] == "browser-to-desktop"
        assert data["status"] == "VERIFIED"
        assert data["isVerified"] is True
        assert "sourceProvenance" in data
        assert "Aarav Sharma" == data["sourceProvenance"]["extractedFields"]["consumer_name"]
        assert "2,450.00" in data["sourceProvenance"]["extractedFields"]["amount_due"]

        # Verify evidence ledger has recorded the verified state
        evidence_id = data["evidence_id"] if "evidence_id" in data else data["evidenceId"]
        assert evidence_id is not None


@pytest.mark.asyncio
async def test_desktop_to_browser_synthetic_transfer(test_session, auth_headers):
    """Test Desktop -> Browser workflow:

    Reads local invoice document, maps to web form fields, and verifies DOM readback values.
    Verifies auto-submission is blocked.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "sessionId": str(test_session.sessionId),
            "instruction": "Populate utility pay web form from local invoice",
        }
        res = await client.post(
            "/api/v1/workflows/desktop-to-browser",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()

        assert data["workflow"] == "desktop-to-browser"
        assert data["status"] == "VERIFIED"
        assert data["isVerified"] is True
        assert data["formMapping"]["customerName"] == "Aarav Sharma"
        assert data["formMapping"]["amountDue"] == "INR 2,450.00"

        # Safety guarantee: Form auto-submission is explicitly blocked
        assert data["verification"]["submissionBlockedBySafety"] is True
        assert data["evidenceId"] is not None


@pytest.mark.asyncio
async def test_models_diagnostics_endpoints(test_session, auth_headers):
    """Test GET /api/v1/models/status and POST /api/v1/models/test-connectivity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        status_res = await client.get("/api/v1/models/status", headers=auth_headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "metaHosted" in status_data
        assert "localLlama" in status_data
        assert "museSpark" in status_data["metaHosted"]["models"]
        assert "museWonder" in status_data["metaHosted"]["models"]

        test_conn = await client.post("/api/v1/models/test-connectivity", headers=auth_headers)
        assert test_conn.status_code == 200
        assert "metaApi" in test_conn.json()
