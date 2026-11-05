"""Test CORS headers and preflight handling for installed browser extension origins."""

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.main import app

EXTENSION_ORIGIN = "chrome-extension://filgbgddapmjcddcoadfpimdicmkhpolc"


@pytest.mark.asyncio
async def test_extension_cors_preflight():
    """Verify that OPTIONS preflight request from installed extension succeeds with CORS headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.options(
            "/api/v1/health",
            headers={
                "Origin": EXTENSION_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Sahaay-Token,Content-Type",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == EXTENSION_ORIGIN
        assert "GET" in res.headers.get("access-control-allow-methods", "")


@pytest.mark.asyncio
async def test_extension_cors_health_get():
    """Verify that GET /health from installed extension origin returns 200 and databaseReady boolean."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.get("/api/v1/health", headers={"Origin": EXTENSION_ORIGIN})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == EXTENSION_ORIGIN
        data = res.json()
        assert data["status"] == "healthy"
        assert data["databaseReady"] is True
