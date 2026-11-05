"""Observation Coordinator Unit Tests.

Verifies the 4 distinct observation modes across execution surfaces:
- Mode A: Semantic UIA (Control tree, roles, values, focused element)
- Mode B: Visual Observation (Target window bounding, strict Sahaay exclusion)
- Mode C: Browser Observation (DOM, active tab, URL, accessible controls)
- Mode D: File / Workspace Observation (File system inspection, line counts, SHA-256)
"""

from unittest.mock import MagicMock

import pytest
from sahaay_core.perception.observation_coordinator import (
    ObservationCoordinator,
    ObservationMode,
)
from sahaay_core.perception.target_resolver import (
    TargetDescriptor,
    TargetSurfaceType,
)


@pytest.fixture
def mock_adapters():
    win_mock = MagicMock()
    br_mock = MagicMock()
    resolver_mock = MagicMock()
    resolver_mock.is_sahaay_window.return_value = False
    return win_mock, br_mock, resolver_mock


def test_mode_a_semantic_uia(mock_adapters):
    win_mock, br_mock, resolver_mock = mock_adapters
    win_mock.inspect_window_elements.return_value = [
        {
            "controlType": "Edit",
            "name": "Text Editor",
            "hasKeyboardFocus": True,
            "value": "Hello world",
        },
        {"controlType": "Button", "name": "Save", "hasKeyboardFocus": False},
    ]

    target = TargetDescriptor(
        surface_type=TargetSurfaceType.DESKTOP_WINDOW,
        target_id="notepad_win",
        name="Notepad",
        hwnd=101,
        process_name="notepad.exe",
    )

    coordinator = ObservationCoordinator(
        windows_adapter=win_mock,
        browser_adapter=br_mock,
        target_resolver=resolver_mock,
    )

    obs = coordinator.observe(
        goal="Check text in Notepad",
        target=target,
        preferred_mode=ObservationMode.MODE_A_SEMANTIC_UIA,
    )

    assert obs.mode == ObservationMode.MODE_A_SEMANTIC_UIA
    assert obs.is_sahaay_excluded is True
    assert obs.semantic_data is not None
    assert obs.semantic_data["hwnd"] == 101
    assert obs.semantic_data["elementsCount"] == 2
    assert obs.semantic_data["focusedElement"]["name"] == "Text Editor"
    win_mock.inspect_window_elements.assert_called_once_with(101)


def test_mode_b_visual_window_bounded_capture(mock_adapters, tmp_path):
    win_mock, br_mock, resolver_mock = mock_adapters
    test_img = tmp_path / "win_capture.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest")

    win_mock.capture_window_screenshot.return_value = {
        "success": True,
        "filePath": str(test_img),
        "width": 1280,
        "height": 720,
    }

    target = TargetDescriptor(
        surface_type=TargetSurfaceType.DESKTOP_WINDOW,
        target_id="calc_win",
        name="Calculator",
        hwnd=202,
        process_name="calc.exe",
    )

    coordinator = ObservationCoordinator(
        windows_adapter=win_mock,
        browser_adapter=br_mock,
        target_resolver=resolver_mock,
    )

    obs = coordinator.observe(
        goal="Take screenshot of calculator",
        target=target,
        preferred_mode=ObservationMode.MODE_B_VISUAL_WINDOW,
    )

    assert obs.mode == ObservationMode.MODE_B_VISUAL_WINDOW
    assert obs.is_sahaay_excluded is True
    assert obs.visual_data is not None
    assert obs.visual_data["hwnd"] == 202
    assert obs.visual_data["screenshotDataUri"].startswith("data:image/png;base64,")
    assert obs.visual_data["sha256"] is not None
    assert obs.visual_data["isSahaayExcluded"] is True
    win_mock.capture_window_screenshot.assert_called_once_with(202)


def test_mode_c_browser_dom(mock_adapters):
    win_mock, br_mock, resolver_mock = mock_adapters
    br_mock.is_connected.return_value = True
    br_mock.is_browser_attached.return_value = True
    br_mock.get_active_tab_observation.return_value = {
        "url": "https://example.org",
        "title": "Example Domain",
        "visibleTextExcerpt": "Example Domain: This domain is for use in illustrative examples.",
        "accessibleElements": [
            {"role": "heading", "name": "Example Domain"},
            {"role": "link", "name": "More information..."},
        ],
        "driverProvenance": "real_browser_extension",
    }

    target = TargetDescriptor(
        surface_type=TargetSurfaceType.BROWSER_TAB,
        target_id="tab_1",
        name="Example Domain",
        url="https://example.org",
    )

    coordinator = ObservationCoordinator(
        windows_adapter=win_mock,
        browser_adapter=br_mock,
        target_resolver=resolver_mock,
    )

    obs = coordinator.observe(
        goal="Inspect active browser tab content",
        target=target,
        preferred_mode=ObservationMode.MODE_C_BROWSER_DOM,
    )

    assert obs.mode == ObservationMode.MODE_C_BROWSER_DOM
    assert obs.is_sahaay_excluded is True
    assert obs.browser_data is not None
    assert obs.browser_data["url"] == "https://example.org"
    assert "Example Domain" in obs.browser_data["visibleTextExcerpt"]
    assert obs.browser_data["accessibleElementsCount"] == 2


def test_mode_d_file_workspace_direct_inspection(mock_adapters, tmp_path):
    win_mock, br_mock, resolver_mock = mock_adapters
    test_file = tmp_path / "notes.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\n", encoding="utf-8")

    target = TargetDescriptor(
        surface_type=TargetSurfaceType.FILE_WORKSPACE,
        target_id=str(test_file),
        name="notes.txt",
        path=str(test_file),
    )

    coordinator = ObservationCoordinator(
        windows_adapter=win_mock,
        browser_adapter=br_mock,
        target_resolver=resolver_mock,
    )

    obs = coordinator.observe(
        goal="Inspect file content",
        target=target,
        preferred_mode=ObservationMode.MODE_D_FILE_WORKSPACE,
    )

    assert obs.mode == ObservationMode.MODE_D_FILE_WORKSPACE
    assert obs.is_sahaay_excluded is True
    assert obs.file_data is not None
    assert obs.file_data["isFile"] is True
    assert obs.file_data["sizeBytes"] > 0
    assert obs.file_data["sha256"] is not None
    assert "Line 1" in obs.file_data["excerpt"]
    # Verify screen capture is NEVER called for Mode D
    win_mock.capture_window_screenshot.assert_not_called()
