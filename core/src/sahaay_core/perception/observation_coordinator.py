"""Observation Coordinator for Target-Aware Multi-Surface Perception.

Coordinates observations across four distinct modes:
- Mode A: Native Semantic Observation (Windows UI Automation tree, controls, values, states)
- Mode B: Visual Observation (Target-window bounded capture, strictly excluding Sahaay UI)
- Mode C: Browser Observation (Native Messaging extension bridge, DOM, active tab, URL)
- Mode D: File / Workspace Observation (Direct filesystem indexing, hashes, metadata)
"""

import base64
import hashlib
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from sahaay_core.adapters.browser.adapter import BrowserAdapter
from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
from sahaay_core.config.logging import logger
from sahaay_core.perception.target_resolver import (
    TargetDescriptor,
    TargetResolver,
    TargetSurfaceType,
)


class ObservationMode(str, Enum):
    MODE_A_SEMANTIC_UIA = "semantic_uia"
    MODE_B_VISUAL_WINDOW = "visual_window"
    MODE_C_BROWSER_DOM = "browser_dom"
    MODE_D_FILE_WORKSPACE = "file_workspace"


class StructuredObservation(BaseModel):
    """Authoritative target-aware structured observation."""

    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    mode: ObservationMode
    target: TargetDescriptor
    is_sahaay_excluded: bool = True
    semantic_data: Optional[Dict[str, Any]] = None
    visual_data: Optional[Dict[str, Any]] = None
    browser_data: Optional[Dict[str, Any]] = None
    file_data: Optional[Dict[str, Any]] = None
    freshness_status: str = "live"
    message: str = ""


