"""Windows Native Companion Adapter.

Coordinates with Sahaay.Controller C# daemon via authenticated local Named Pipe.
Enforces strict driver provenance: distinguishes real native execution from offline simulation.
"""

from typing import Any, Dict, List, Optional

from sahaay_core.adapters.windows.named_pipe_client import NamedPipeClient


class WindowsNativeAdapter:
    """Adapter communicating with native Windows companion daemon."""

    def __init__(
        self, pipe_name: str = "SahaayControllerPipe", allow_simulation: bool = True
    ) -> None:
        self.pipe_name = pipe_name
        self.allow_simulation = allow_simulation
        self.client = NamedPipeClient(pipe_name=pipe_name)
        self._mock_controls: Dict[str, str] = {}
        self._system_volume: int = 50

    def _handle_connection_error(self, operation: str) -> None:
        """Handle missing daemon connection based on allow_simulation policy."""
        if not self.allow_simulation:
            raise ConnectionError(
                f"Windows companion daemon (Sahaay.Controller) is not running on \\\\.\\pipe\\{self.pipe_name}. "
                f"Real desktop operation '{operation}' is unavailable. "
                "Ensure Sahaay Desktop supervisor or Sahaay.Controller is active in the interactive desktop session."
            )

    def ping(self) -> bool:
        """Check if native companion daemon is reachable."""
        try:
            res = self.client.send_command("ping", timeout_ms=500)
            return bool(res.get("success", False))
        except Exception:
            return False

    def is_connected(self) -> bool:
        """Check if Sahaay Windows companion daemon is active and responsive."""
        return self.ping()

    def get_capabilities(self) -> Dict[str, Any]:
        """Fetch real native capabilities from Windows controller."""
        try:
            res = self.client.send_command("get_capabilities")
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to retrieve capabilities."))
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("get_capabilities")
            return {
                "uiAutomationAvailable": True,
                "appLaunchAvailable": True,
                "audioControlAvailable": True,
                "version": "0.2.0-offline",
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def list_open_windows(self) -> List[Dict[str, Any]]:
        """List open top-level application windows discovered by UI Automation."""
        try:
            res = self.client.send_command("list_open_windows")
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to list windows."))
            return res.get("data", [])
        except ConnectionError:
            self._handle_connection_error("list_open_windows")
            return [
                {"hwnd": 1001, "title": "Untitled - Notepad", "processName": "notepad"},
                {"hwnd": 1002, "title": "Calculator", "processName": "CalculatorApp"},
            ]

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get descriptor of current active foreground window."""
        try:
            res = self.client.send_command("get_active_window")
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to get active window."))
            return res.get("data")
        except ConnectionError:
            self._handle_connection_error("get_active_window")
            return {"hwnd": 1001, "title": "Untitled - Notepad", "processName": "notepad"}

    def inspect_window_elements(self, hwnd: int) -> List[Dict[str, Any]]:
        """Inspect accessible UI Automation elements in a window."""
        try:
            res = self.client.send_command("inspect_window_elements", parameters={"hwnd": hwnd})
            if not res.get("success"):
                raise RuntimeError(res.get("error", f"Failed to inspect window {hwnd}."))
            return res.get("data", [])
        except ConnectionError:
            self._handle_connection_error("inspect_window_elements")
            return [
                {"automationId": "15", "name": "Text Editor", "controlType": "DocumentEdit"},
                {"automationId": "FileMenu", "name": "File", "controlType": "MenuItem"},
            ]

    def capture_window_screenshot(
        self, hwnd: int, output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Capture screenshot of authorized application window."""
        params = {"hwnd": hwnd}
        if output_dir:
            params["outputDir"] = output_dir

        try:
            res = self.client.send_command("capture_window_screenshot", parameters=params)
            if not res.get("success"):
                raise RuntimeError(res.get("error", f"Failed to capture window {hwnd}."))
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("capture_window_screenshot")
            return {
                "screenshotCaptured": True,
                "hwnd": hwnd,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def set_control_text(
        self, hwnd: int, text: str, target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set text in a window control via UI Automation."""
        params: Dict[str, Any] = {"hwnd": hwnd, "text": text}
        if target_id:
            params["targetId"] = target_id
        try:
            res = self.client.send_command("set_control_text", parameters=params)
            if not res.get("success"):
                raise RuntimeError(
                    res.get("error", f"Failed to set control text in window {hwnd}.")
                )
            data = res.get("data", {})
            if isinstance(data, dict):
                if "text" not in data and "value" in data:
                    data["text"] = data["value"]
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("set_control_text")
            ctrl_key = f"{hwnd}_{target_id}"
            self._mock_controls[ctrl_key] = text
            return {
                "success": True,
                "hwnd": hwnd,
                "targetId": target_id,
                "text": text,
                "value": text,
                "writtenText": text,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def get_control_text(self, hwnd: int, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Read text from a window control via UI Automation."""
        params: Dict[str, Any] = {"hwnd": hwnd}
        if target_id:
            params["targetId"] = target_id
        try:
            res = self.client.send_command("get_control_text", parameters=params)
            if not res.get("success"):
                raise RuntimeError(
                    res.get("error", f"Failed to get control text in window {hwnd}.")
                )
            data = res.get("data", {})
            if isinstance(data, dict):
                if "text" not in data and "value" in data:
                    data["text"] = data["value"]
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("get_control_text")
            ctrl_key = f"{hwnd}_{target_id}"
            text = self._mock_controls.get(ctrl_key, "Sample Document Content")
            return {
                "success": True,
                "hwnd": hwnd,
                "targetId": target_id,
                "text": text,
                "value": text,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    AUTHORIZED_LAUNCH_APPS = {
        "calc",
        "calc.exe",
        "calculator",
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
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("launch_application")
            return {
                "success": True,
                "launched": True,
                "application": application,
                "pid": 0,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def click_control(self, hwnd: int, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Click a UI Automation control in the specified window."""
        params: Dict[str, Any] = {"hwnd": hwnd}
        if target_id:
            params["targetId"] = target_id
        try:
            res = self.client.send_command("click_control", parameters=params)
            if not res.get("success"):
                raise RuntimeError(res.get("error", f"Failed to click control in window {hwnd}."))
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("click_control")
            return {
                "success": True,
                "clicked": True,
                "hwnd": hwnd,
                "targetId": target_id,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def focus_window(self, hwnd: int) -> bool:
        """Bring window to foreground."""
        try:
            res = self.client.send_command("focus_window", parameters={"hwnd": hwnd})
            return bool(res.get("success", False))
        except ConnectionError:
            self._handle_connection_error("focus_window")
            return True

    def set_system_volume(self, volume: int) -> Dict[str, Any]:
        """Set native Windows system master volume (0-100) and read back actual state."""
        if volume < 0 or volume > 100:
            raise ValueError("Volume must be between 0 and 100.")
        try:
            res = self.client.send_command("set_system_volume", parameters={"volume": volume})
            if not res.get("success"):
                raise RuntimeError(res.get("error", f"Failed to set system volume to {volume}%."))
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("set_system_volume")
            self._system_volume = volume
            return {
                "success": True,
                "verified": True,
                "volumePercent": volume,
                "isMuted": False,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }

    def get_system_volume(self) -> Dict[str, Any]:
        """Query native Windows system master volume and mute status."""
        try:
            res = self.client.send_command("get_system_volume")
            if not res.get("success"):
                raise RuntimeError(res.get("error", "Failed to get system volume."))
            data = res.get("data", {})
            if isinstance(data, dict):
                data["success"] = True
                data["driverProvenance"] = "real_native_driver"
            return data
        except ConnectionError:
            self._handle_connection_error("get_system_volume")
            return {
                "success": True,
                "verified": True,
                "volumePercent": getattr(self, "_system_volume", 65),
                "isMuted": False,
                "driverProvenance": "offline_simulation",
                "offlineSimulation": True,
            }
