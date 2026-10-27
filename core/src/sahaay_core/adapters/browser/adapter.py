"""Browser Integration Adapter Interface.

Coordinates with Manifest V3 browser extension and Playwright (for Sahaay-owned contexts).
Notice: This skeleton interface is explicitly labelled as UNIMPLEMENTED in Stage 01.
"""

from typing import Any, Dict


class BrowserAdapterNotImplementedError(NotImplementedError):
    pass


class BrowserAdapter:
    """Adapter for browser tab inspection and permitted interactions."""

    def __init__(self) -> None:
        self.is_connected: bool = False

    async def get_active_tab_metadata(self) -> Dict[str, Any]:
        """Fetch metadata from authorized active browser tab via extension."""
        raise BrowserAdapterNotImplementedError(
            "Browser extension communication is scaffolded but not yet live in Stage 01."
        )

    async def get_tab_dom_snapshot(self, tab_id: int) -> Dict[str, Any]:
        """Fetch sanitized DOM representation from content script."""
        raise BrowserAdapterNotImplementedError(
            "DOM snapshot retrieval is scaffolded but not yet live in Stage 01."
        )
