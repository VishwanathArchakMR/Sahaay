"""Windows Native Companion Adapter.

Coordinates with Sahaay.Controller C# daemon via authenticated local Named Pipe.
"""

from typing import Any, Dict, List, Optional

from sahaay_core.adapters.windows.named_pipe_client import NamedPipeClient


class WindowsNativeAdapter:
    """Adapter communicating with native Windows companion daemon."""

    def __init__(self, pipe_name: str = "SahaayControllerPipe") -> None:
        self.client = NamedPipeClient(pipe_name=pipe_name)

    def ping(self) -> bool:
        """Check if native companion daemon is reachable."""
        try:
            res = self.client.send_command("ping")
            return res.get("success", False)
        except Exception:
            return False

    def get_capabilities(self) -> Dict[str, Any]:
        """Fetch real native capabilities from Windows controller."""
        res = self.client.send_command("get_capabilities")
        if not res.get("success"):
            raise RuntimeError(res.get("error", "Failed to retrieve capabilities."))
        return res.get("data", {})

    def list_open_windows(self) -> List[Dict[str, Any]]:
        """List open top-level application windows discovered by UI Automation."""
        res = self.client.send_command("list_open_windows")
        if not res.get("success"):
            raise RuntimeError(res.get("error", "Failed to list windows."))
        return res.get("data", [])

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get descriptor of current active foreground window."""
        res = self.client.send_command("get_active_window")
        if not res.get("success"):
            raise RuntimeError(res.get("error", "Failed to get active window."))
        return res.get("data")

    def inspect_window_elements(self, hwnd: int) -> List[Dict[str, Any]]:
        """Inspect accessible UI Automation elements in a window."""
        res = self.client.send_command("inspect_window_elements", parameters={"hwnd": hwnd})
        if not res.get("success"):
            raise RuntimeError(res.get("error", f"Failed to inspect window {hwnd}."))
        return res.get("data", [])

    def capture_window_screenshot(
        self, hwnd: int, output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Capture screenshot of authorized application window."""
        params = {"hwnd": hwnd}
        if output_dir:
            params["outputDir"] = output_dir

        res = self.client.send_command("capture_window_screenshot", parameters=params)
        if not res.get("success"):
            raise RuntimeError(res.get("error", f"Failed to capture window {hwnd}."))
        return res.get("data", {})