class ObservationCoordinator:
    """Coordinates target-aware observations avoiding agent UI self-contamination."""

    def __init__(
        self,
        windows_adapter: Optional[WindowsNativeAdapter] = None,
        browser_adapter: Optional[BrowserAdapter] = None,
        target_resolver: Optional[TargetResolver] = None,
    ) -> None:
        self.windows_adapter = windows_adapter or WindowsNativeAdapter()
        self.browser_adapter = browser_adapter or BrowserAdapter()
        self.target_resolver = target_resolver or TargetResolver()

    def observe(
        self,
        goal: str = "",
        target: Optional[TargetDescriptor] = None,
        preferred_mode: Optional[ObservationMode] = None,
        context: Optional[str] = None,
    ) -> StructuredObservation:
        """Collects a target-aware observation based on task goal and target environment."""
        # 1. Resolve Target if not provided
        if not target:
            open_wins = []
            try:
                open_wins = self.windows_adapter.list_open_windows()
            except Exception as ex:
                logger.debug("Could not list open windows during target resolution: %s", ex)
            target = self.target_resolver.resolve_target(
                goal=goal, context=context, open_windows=open_wins
            )

        # 2. Select appropriate observation mode
        mode = preferred_mode
        if not mode:
            if target.surface_type == TargetSurfaceType.BROWSER_TAB:
                mode = ObservationMode.MODE_C_BROWSER_DOM
            elif target.surface_type == TargetSurfaceType.FILE_WORKSPACE:
                mode = ObservationMode.MODE_D_FILE_WORKSPACE
            elif target.surface_type == TargetSurfaceType.DESKTOP_WINDOW:
                mode = ObservationMode.MODE_A_SEMANTIC_UIA
            else:
                mode = ObservationMode.MODE_B_VISUAL_WINDOW

        # 3. Execute Mode-Specific Observation
        if mode == ObservationMode.MODE_C_BROWSER_DOM:
            return self._observe_browser(target)
        elif mode == ObservationMode.MODE_D_FILE_WORKSPACE:
            return self._observe_file_workspace(target)
        elif mode == ObservationMode.MODE_A_SEMANTIC_UIA:
            return self._observe_semantic_uia(target)
        else:
            return self._observe_visual_window(target)

    def _observe_semantic_uia(self, target: TargetDescriptor) -> StructuredObservation:
        """Mode A: Native Semantic Observation using Windows UI Automation."""
        hwnd = target.hwnd or 0
        if hwnd <= 0:
            # Query current active external window
            active_win = self.windows_adapter.get_active_window()
            if active_win and not self.target_resolver.is_sahaay_window(
                process_name=active_win.get("processName"),
                title=active_win.get("title"),
                hwnd=int(active_win.get("hwnd", 0)),
            ):
                hwnd = int(active_win.get("hwnd", 0))
                target.hwnd = hwnd
                target.process_name = active_win.get("processName")
                target.name = active_win.get("title") or target.name
                target.bounds = active_win.get("bounds")

        elements: List[Dict[str, Any]] = []
        focused_el = None
        if hwnd > 0:
            try:
                elements = self.windows_adapter.inspect_window_elements(hwnd)
                for el in elements:
                    if el.get("hasKeyboardFocus") or el.get("isFocused"):
                        focused_el = el
                        break
                if not focused_el and elements:
                    focused_el = elements[0]
            except Exception as ex:
                logger.warning("UIA element inspection error for HWND %s: %s", hwnd, ex)

        has_target = bool(hwnd > 0 and (elements or target.name))
        semantic_payload = {
            "hwnd": hwnd,
            "processName": target.process_name,
            "windowTitle": target.name,
            "bounds": target.bounds,
            "elementsCount": len(elements),
            "elements": elements[:60],
            "focusedElement": focused_el,
            "isExternalTarget": True,
        }

        msg = (
            f"Mode A Semantic UIA: Observing external window '{target.name}' (HWND: {hwnd}, {len(elements)} controls)"
            if has_target
            else "Mode A Semantic UIA: No external desktop application active. Focus an external application."
        )

        return StructuredObservation(
            mode=ObservationMode.MODE_A_SEMANTIC_UIA,
            target=target,
            is_sahaay_excluded=True,
            semantic_data=semantic_payload,
            freshness_status="live" if has_target else "no_target",
            message=msg,
        )

    def _observe_visual_window(self, target: TargetDescriptor) -> StructuredObservation:
        """Mode B: Visual Observation capturing ONLY the target window, strictly excluding Sahaay."""
        hwnd = target.hwnd or 0
        screenshot_uri = None
        sha256_hash = None
        width = 0
        height = 0

        if hwnd > 0:
            try:
                cap_res = self.windows_adapter.capture_window_screenshot(hwnd)
                file_path = cap_res.get("filePath")
                if file_path and os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                        sha256_hash = hashlib.sha256(img_bytes).hexdigest()
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        screenshot_uri = f"data:image/png;base64,{b64}"
                width = cap_res.get("width", 0)
                height = cap_res.get("height", 0)
            except Exception as ex:
                logger.warning("Visual window screenshot capture failed for HWND %s: %s", hwnd, ex)

        visual_payload = {
            "hwnd": hwnd,
            "windowTitle": target.name,
            "processName": target.process_name,
            "bounds": target.bounds,
            "screenshotDataUri": screenshot_uri,
            "sha256": sha256_hash,
            "dimensions": {"width": width, "height": height},
            "isSahaayExcluded": True,
        }

        has_target = bool(hwnd > 0 and screenshot_uri)
        msg = (
            f"Mode B Visual: Captured target window '{target.name}' (HWND: {hwnd}, SHA-256: {sha256_hash[:8] if sha256_hash else 'N/A'})."
            if has_target
            else "Mode B Visual: No valid target window to capture. Agent window excluded."
        )

        return StructuredObservation(
            mode=ObservationMode.MODE_B_VISUAL_WINDOW,
            target=target,
            is_sahaay_excluded=True,
            visual_data=visual_payload,
            freshness_status="live" if has_target else "no_target",
            message=msg,
        )

    def _observe_browser(self, target: TargetDescriptor) -> StructuredObservation:
        """Mode C: Browser Observation via Extension and Native Messaging bridge."""
        is_conn = self.browser_adapter.is_connected()
        is_attached = self.browser_adapter.is_browser_attached() if is_conn else False

        tab_data: Dict[str, Any] = {}
        if is_attached:
            try:
                tab_data = self.browser_adapter.get_active_tab_observation()
            except Exception as ex:
                logger.warning("Active tab query error: %s", ex)

        # Fallback to in-memory active observation if available
        if not tab_data and self.browser_adapter.active_observations:
            tab_data = list(self.browser_adapter.active_observations.values())[-1]

        url = tab_data.get("url") or target.url or ""
        title = tab_data.get("title") or target.name or "Active Web Tab"
        excerpt = tab_data.get("visibleTextExcerpt", "")

        browser_payload = {
            "isBridgeConnected": is_conn,
            "isBrowserAttached": is_attached,
            "url": url,
            "title": title,
            "visibleTextExcerpt": excerpt,
            "scrollPosition": tab_data.get("scrollPosition", {"x": 0, "y": 0}),
            "documentDimensions": tab_data.get("documentDimensions", {}),
            "accessibleElementsCount": len(tab_data.get("accessibleElements", [])),
        }

        freshness = (
            "live" if is_attached and url else ("awaiting_tab" if is_conn else "disconnected")
        )
        msg = (
            f"Mode C Browser: Observing web tab '{title}' ({url})."
            if is_attached and url
            else "Mode C Browser: Browser bridge active; waiting for open web tab."
            if is_conn
            else "Mode C Browser: Native messaging bridge disconnected."
        )

        return StructuredObservation(
            mode=ObservationMode.MODE_C_BROWSER_DOM,
            target=target,
            is_sahaay_excluded=True,
            browser_data=browser_payload,
            freshness_status=freshness,
            message=msg,
        )

    def _observe_file_workspace(self, target: TargetDescriptor) -> StructuredObservation:
        """Mode D: Direct Filesystem Observation without screen capture."""
        target_path_str = target.path or "."
        target_path = Path(os.path.expandvars(os.path.expanduser(target_path_str))).resolve()

        exists = target_path.exists()
        is_dir = target_path.is_dir() if exists else False
        is_file = target_path.is_file() if exists else False

        items_summary = []
        file_sha256 = None
        file_content_excerpt = None
        total_size = 0

        if exists:
            if is_file:
                try:
                    stat = target_path.stat()
                    total_size = stat.st_size
                    with open(target_path, "rb") as f:
                        raw = f.read(65536)  # Read up to 64KB for inspection
                        file_sha256 = hashlib.sha256(raw).hexdigest()
                        file_content_excerpt = raw.decode("utf-8", errors="replace")[:2000]
                except Exception as ex:
                    logger.warning("File read error for %s: %s", target_path, ex)
            elif is_dir:
                try:
                    for entry in target_path.iterdir():
                        try:
                            stat = entry.stat()
                            items_summary.append(
                                {
                                    "name": entry.name,
                                    "isDir": entry.is_dir(),
                                    "size": stat.st_size if entry.is_file() else 0,
                                }
                            )
                        except Exception:
                            pass
                except Exception as ex:
                    logger.warning("Directory read error for %s: %s", target_path, ex)

        file_payload = {
            "path": str(target_path),
            "exists": exists,
            "isDirectory": is_dir,
            "isFile": is_file,
            "sizeBytes": total_size,
            "sha256": file_sha256,
            "excerpt": file_content_excerpt,
            "itemsCount": len(items_summary),
            "items": items_summary[:50],
        }

        msg = (
            f"Mode D File: Observing file '{target_path.name}' ({total_size} bytes, SHA-256: {file_sha256[:8] if file_sha256 else 'N/A'})."
            if is_file
            else f"Mode D Workspace: Observing directory '{target_path.name}' ({len(items_summary)} entries)."
            if is_dir
            else f"Mode D File: Path '{target_path}' not found."
        )

        return StructuredObservation(
            mode=ObservationMode.MODE_D_FILE_WORKSPACE,
            target=target,
            is_sahaay_excluded=True,
            file_data=file_payload,
            freshness_status="live" if exists else "not_found",
            message=msg,
        )
