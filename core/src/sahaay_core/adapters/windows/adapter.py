"""Windows Native Companion Adapter Interface.

Coordinates with Sahaay.Controller C# daemon via local IPC / named pipe / loopback.
Notice: This skeleton interface is explicitly labelled as UNIMPLEMENTED in Stage 01.
"""

from typing import Any, Dict, List


class WindowsAdapterNotImplementedError(NotImplementedError):
    pass


class WindowsNativeAdapter:
    """Adapter communicating with native Windows companion."""

    def __init__(self) -> None:
        self.is_companion_connected: bool = False

    async def list_open_windows(self) -> List[Dict[str, Any]]:
        """List open top-level application windows discovered by UI Automation."""
        raise WindowsAdapterNotImplementedError(
            "Windows UI Automation companion is scaffolded but not yet live in Stage 01."
        )

    async def capture_window_screenshot(self, hwnd: int) -> bytes:
        """Capture screenshot of authorized application window."""
        raise WindowsAdapterNotImplementedError(
            "Controlled window capture is scaffolded but not yet live in Stage 01."
        )
