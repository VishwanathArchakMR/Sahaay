"""Windows Companion Controller Endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter

router = APIRouter(prefix="/windows", tags=["Windows Controller"])
adapter = WindowsNativeAdapter()


class InspectWindowRequest(BaseModel):
    hwnd: int


class ObserveWindowRequest(BaseModel):
    hwnd: int
    captureScreenshot: bool = True


@router.get("", response_model=Dict[str, Any])
async def list_open_windows() -> Dict[str, Any]:
    """List open visible application windows discovered by native UI Automation."""
    try:
        windows = adapter.list_open_windows()
        return {"isConnected": True, "windows": windows, "count": len(windows)}
    except ConnectionError as ce:
        return {"isConnected": False, "windows": [], "count": 0, "error": str(ce)}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@router.get("/active", response_model=Dict[str, Any])
async def get_active_window() -> Dict[str, Any]:
    """Get the current active foreground window descriptor."""
    try:
        active = adapter.get_active_window()
        return {"isConnected": True, "activeWindow": active}
    except ConnectionError as ce:
        return {"isConnected": False, "activeWindow": None, "error": str(ce)}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@router.post("/inspect", response_model=Dict[str, Any])
async def inspect_window_elements(req: InspectWindowRequest) -> Dict[str, Any]:
    """Inspect accessible UI Automation elements for a specific window HWND."""
    try:
        elements = adapter.inspect_window_elements(req.hwnd)
        return {"hwnd": req.hwnd, "elements": elements, "count": len(elements)}
    except ConnectionError as ce:
        raise HTTPException(status_code=503, detail=str(ce)) from ce
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


@router.post("/observe", response_model=Dict[str, Any])
async def observe_window(req: ObserveWindowRequest) -> Dict[str, Any]:
    """Capture structured observation and optional screenshot of an authorized window."""
    try:
        elements = adapter.inspect_window_elements(req.hwnd)
        screenshot_data = {}
        if req.captureScreenshot:
            screenshot_data = adapter.capture_window_screenshot(req.hwnd)

        return {
            "hwnd": req.hwnd,
            "elementsCount": len(elements),
            "elements": elements,
            "screenshot": screenshot_data,
        }
    except ConnectionError as ce:
        raise HTTPException(status_code=503, detail=str(ce)) from ce
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex
