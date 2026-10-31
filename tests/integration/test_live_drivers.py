"""Opt-in live driver verification tests for real Windows and Browser sessions.

These tests are excluded from headless CI workflows and are executed on real machines
with an interactive desktop and running browser bridge:
    pytest -m live_browser
    pytest -m live_windows
"""

import pytest
from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter


@pytest.mark.live_browser
def test_live_browser_extension_connection():
    """Verify live browser bridge connection when Chrome/Edge is open with Sahaay extension."""
    adapter = BrowserAdapter()
    if not adapter.is_connected():
        pytest.skip(
            "Sahaay Browser Bridge extension is not currently connected to Native Messaging Host."
        )

    observations = adapter.active_observations
    assert len(observations) > 0, (
        "Connected bridge should yield at least one active tab observation."
    )
    active = next(iter(observations.values()))
    assert active.url != ""
    assert active.driverProvenance == "real_browser_extension"


@pytest.mark.live_windows
def test_live_windows_native_companion_connection():
    """Verify live Windows companion named pipe connection when Sahaay.WindowsCompanion is running."""
    adapter = WindowsNativeAdapter(allow_simulation=False)
    if not adapter.is_connected():
        pytest.skip(
            "Sahaay Windows Companion daemon is not running on named pipe 'SahaayControllerPipe'."
        )

    windows = adapter.find_windows()
    assert isinstance(windows, list)
