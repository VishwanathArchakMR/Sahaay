"""Integration tests for execute-goal general-purpose task flows."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_execute_goal_capabilities_introspection():
    """Verify system introspection accurately reports connected and unavailable components."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        # 1. Establish valid session first (requirement: no unauthorized sessions)
        session_res = await client.post("/api/v1/sessions", json={"localOnlyMode": True})
        assert session_res.status_code == 201
        session_id = session_res.json()["sessionId"]

        # 2. Execute general goal for capability introspection
        res = await client.post(
            "/api/v1/workflows/execute-goal",
            json={
                "sessionId": session_id,
                "goal": "Hello Sahaay. Explain which capabilities are actually available and identify which connected components are currently unavailable.",
                "workflowMode": "ask",
                "sourceSurface": "desktop",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["isVerified"] is True
        assert "CONNECTED & OPERATIONAL:" in data["summary"]
        assert "CURRENTLY UNAVAILABLE / AWAITING CONNECTION:" in data["summary"]
        assert "REGISTERED CAPABILITIES" in data["summary"]
        assert data["taskId"] is not None

        # 3. Verify task is durably persisted and queryable
        task_res = await client.get(f"/api/v1/tasks/{data['taskId']}")
        assert task_res.status_code == 200
        task_data = task_res.json()
        assert task_data["status"] == "COMPLETED"
        assert task_data["taskId"] == data["taskId"]


@pytest.mark.asyncio
async def test_execute_goal_document_retrieval():
    """Verify document retrieval extracts real invoice facts and generates cryptographic proof."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        # 1. Establish valid session
        session_res = await client.post("/api/v1/sessions", json={"localOnlyMode": True})
        assert session_res.status_code == 201
        session_id = session_res.json()["sessionId"]

        # 2. Execute document retrieval goal
        res = await client.post(
            "/api/v1/workflows/execute-goal",
            json={
                "sessionId": session_id,
                "goal": "Search recent invoices and summarize key facts",
                "workflowMode": "ask",
                "sourceSurface": "desktop",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["isVerified"] is True
        assert "INR 2,450.00" in data["summary"]
        assert "BLR-UTIL-98421" in data["summary"]
        assert data["taskId"] is not None

        # 3. Verify task persistence
        task_res = await client.get(f"/api/v1/tasks/{data['taskId']}")
        assert task_res.status_code == 200
        assert task_res.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_execute_goal_rejects_invalid_session():
    """Verify execute-goal strictly rejects non-existent session IDs."""
    transport = ASGITransport(app=app)
    unauthorized_id = str(uuid4())

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            "/api/v1/workflows/execute-goal",
            json={
                "sessionId": unauthorized_id,
                "goal": "Explain available capabilities",
                "workflowMode": "ask",
                "sourceSurface": "desktop",
            },
        )
        assert res.status_code == 404
        assert "Session not found" in res.json()["detail"]
