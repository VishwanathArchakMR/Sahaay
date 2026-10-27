"""Tests for Health and Capability Endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify /api/v1/health returns healthy status and system diagnostics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["systemVersion"] == "0.1.0-foundation"
        assert data["localOnlyMode"] is True
        assert data["databaseReady"] is True


@pytest.mark.asyncio
async def test_capabilities_endpoint_reports_only_implemented():
    """Verify capabilities endpoint reports only what is actually available in Stage 02."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        response = await client.get("/api/v1/capabilities")
        assert response.status_code == 200
        data = response.json()
        # In Build 02: Browser extension bridge is implemented
        assert data["browserAutomationAvailable"] is True
        # Desktop automation availability is dynamically determined by named pipe probe
        assert isinstance(data["desktopAutomationAvailable"], bool)
        # External models MUST remain empty in this stage
        assert data["modelsAvailable"] == []
        # Active capabilities must contain baseline mechanisms and new Stage 02 components
        active = data["activeCapabilities"]
        assert "action_gate_authorization" in active
        assert "privacy_gateway_fail_closed" in active
        assert "task_state_machine" in active
        assert "independent_verification_engine" in active
        assert "browser_tab_observation" in active
        assert "browser_bounded_scroll_action" in active
        assert "deterministic_source_grounded_retrieval" in active
