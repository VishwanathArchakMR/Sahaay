"""Target Resolver Unit Tests.

Verifies target-aware perception, identification of execution target surfaces
(DESKTOP_WINDOW, BROWSER_TAB, FILE_WORKSPACE, CREATIVE_CANVAS, SYSTEM_GLOBAL),
and strict exclusion of Sahaay Electron UI windows to prevent self-observation contamination.
"""

import pytest
from sahaay_core.perception.target_resolver import (
    TargetDescriptor,
    TargetResolver,
    TargetSurfaceType,
)


def test_sahaay_window_detection_by_process():
    resolver = TargetResolver(known_sahaay_hwnd=12345)

    # All variations of Sahaay process names must be flagged as Sahaay UI
    assert resolver.is_sahaay_window(process_name="electron", title="Random") is True
    assert resolver.is_sahaay_window(process_name="electron.exe", title="App") is True
    assert resolver.is_sahaay_window(process_name="sahaay", title="Main Window") is True
    assert resolver.is_sahaay_window(process_name="sahaay-desktop.exe", title="Sahaay") is True
    assert resolver.is_sahaay_window(process_name="sahaay.controller", title="Service") is True
    assert resolver.is_sahaay_window(process_name="sahaay.nativehost.exe", title="") is True

    # Known Sahaay HWND must be flagged
    assert resolver.is_sahaay_window(process_name="external_app", title="Ext", hwnd=12345) is True


def test_sahaay_window_detection_by_title():
    resolver = TargetResolver()

    assert resolver.is_sahaay_window(process_name="app", title="Sahaay Desktop Agent") is True
    assert resolver.is_sahaay_window(process_name="app", title="Developer Tools - localhost:5173") is True
    assert resolver.is_sahaay_window(process_name="app", title="Antigravity Workspace") is True


def test_external_window_not_flagged_as_sahaay():
    resolver = TargetResolver(known_sahaay_hwnd=99999)

    assert resolver.is_sahaay_window(process_name="notepad.exe", title="Untitled - Notepad", hwnd=101) is False
    assert resolver.is_sahaay_window(process_name="calculator.exe", title="Calculator", hwnd=102) is False
    assert resolver.is_sahaay_window(process_name="chrome.exe", title="Google - Google Chrome", hwnd=103) is False
    assert resolver.is_sahaay_window(process_name="msedge.exe", title="Microsoft Edge", hwnd=104) is False
    assert resolver.is_sahaay_window(process_name="code.exe", title="VS Code", hwnd=105) is False


def test_filter_external_windows_excludes_sahaay_and_devtools():
    resolver = TargetResolver(known_sahaay_hwnd=8888)

    sample_windows = [
        {"hwnd": 8888, "processName": "electron", "title": "Sahaay Agent"},
        {"hwnd": 1001, "processName": "notepad", "title": "Untitled - Notepad"},
        {"hwnd": 1002, "processName": "calculator", "title": "Calculator"},
        {"hwnd": 1003, "processName": "node", "title": "Developer Tools"},
        {"hwnd": 1004, "processName": "chrome", "title": "Wikipedia - Google Chrome"},
        {"hwnd": 0, "processName": "", "title": ""},  # invalid hwnd
    ]

    filtered = resolver.filter_external_windows(sample_windows)
    filtered_hwnds = [w["hwnd"] for w in filtered]

    assert 1001 in filtered_hwnds
    assert 1002 in filtered_hwnds
    assert 1004 in filtered_hwnds
    assert 8888 not in filtered_hwnds
    assert 1003 not in filtered_hwnds
    assert 0 not in filtered_hwnds
    assert len(filtered) == 3


def test_resolve_target_desktop_window():
    resolver = TargetResolver()
    open_windows = [
        {"hwnd": 501, "processName": "notepad.exe", "title": "meeting_notes.txt - Notepad"},
        {"hwnd": 502, "processName": "chrome.exe", "title": "Dashboard"},
    ]

    target = resolver.resolve_target(
        goal="Type meeting summary into Notepad and save it",
        open_windows=open_windows,
    )

    assert target.surface_type == TargetSurfaceType.DESKTOP_WINDOW
    assert target.hwnd == 501
    assert "Notepad" in target.name
    assert target.is_sahaay_excluded is True


def test_resolve_target_browser_tab():
    resolver = TargetResolver()

    target = resolver.resolve_target(
        goal="Navigate to https://news.ycombinator.com and read the top stories",
        context="Active browser tab: Hacker News",
    )

    assert target.surface_type == TargetSurfaceType.BROWSER_TAB
    assert target.url == "https://news.ycombinator.com"
    assert target.is_sahaay_excluded is True


def test_resolve_target_file_workspace():
    resolver = TargetResolver()

    target = resolver.resolve_target(
        goal="Read the contents of C:\\Sahaay\\data\\records.csv and analyze columns",
    )

    assert target.surface_type == TargetSurfaceType.FILE_WORKSPACE
    assert "records.csv" in target.path
    assert target.is_sahaay_excluded is True


def test_resolve_target_creative_canvas():
    resolver = TargetResolver()

    target = resolver.resolve_target(
        goal="Generate a high-resolution vector illustration of an aurora over mountains",
    )

    assert target.surface_type == TargetSurfaceType.CREATIVE_CANVAS
    assert target.is_sahaay_excluded is True

