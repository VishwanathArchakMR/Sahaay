# SAHAAY — OPERATIONAL CONSTRAINTS AND KNOWN LIMITATIONS

## 1. Introduction

In keeping with Sahaay's core engineering principle of truthful attestation, this document transparently catalogs the technical boundaries, platform constraints, and operational considerations of the system as configured for the Meta AI Developer Hackathon.

---

## 2. Windows Desktop Operating Constraints

### 2.1 Process Elevation and User Account Control (UAC)
- **Constraint**: Windows UI Automation (UIA) running under a standard user token cannot inspect or interact with windows owned by elevated administrative processes (e.g., Task Manager running as Admin, Command Prompt running as Administrator, or elevated installer prompts).
- **Behavior**: If an automated task targets an elevated window, UI Automation returns `ElementNotAvailableException`.
- **Mitigation / Architecture**: The `ActionGate` detects access violations and gracefully triggers `HANDOFF_REQUESTED`, informing the user: *"This window requires elevated permissions. Please complete this step manually or take over control."*

### 2.2 Direct-Drawn and Accelerated Canvases
- **Constraint**: Legacy Win32 controls and modern WPF/WinUI controls expose rich semantic accessibility trees. However, custom graphic engines (e.g. video games, legacy DirectX/OpenGL viewports, or custom HTML5 `<canvas>` elements that omit ARIA attributes) do not populate accessibility nodes.
- **Behavior**: The controller cannot resolve specific control names or automation IDs within raw rendered canvases.
- **Mitigation / Architecture**: Sahaay falls back to coordinate clicks grounded via Meta SAM 3.1 visual segmentation or prompts the user via human-in-the-loop handoff.

### 2.3 High-DPI Multi-Monitor Setups
- **Constraint**: Multi-monitor displays with mismatched DPI scaling (e.g., 200% on a 4K primary laptop display and 100% on an external 1080p secondary display) can introduce coordinate translation offsets if synthetic mouse coordinates are used.
- **Mitigation / Architecture**: Sahaay uses native UI Automation patterns (`ValuePattern.SetValue`, `InvokePattern.Invoke`) which operate directly on window control handles independent of physical screen pixel coordinates.

---

## 3. Browser Extension and Chromium Environment

### 3.1 Chrome Web Store / System URL Restrictions
- **Constraint**: Chromium security architecture forbids content scripts from executing on special internal scheme URLs:
  - `chrome://*` and `edge://*` (Settings, Extensions, Flags)
  - `chrome.google.com/webstore/*` (Chrome Web Store pages)
- **Behavior**: The extension sidepanel detects when the user is viewing an internal page and displays: *"Browser automation is restricted on internal browser system pages by Chromium security policy."*
- **Mitigation / Architecture**: Normal web URLs (`http://*`, `https://*`) and local files (`file://*` with "Allow access to file URLs" enabled) operate with full capability.

### 3.2 Dynamic Cross-Origin iframes
- **Constraint**: By default, content scripts running in the top frame cannot inspect DOM trees inside cross-origin `<iframe>` elements (e.g., third-party payment gateway forms) due to the Same-Origin Policy.
- **Behavior**: The DOM observer captures the iframe element container but cannot read inner inputs without specific all-frames permissions.
- **Mitigation / Architecture**: The Action Gate recognizes embedded payment gateways as high-risk sensitive surfaces and immediately requests user approval or takeover.

---

## 4. Meta Cloud Network Connectivity

### 4.1 Internet Access Requirement for Hosted Features
- **Constraint**: High-fidelity multimodal visual verification (`muse-wonder-1.0`), semantic planning (`muse-spark-1.3`), and streaming voice transcription (`muse-voice-1.0`) rely on Meta's Cloud API endpoints.
- **Behavior**: If the host laptop loses internet connectivity, outbound requests to `api.meta.ai` fail.
- **Mitigation / Architecture**: Sahaay gracefully switches to local deterministic mode (`_generate_deterministic_local_plan`), enabling offline task execution for known templates (Notepad automation, local file inspection) with zero synthetic hallucinations.

---

## 5. Security & Permission Boundaries

### 5.1 Credential & Secret Redaction
- **Constraint**: The `PrivacyGateway` aggressively redacts high-entropy strings, JWT tokens, AWS/GCP keys, and passwords.
- **Behavior**: If a user prompts: *"Log in using my password MySecretPassword123!"*, the secret scanner intercepts the prompt and prevents egress to cloud models.
- **Recommendation**: Authentication operations should always be completed using manual handoff or password managers.

