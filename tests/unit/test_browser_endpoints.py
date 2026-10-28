"""Unit tests for Browser Bridge endpoints: observation and verified action execution."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.api.v1.tasks import orchestrator
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_ingest_tab_observation():
    """Verify real observation ingestion into context store and source registration."""
    transport = ASGITransport(app=app)
    obs_payload = {
        "url": "https://developer.mozilla.org/en-US/docs/Web/API",
        "title": "Web APIs | MDN",
        "scrollPosition": {"x": 0, "y": 150},
        "documentDimensions": {"width": 1280, "height": 3400},
        "visibleTextExcerpt": "Web APIs are typically used with JavaScript, although this doesn't always have to be the case.",
        "accessibleElements": [
            {
                "tag": "a",
                "role": "link",
                "text": "References",
                "href": "https://developer.mozilla.org/references",
            },
            {"tag": "button", "role": "button", "text": "Search", "href": None},
        ],
    }
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post("/api/v1/browser/observe", json=obs_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["url"] == obs_payload["url"]
        assert "sourceId" in data
        assert data["observation"]["url"] == obs_payload["url"]


@pytest.mark.asyncio
async def test_execute_and_verify_scroll_action_success():
    """Verify bounded scroll proposal passes Action Gate and independent verifier."""
    transport = ASGITransport(app=app)
    # Create task
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Scroll down 300px in documentation",
    )

    scroll_req = {
        "sessionId": str(task.sessionId),
        "taskId": str(task.taskId),
        "stepId": str(uuid4()),
        "url": "https://developer.mozilla.org/en-US/docs/Web/API",
        "requestedDeltaY": 300,
        "preScrollY": 100,
        "postScrollY": 400,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post("/api/v1/browser/action/scroll", json=scroll_req)
        assert res.status_code == 200
        data = res.json()
        assert data["authorized"] is True
        assert data["policyDecision"] == "ALLOW"
        assert data["verificationStatus"] == "VERIFIED"
        assert data["actualDeltaY"] == 300
        assert "evidenceId" in data


@pytest.mark.asyncio
async def test_execute_scroll_action_detected_conflict():
    """Verify scroll action with zero movement results in CONFLICT status."""
    transport = ASGITransport(app=app)
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Scroll down 300px",
    )

    scroll_req = {
        "sessionId": str(task.sessionId),
        "taskId": str(task.taskId),
        "stepId": str(uuid4()),
        "url": "https://example.com",
        "requestedDeltaY": 300,
        "preScrollY": 200,
        "postScrollY": 200,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        # Ingest tab observation for example.com first
        await client.post(
            "/api/v1/browser/observe",
            json={
                "url": "https://example.com",
                "title": "Example Domain",
                "scrollPosition": {"x": 0, "y": 200},
                "documentDimensions": {"width": 800, "height": 600},
                "visibleTextExcerpt": "Example Domain text",
            },
        )
        res = await client.post("/api/v1/browser/action/scroll", json=scroll_req)
        assert res.status_code == 200
        data = res.json()
        assert data["authorized"] is True
        assert data["verificationStatus"] == "CONFLICT"
        assert data["actualDeltaY"] == 0


@pytest.mark.asyncio
async def test_execute_scroll_action_cancelled_task_denied():
    """Verify Action Gate denies action execution if task is cancelled."""
    transport = ASGITransport(app=app)
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Scroll down",
    )
    # Cancel task
    orchestrator.cancel_task(task.taskId)

    scroll_req = {
        "sessionId": str(task.sessionId),
        "taskId": str(task.taskId),
        "stepId": str(uuid4()),
        "url": "https://example.com",
        "requestedDeltaY": 300,
        "preScrollY": 100,
        "postScrollY": 400,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post("/api/v1/browser/action/scroll", json=scroll_req)
        assert res.status_code == 200
        data = res.json()
        assert data["authorized"] is False
        assert data["policyDecision"] == "DENY"
        assert "cancelled" in data["reason"].lower()
