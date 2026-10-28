"""Unit tests for Windows Controller API endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sahaay_core.main import app


@pytest.mark.asyncio
async def test_list_open_windows_offline():
    """Verify endpoint handles companion offline state gracefully."""
    transport = ASGITransport(app=app)
    with patch(
        "sahaay_core.api.v1.windows.adapter.list_open_windows",
        side_effect=ConnectionError("Pipe not found"),
    ):
        async with AsyncClient(transport=transport, base_url="http://testclient") as client:
            res = await client.get("/api/v1/windows")
            assert res.status_code == 200
            data = res.json()
            assert data["isConnected"] is False
            assert data["windows"] == []
            assert "Pipe not found" in data["error"]


@pytest.mark.asyncio
async def test_list_open_windows_online():
    """Verify endpoint returns discovered windows when companion is online."""
    transport = ASGITransport(app=app)
    mock_windows = [
        {
            "hwnd": 12345,
            "title": "Notepad",
            "processName": "notepad.exe",
            "bounds": {"x": 0, "y": 0, "width": 800, "height": 600},
        },
        {
            "hwnd": 67890,
            "title": "Calculator",
            "processName": "CalculatorApp.exe",
            "bounds": {"x": 100, "y": 100, "width": 400, "height": 500},
        },
    ]
    with patch(
        "sahaay_core.api.v1.windows.adapter.list_open_windows",
        return_value=mock_windows,
    ):
        async with AsyncClient(transport=transport, base_url="http://testclient") as client:
            res = await client.get("/api/v1/windows")
            assert res.status_code == 200
            data = res.json()
            assert data["isConnected"] is True
            assert data["count"] == 2
            assert data["windows"][0]["title"] == "Notepad"


@pytest.mark.asyncio
async def test_get_active_window():
    """Verify active foreground window endpoint."""
    transport = ASGITransport(app=app)
    mock_active = {
        "hwnd": 12345,
        "title": "Visual Studio Code",
        "processName": "Code.exe",
    }
    with patch(
        "sahaay_core.api.v1.windows.adapter.get_active_window",
        return_value=mock_active,
    ):
        async with AsyncClient(transport=transport, base_url="http://testclient") as client:
            res = await client.get("/api/v1/windows/active")
            assert res.status_code == 200
            data = res.json()
            assert data["isConnected"] is True
            assert data["activeWindow"]["title"] == "Visual Studio Code"


@pytest.mark.asyncio
async def test_inspect_window_elements():
    """Verify UI Automation elements inspection endpoint."""
    transport = ASGITransport(app=app)
    mock_elements = [
        {
            "name": "Save",
            "controlType": "Button",
            "bounds": {"x": 10, "y": 10, "width": 50, "height": 25},
        },
        {
            "name": "Text Editor",
            "controlType": "Document",
            "bounds": {"x": 0, "y": 50, "width": 800, "height": 550},
        },
    ]
    with patch(
        "sahaay_core.api.v1.windows.adapter.inspect_window_elements",
        return_value=mock_elements,
    ):
        async with AsyncClient(transport=transport, base_url="http://testclient") as client:
            res = await client.post("/api/v1/windows/inspect", json={"hwnd": 12345})
            assert res.status_code == 200
            data = res.json()
            assert data["count"] == 2
            assert data["elements"][0]["name"] == "Save"
