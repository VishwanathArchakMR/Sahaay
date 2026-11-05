"""Task Target Resolver for Sahaay Perception.

Identifies the intended external execution target (window, browser tab, file/workspace,
creative canvas, or system global) while strictly excluding Sahaay's own Electron UI window
to prevent perception contamination.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TargetSurfaceType(str, Enum):
    DESKTOP_WINDOW = "desktop_window"
    BROWSER_TAB = "browser_tab"
    FILE_WORKSPACE = "file_workspace"
    CREATIVE_CANVAS = "creative_canvas"
    SYSTEM_GLOBAL = "system_global"


class TargetDescriptor(BaseModel):
    """Structured resolution of the target execution environment."""

    surface_type: TargetSurfaceType
    target_id: str
    name: str
    hwnd: Optional[int] = None
    process_name: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    bounds: Optional[Dict[str, int]] = None
    is_sahaay_excluded: bool = True
    confidence: float = 1.0
    reasoning: str = ""


# Process names and window titles associated with Sahaay or dev environments to exclude
SAHAAY_PROCESS_NAMES = {
    "electron",
    "sahaay",
    "sahaay-desktop",
    "sahaay.exe",
    "sahaay.controller",
    "sahaay.nativehost",
    "node",
    "conhost",
}

SAHAAY_TITLE_EXCLUSIONS = [
    "sahaay",
    "antigravity",
    "developer tools",
    "program manager",
    "task switching",
]


class TargetResolver:
    """Resolves the external target surface and application for any user task or observation request."""

    def __init__(self, known_sahaay_hwnd: Optional[int] = None) -> None:
        self.known_sahaay_hwnd = known_sahaay_hwnd

    def is_sahaay_window(
        self,
        process_name: Optional[str] = None,
        title: Optional[str] = None,
        hwnd: Optional[int] = None,
    ) -> bool:
        """Determines if a window belongs to Sahaay's own UI and must be excluded from external perception."""
        if hwnd and self.known_sahaay_hwnd and hwnd == self.known_sahaay_hwnd:
            return True

        p_name = (process_name or "").lower().strip()
        # Remove .exe extension if present
        if p_name.endswith(".exe"):
            p_name = p_name[:-4]

        if p_name in SAHAAY_PROCESS_NAMES or any(k in p_name for k in ("sahaay", "electron")):
            return True

        w_title = (title or "").lower().strip()
        for excl in SAHAAY_TITLE_EXCLUSIONS:
            if excl in w_title:
                return True

        return False

    def filter_external_windows(self, windows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters a list of windows to only include valid external applications."""
        external = []
        for win in windows:
            hwnd = int(win.get("hwnd", 0))
            if hwnd <= 0:
                continue
            p_name = win.get("processName", "")
            title = win.get("title", "")

            if not self.is_sahaay_window(process_name=p_name, title=title, hwnd=hwnd):
                external.append(win)

        return external

    def resolve_target(
        self,
        goal: str,
        context: Optional[str] = None,
        open_windows: Optional[List[Dict[str, Any]]] = None,
    ) -> TargetDescriptor:
        """Resolves the target execution surface and window/context from the goal and environment."""
        combined_text = f"{goal} {context or ''}".lower()

        # 1. Creative canvas / image editing detection
        if any(
            w in combined_text
            for w in (
                "edit image",
                "style image",
                "retro style",
                "vintage style",
                "canvas",
                "artistic",
                "illustration",
                "generate image",
                "draw",
            )
        ):
            return TargetDescriptor(
                surface_type=TargetSurfaceType.CREATIVE_CANVAS,
                target_id="creative_canvas",
                name="Creative Image Canvas",
                reasoning="Goal involves artistic image editing or visual artifact creation.",
            )

        # 2. File / Workspace observation
        file_match = re.search(r'([A-Za-z]:\\[^\n\r"]+|(?:\.\/|\.\.\\)[^\n\r"]+)', combined_text)
        if (
            any(
                w in combined_text
                for w in (
                    "file",
                    "directory",
                    "folder",
                    "workspace",
                    "code",
                    "table",
                    "csv",
                    "json",
                )
            )
            or file_match
        ):
            path_str = file_match.group(1) if file_match else None
            return TargetDescriptor(
                surface_type=TargetSurfaceType.FILE_WORKSPACE,
                target_id=path_str or "workspace_root",
                name="Filesystem Workspace",
                path=path_str,
                reasoning="Goal involves filesystem, workspace files, code, or tabular datasets.",
            )

        # 3. Browser tab detection
        url_match = re.search(
            r"(https?://[^\s]+|[a-zA-Z0-9\-\.]+\.(?:com|org|io|net|edu|dev|in|ai)(?:/[^\s]*)?)",
            combined_text,
        )
        if url_match or any(
            w in combined_text
            for w in (
                "browser",
                "tab",
                "webpage",
                "website",
                "chrome",
                "edge",
                "youtube",
                "amazon",
                "google",
                "wikipedia",
            )
        ):
            target_url = url_match.group(1) if url_match else None
            if target_url and not target_url.startswith(("http://", "https://")):
                target_url = f"https://{target_url}"
            return TargetDescriptor(
                surface_type=TargetSurfaceType.BROWSER_TAB,
                target_id=target_url or "active_browser_tab",
                name="Browser Web Tab",
                url=target_url,
                reasoning="Goal involves web browsing, active webpage inspection, or website navigation.",
            )

        # 4. System Global controls
        if any(w in combined_text for w in ("volume", "mute", "unmute", "audio level", "sound")):
            return TargetDescriptor(
                surface_type=TargetSurfaceType.SYSTEM_GLOBAL,
                target_id="system_audio",
                name="Windows System Audio",
                reasoning="Goal involves global system audio or volume manipulation.",
            )

        # 5. Desktop Application Target Resolution
        app_target_name = "Desktop Application"
        detected_hwnd = None
        detected_proc = None
        detected_bounds = None

        # Known desktop app keywords
        app_hints = {
            "notepad": ("notepad", "notepad.exe"),
            "calculator": ("calculator", "calc.exe"),
            "calc": ("calculator", "calc.exe"),
            "explorer": ("explorer", "explorer.exe"),
            "code": ("code", "Code.exe"),
            "word": ("winword", "WINWORD.EXE"),
            "excel": ("excel", "EXCEL.EXE"),
            "powerpoint": ("powerpnt", "POWERPNT.EXE"),
            "terminal": ("windowsterminal", "WindowsTerminal.exe"),
        }

        matched_app_keyword = None
        for hint_kw, (pname, exename) in app_hints.items():
            if re.search(r"\b" + re.escape(hint_kw) + r"\b", combined_text):
                matched_app_keyword = (hint_kw, pname, exename)
                app_target_name = hint_kw.capitalize()
                break

        # Filter external open windows
        ext_windows = self.filter_external_windows(open_windows or [])

        if matched_app_keyword:
            hint_kw, pname, exename = matched_app_keyword
            for win in ext_windows:
                wp = (win.get("processName") or "").lower()
                wt = (win.get("title") or "").lower()
                if pname in wp or exename.lower() in wp or hint_kw in wt:
                    detected_hwnd = int(win.get("hwnd", 0))
                    detected_proc = win.get("processName")
                    detected_bounds = win.get("bounds")
                    app_target_name = win.get("title") or app_target_name
                    break

        # Fallback to topmost non-Sahaay external window
        if not detected_hwnd and ext_windows:
            top_ext = ext_windows[0]
            detected_hwnd = int(top_ext.get("hwnd", 0))
            detected_proc = top_ext.get("processName")
            detected_bounds = top_ext.get("bounds")
            app_target_name = top_ext.get("title") or "Topmost External Window"

        return TargetDescriptor(
            surface_type=TargetSurfaceType.DESKTOP_WINDOW,
            target_id=str(detected_hwnd or app_target_name),
            name=app_target_name,
            hwnd=detected_hwnd,
            process_name=detected_proc,
            bounds=detected_bounds,
            reasoning=f"Target identified as external Windows desktop window '{app_target_name}'.",
        )
