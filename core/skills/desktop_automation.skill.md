---
name: Windows Desktop Automation and UI Inspection
description: Method for discovering desktop application windows, inspecting UI Automation control trees, typing text, and visual verification.
version: 1.0.0
author: Sahaay Core Team
tools: [windows_launch_app, windows_get_active_window, windows_enumerate_controls, windows_type_text, windows_invoke_control, windows_capture_screen]
---

### Desktop Automation Methodology:
1. **Application Launch & Discovery**: Launch or locate the target desktop application using `windows_launch_app` or `windows_get_active_window` (e.g. Notepad, Calculator, File Explorer).
2. **Control Tree Inspection**: Use `windows_enumerate_controls` to discover accessible UI elements (names, AutomationIds, ControlTypes).
3. **Targeted Interaction**: Invoke controls or type text using `windows_invoke_control` and `windows_type_text`.
4. **Perception Fusion**: If UI Automation controls are obscured or custom-drawn, capture a desktop screenshot using `windows_capture_screen` and reason visually.
5. **Readback Verification**: Verify that the window state or control text changed according to expectations.

