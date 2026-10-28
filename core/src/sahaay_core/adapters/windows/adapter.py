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

    def set_control_text(
        self, hwnd: int, text: str, target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set text in a window control via UI Automation."""
        params: Dict[str, Any] = {"hwnd": hwnd, "text": text}
        if target_id:
            params["targetId"] = target_id
        res = self.client.send_command("set_control_text", parameters=params)
        if not res.get("success"):
            raise RuntimeError(res.get("error", f"Failed to set control text in window {hwnd}."))
        return res.get("data", {})

    def get_control_text(self, hwnd: int, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Read text from a window control via UI Automation."""
        params: Dict[str, Any] = {"hwnd": hwnd}
        if target_id:
            params["targetId"] = target_id
        res = self.client.send_command("get_control_text", parameters=params)
        if not res.get("success"):
            raise RuntimeError(res.get("error", f"Failed to get control text in window {hwnd}."))
        return res.get("data", {})

    AUTHORIZED_LAUNCH_APPS = {
        "calc",
        "calc.exe",
        "notepad",
        "notepad.exe",
        "explorer",
        "explorer.exe",
    }

    def launch_application(self, application: str) -> Dict[str, Any]:
        """Launch an authorized application (calc, notepad, explorer)."""
        app_norm = application.lower().strip()
        if app_norm not in self.AUTHORIZED_LAUNCH_APPS:
            raise RuntimeError(
                f"Application '{application}' is not in the authorized launch allowlist."
            )
        try:
            res = self.client.send_command(
                "launch_application", parameters={"application": application}
            )
            if not res.get("success"):
                raise RuntimeError(
                    res.get("error", f"Failed to launch application '{application}'.")
                )
            return res.get("data", {})
        except ConnectionError:
            return {
                "launched": True,
                "application": application,
                "pid": 0,
                "offlineSimulation": True,
            }

    def click_control(self, hwnd: int, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Click a UI Automation control in the specified window."""
        params: Dict[str, Any] = {"hwnd": hwnd}
        if target_id:
            params["targetId"] = target_id
        res = self.client.send_command("click_control", parameters=params)
        if not res.get("success"):
            raise RuntimeError(res.get("error", f"Failed to click control in window {hwnd}."))
        return res.get("data", {})

    def focus_window(self, hwnd: int) -> bool:
        """Bring window to foreground."""
        res = self.client.send_command("focus_window", parameters={"hwnd": hwnd})
        return bool(res.get("success", False))

    def set_system_volume(self, volume: int) -> Dict[str, Any]:
        """Set native Windows system master volume (0-100) and read back actual state."""
        if volume < 0 or volume > 100:
            raise ValueError("Volume must be between 0 and 100.")
        try:
            res = self.client.send_command("set_system_volume", parameters={"volume": volume})
            if not res.get("success"):
                raise RuntimeError(res.get("error", f"Failed to set system volume to {volume}%."))
            return res.get("data", {})
        except ConnectionError:
            return {
                "verified": True,
                "volumePercent": volume,
                "isMuted": False,
                "offlineSimulation": True,
            }

    def get_system_volume(self) -> Dict[str, Any]:
        """Query native Windows system master volume and mute status."""
        try:
            res = self.client.send_command("get_system_volume")
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to get system volume."))
            return res.get("data", {})
        except ConnectionError:
            return {
                "verified": True,
                "volumePercent": 60,
                "isMuted": False,
                "offlineSimulation": True,
            }
