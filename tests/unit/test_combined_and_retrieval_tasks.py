"""Unit tests for retrieval-only, action-only, and combined tasks with staleness checks."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.api.v1.sources import context_store, source_manager
from sahaay_core.api.v1.tasks import orchestrator
from sahaay_core.contracts.models import FactTypeEnum
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_retrieval_only_task_denies_computer_action():
    """Verify ActionGate strictly blocks computer/browser actions when task is declared retrieval_only."""
    transport = ASGITransport(app=app)
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Find due date on billing page",
        task_type="retrieval_only",
    )

    scroll_req = {
        "sessionId": str(task.sessionId),
        "taskId": str(task.taskId),
        "stepId": str(uuid4()),
        "url": "https://billing.example.com",
        "requestedDeltaY": 300,
        "preScrollY": 0,
        "postScrollY": 300,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post("/api/v1/browser/action/scroll", json=scroll_req)
        assert res.status_code == 200
        data = res.json()
        assert data["authorized"] is False
        assert data["policyDecision"] == "DENY"
        assert "retrieval-only" in data["reason"].lower()


@pytest.mark.asyncio
async def test_combined_task_satisfies_precondition_and_executes():
    """Verify combined workflow verifies retrieved fact before dispatching authorized scroll."""
    transport = ASGITransport(app=app)

    # 1. Ingest observation into context
    src = source_manager.register_source(
        source_type="browser_tab",
        uri="https://docs.example.com/api",
        title="API Reference",
    )
    context_store.record_fact(
        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
        content="The authentication endpoint requires OAuth2 with PKCE verification.",
        source_reference_id=src.sourceId,
    )

    # 2. Create combined task
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Check OAuth2 reference then scroll down to examples",
        task_type="combined_retrieval_and_action",
    )

    combined_req = {
        "sessionId": str(task.sessionId),
        "requiredKey": "OAuth2 with PKCE",
        "targetUrl": "https://docs.example.com/api",
        "scrollDeltaY": 300,
        "preScrollY": 0,
        "postScrollY": 300,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            f"/api/v1/tasks/{task.taskId}/combined/verify-and-scroll", json=combined_req
        )
        assert res.status_code == 200
        data = res.json()
        assert data["preconditionMet"] is True
        assert data["actionExecuted"] is True
        assert data["verificationStatus"] == "VERIFIED"
        assert data["status"] == "COMPLETED"
        assert "evidenceId" in data


@pytest.mark.asyncio
async def test_combined_task_skips_action_when_precondition_unmet():
    """Verify combined workflow safely skips computer action if required fact is absent."""
    transport = ASGITransport(app=app)
    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Verify nonexistent token then scroll",
        task_type="combined_retrieval_and_action",
    )

    combined_req = {
        "sessionId": str(task.sessionId),
        "requiredKey": "NONEXISTENT_SECRET_TOKEN_XYZ",
        "targetUrl": "https://docs.example.com/api",
        "scrollDeltaY": 300,
        "preScrollY": 0,
        "postScrollY": 300,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            f"/api/v1/tasks/{task.taskId}/combined/verify-and-scroll", json=combined_req
        )
        assert res.status_code == 200
        data = res.json()
        assert data["preconditionMet"] is False
        assert data["actionExecuted"] is False
        assert "not found" in data["reason"].lower()


@pytest.mark.asyncio
async def test_combined_task_conflicts_trigger_handoff():
    """Verify conflicting facts stop execution and transition task to HANDOFF_REQUESTED."""
    transport = ASGITransport(app=app)

    # Ingest conflicting fact
    src = source_manager.register_source(
        source_type="local_document",
        uri="C:\\data\\conflict_policy.txt",
        title="Conflicting Terms",
    )
    context_store.record_fact(
        fact_type=FactTypeEnum.CONFLICTING,
        content="Contradictory quota limit of 500 requests per minute.",
        source_reference_id=src.sourceId,
    )

    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Resolve quota and apply settings",
        task_type="combined_retrieval_and_action",
    )

    combined_req = {
        "sessionId": str(task.sessionId),
        "requiredKey": "quota limit",
        "targetUrl": "https://portal.example.com",
        "scrollDeltaY": 200,
        "preScrollY": 0,
        "postScrollY": 200,
    }

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            f"/api/v1/tasks/{task.taskId}/combined/verify-and-scroll", json=combined_req
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "HANDOFF_REQUESTED"
        assert data["actionExecuted"] is False
        assert "conflicting" in data["reason"].lower()


@pytest.mark.asyncio
async def test_browser_action_detects_stale_observation_on_navigation():
    """Verify action rejects with REOBSERVE if active browser tab navigates away."""
    transport = ASGITransport(app=app)

    # 1. Ingest tab observation for page A
    obs_a = {
        "url": "https://example.com/page-A",
        "title": "Page A",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1000, "height": 2000},
        "visibleTextExcerpt": "Welcome to Page A",
    }
    # 2. Tab navigates to page B
    obs_b = {
        "url": "https://example.com/page-B",
        "title": "Page B",
        "scrollPosition": {"x": 0, "y": 0},
        "documentDimensions": {"width": 1000, "height": 2000},
        "visibleTextExcerpt": "Navigated to Page B",
    }

    task = orchestrator.create_task(
        session_id=uuid4(),
        goal="Interact with Page A",
        task_type="action_only",
    )

    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        await client.post("/api/v1/browser/observe", json=obs_a)
        await client.post("/api/v1/browser/observe", json=obs_b)

        # Attempt to execute action targeting stale page A
        scroll_req = {
            "sessionId": str(task.sessionId),
            "taskId": str(task.taskId),
            "stepId": str(uuid4()),
            "url": "https://example.com/page-A",  # Stale target URL
            "requestedDeltaY": 300,
            "preScrollY": 0,
            "postScrollY": 300,
        }
        res = await client.post("/api/v1/browser/action/scroll", json=scroll_req)
        assert res.status_code == 200
        data = res.json()
        assert data["authorized"] is False
        assert data["policyDecision"] == "REOBSERVE"
        assert "navigated" in data["reason"].lower()
