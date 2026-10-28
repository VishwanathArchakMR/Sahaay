"""Integration tests for Task Passport and visual storytelling API."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.api.v1.storytelling import register_or_update_passport
from sahaay_core.config.settings import settings
from sahaay_core.main import app


@pytest.fixture
def auth_headers() -> dict:
    return {"X-Sahaay-Token": settings.api_token}


@pytest.mark.asyncio
async def test_task_passport_registration_and_retrieval(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_id = f"task-pass-{uuid4().hex[:6]}"

        # 1. Register passport
        passport = register_or_update_passport(
            task_id=task_id,
            goal="Transfer utility bill data to desktop app",
            workflow_mode="combined_retrieval_and_action",
            direction="Browser Tab → Windows Application",
            extracted_fields={"account": "BLR-UTIL-98421", "amount": "INR 2,450.00"},
            verification_status="VERIFIED",
            evidence_id=f"ev-{task_id}",
            target_app_or_url="Notepad",
            source_ref="http://127.0.0.1:8000/fixtures/utility_bill.html",
        )

        assert passport.task_id == task_id
        assert len(passport.milestones) == 5

        # 2. Retrieve passport via API
        resp = await client.get(f"/api/v1/tasks/{task_id}/passport", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["taskId"] == task_id
        assert data["verificationStatus"] == "VERIFIED"
        assert data["totalMilestones"] == 5

        # Check milestones contain ordinary language titles and vector SVG fallbacks
        milestones = data["milestones"]
        assert milestones[0]["title"] == "Source Context Ingested"
        assert "<svg" in milestones[0]["svgFallback"]
        assert milestones[2]["title"] == "Action Gate Authorized"
        assert milestones[3]["title"] == "Cross-Surface Transfer: Browser Tab → Windows Application"
        assert milestones[4]["status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_explain_this_step_endpoint(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_id = f"task-explain-{uuid4().hex[:6]}"

        # Register passport first
        register_or_update_passport(
            task_id=task_id,
            goal="Form auto-fill demo",
            workflow_mode="combined_retrieval_and_action",
            direction="Local Document → Browser Form",
            extracted_fields={"amountDue": "2450.00"},
            verification_status="VERIFIED",
            evidence_id=f"ev-{task_id}",
            target_app_or_url="bill_pay_form.html",
            source_ref="invoice_data.json",
        )

        # Call Explain This Step
        payload = {
            "milestone_type": "transfer",
            "direction": "Local Document → Browser Form",
            "abstract_context": "Synthetic invoice transfer",
        }
        res = await client.post(
            f"/api/v1/tasks/{task_id}/steps/ms-{task_id}-4/illustrate",
            json=payload,
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["taskId"] == task_id
        assert "Vector" in data["aiLabel"] or "Muse Image" in data["aiLabel"]
        assert data["svgFallback"] is not None


@pytest.mark.asyncio
async def test_delete_task_visual_artifacts_endpoint(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_id = f"task-del-{uuid4().hex[:6]}"

        register_or_update_passport(
            task_id=task_id,
            goal="Test deletion",
            workflow_mode="combined_retrieval_and_action",
            direction="Browser → Desktop",
            extracted_fields={},
            verification_status="VERIFIED",
            evidence_id=f"ev-{task_id}",
            target_app_or_url="Notepad",
            source_ref="test",
        )

        del_res = await client.delete(f"/api/v1/tasks/{task_id}/artifacts", headers=auth_headers)
        assert del_res.status_code == 200
        data = del_res.json()
        assert data["success"] is True
        assert data["taskId"] == task_id


@pytest.mark.asyncio
async def test_models_status_reports_meta_models_and_muse_image(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/models/status", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()

        assert "metaHosted" in data
        assert data["metaHosted"]["models"]["museSpark"]["id"] == "muse-spark-1.3"
        assert "museImage" in data["metaHosted"]["models"]
        assert data["metaHosted"]["models"]["museImage"]["id"] == "muse-image-1.0"
        assert "visualStorytelling" in data
        assert data["visualStorytelling"]["enabled"] is True
