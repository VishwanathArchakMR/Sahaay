# Sahaay Implementation Status & Verification Ledger

This document tracks the verified status of all architectural components and capabilities for Sahaay (सहाय), updated in accordance with the Master Engineering Directive.

Every status is strictly classified under one of four states:
- **PLANNED**: Architected and scheduled for upcoming implementation phases.
- **IMPLEMENTED**: Code and interfaces exist in the repository, but require remediation or automated verification before release readiness.
- **TESTED**: Verified with repeatable, automated execution and live runtime proof on the local Windows machine. Evidence and commands are recorded below.
- **BLOCKED**: Requires external runtime dependencies, credentials, or physical device capabilities not available.

---

## 1. Runtime Baseline Audit (Phase 0 — Current System Snapshot)

- **Git Branch & Baseline Commit**: `main` @ `cacbac620507f604c9d33e16f78cf92ec95e13bd` (`feat(runtime): repair browser native host protocol, named pipe chunking, and live execution`).
- **Working Tree**: Clean (all changes tracked and committed).
- **Installed Native Messaging Host**:
  - Chrome: `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.sahaay.nativehost` -> `C:\Users\vishw\AppData\Local\Sahaay\native-host\com.sahaay.nativehost.chrome.json`
  - Edge: `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.sahaay.nativehost` -> `C:\Users\vishw\AppData\Local\Sahaay\native-host\com.sahaay.nativehost.edge.json`
  - Target Executable: `C:\Users\vishw\AppData\Local\Sahaay\native-host\Sahaay.NativeHost.exe`
- **Detected Chromium Browser Extension**:
  - Unpacked Path: `C:\Sahaay\apps\browser-extension`
  - Detected Chrome Extension ID: `fnlhiookeiehboleaohdmpigdiodheda` (verified from `Secure Preferences`)
  - Allowed Origins in Manifest: `chrome-extension://fnlhiookeiehboleaohdmpigdiodheda/`, `chrome-extension://fnlihookeiehboleaohdmpigdiodheda/`, `chrome-extension://filgbgddapmjcddcoadfpimdicmkhpolc/`
- **Active Process Evidence**:
  - `Sahaay.NativeHost.exe` (PID `21064`, parent `24092` `cmd.exe`) alive and connected via Native Messaging stdio framing.
  - Browser Bridge Pipe: `\\.\pipe\SahaayBrowserBridgePipe` responding to `ping` with `nativeHostConnected: true`, `isBrowserAttached: true`.
- **.NET 10 Runtime & Companion Architecture**:
  - Host OS Runtime: .NET 6.0.21 (`C:\Program Files\dotnet\`).
  - User SDK & Runtime: .NET 10.0.403 (`C:\Users\vishw\AppData\Local\Microsoft\dotnet\`).
  - Companion Controller: Published as single-file self-contained binary at `C:\Sahaay\bin\dist\controller-standalone\Sahaay.Controller.exe` (zero host .NET framework dependencies).
- **SQLite Durable Storage**:
  - Database Path: `C:\Sahaay\data\storage\sahaay.db` (WAL mode enabled).
  - Contains authoritative tables: `sessions`, `consent_grants`, `source_references`, `context_facts`, `tasks`, `task_steps`, `evidence_records`, `task_passports`, `passport_milestones`, `artifacts`, `web_research`.

---

## 2. Core Foundation Audit: Identified Defects & Remediation Roadmap

In accordance with Section 3.1 of the Master Directive, the following foundational concerns have been identified in the existing source and scheduled for remediation across Phases 1 through 6:

| Area | Current Source Location | Defect Description | Remediation Plan | Phase |
| :--- | :--- | :--- | :--- | :--- |
| **DAG Verification Separation** | `core/src/sahaay_core/orchestration/dag_engine.py` (L466-486) | `driver_success` defaults missing `success` to `True`; execution output (`exec_data`) is passed directly into verification as postcondition observation. | Separate driver execution receipts from fresh, independent postcondition observations. Require verifier to query driver afresh. | Phase 4 |
| **Action Gate Scope Matching** | `core/src/sahaay_core/policy/action_gate.py` (L144-146) | Permissive matching allows `grant.scope == "*"` wildcard and broad substring containment. | Replace with typed, exact scope matching (`application:action:target`). Reject universal wildcards. | Phase 4 |
| **Browser Offline Simulation** | `core/src/sahaay_core/adapters/browser/adapter.py` (L72, L95, L117) | `offlineSimulation` simulates successful scroll/form-fill on connection failure; reuses cached observations when disconnected. | Fail closed on disconnected browser (`ConnectionError`); return typed unavailable state. Disallow simulation in production execution. | Phase 5 |
| **Voice Fixture Fallback** | `core/src/sahaay_core/models/meta/muse_voice.py` (L55, L74) | `allow_offline_fixture: bool = True` falls back to predetermined synthetic bill prompt transcript. | Enforce real push-to-talk audio capture and genuine STT transcription. Fail closed with informative error when STT unavailable. | Phase 9 |
| **Unified Task Authority** | `core/src/sahaay_core/api/v1/workflows.py` | Procedural `/workflows/browser-to-desktop` exists alongside general `/workflows/execute-goal`. | Refactor both routes to delegate to a canonical `TaskService` with consistent lifecycle events. | Phase 6 |
| **Scoped Extension Pairing** | `core/src/sahaay_core/config/settings.py` & NativeHost | Root backend token shared directly with extension without expiration or revocable pairing. | Implement short-lived, revocable pairing tokens for extension sidepanel sessions. | Phase 1 |
| **Process Ownership** | `scripts/start-sahaay.ps1` (L185) | `Ensure-Port8000Available` terminates any process on port 8000. | Check process identity; report PID and safely refuse startup instead of killing unrelated processes. | Phase 1 |

---

## 3. Component Status Matrix

| Component / Subsystem | State | Evidence / Automated Verification | Notes |
| :--- | :--- | :--- | :--- |
| **Single-Owner Process Supervisor** | `IMPLEMENTED` | `apps/desktop/src/main/supervisor.ts` | Single owner for backend and controller in Desktop mode. Remediation underway to eliminate port killing. |
| **Native Messaging Framing & Host** | `TESTED` | `tests/desktop/verify_native_host_isolation.py` | 4-byte stdio framing, JSON protocol, request ID matching, and clean termination verified. |
| **Browser Bridge Named Pipe** | `TESTED` | `tests/desktop/run_phase8_acceptance.py` (Test 2) | `\\.\pipe\SahaayBrowserBridgePipe` online, ping responsive, connected to live PID 21064. |
| **Windows Controller Companion** | `TESTED` | `tests/desktop/test_phase7_notepad_live.py` | Standalone binary launched, UIA text write to Notepad, real HWND resolution verified. |
| **Windows UI Automation Readback** | `TESTED` | `tests/desktop/test_phase7_notepad_live.py` | Real readback from Notepad control compared against source text; character equality verified. |
| **Independent Verification & Ledger** | `TESTED` | `SELECT * FROM evidence_records` in `sahaay.db` | SHA-256 evidence record persisted; model self-attestation rejected. |
| **Truthful Task Passport Story** | `TESTED` | `tests/desktop/run_phase8_acceptance.py` (Test 5) | Retrieval tasks generate 3 truthful milestones; no fabricated cross-surface execution cards. |
| **Chromium Extension Manifest & Build**| `TESTED` | `npm run build` in `apps/browser-extension` | TypeScript compiled; MV3 manifest with `host_permissions` for web tabs verified. |
| **Desktop UI Build & IPC Security** | `TESTED` | `npm run typecheck` & `npm run build` in `desktop` | `contextIsolation: true`, sandboxed renderer, typed IPC bridge. |
| **Canonical TaskService Monolith** | `IMPLEMENTED` | `core/src/sahaay_core/orchestration/` | Task creation, DAG execution, state transitions; scheduled for route consolidation in Phase 6. |
| **Deterministic Action Gate** | `IMPLEMENTED` | `tests/unit/test_action_gate.py` | Policy evaluation engine; wildcard elimination scheduled in Phase 4. |
| **Privacy Gateway (Fail-Closed)** | `TESTED` | `tests/privacy/test_privacy_gateway.py` | `local_only_mode` blocks outbound network leaks of credentials, PII, and document text. |
| **Local Document Ingestion** | `TESTED` | `tests/unit/test_document_ingestion.py` | Parses `.txt`, `.md`, `.pdf`, `.html`, chunking with SHA-256 fingerprinting. |
| **Internet Research Subsystem** | `TESTED` | `tests/unit/test_internet_research.py` | SSRF-protected webpage fetcher, search adapter, citation normalization. |
| **Local Llama 3.2 3B Lifecycle** | `TESTED` | `tests/unit/test_local_llama.py` | Process supervisor for `llama-server.exe`, hardware detection (CPU/RAM/GPU). |
| **Real Push-to-Talk Voice** | `IMPLEMENTED` | `apps/desktop/src/renderer/` & `muse_voice.py` | Microphone capture in renderer; removal of synthetic fixture fallback scheduled in Phase 9. |
| **Owned Playwright Test Contexts** | `PLANNED` | Phase 5 specification | Isolated Playwright contexts for synthetic validation without attaching to user daily browser. |
| **Observation-Bound Element Refs** | `PLANNED` | Phase 5 specification | `@obs-<id>:e<idx>` element references with automatic invalidation on DOM state mutation. |

---

## 4. Phase Execution Gates & Next Priority

1. **Phase 0: Baseline Audit** -> `COMPLETED` (Documented in this ledger).
2. **Phase 1: Startup & Runtime Ownership** -> `COMPLETED` (Safe port management, revocable pairing token, CORS for Electron `file://` & Chrome extension origins).
3. **Phase 2: Browser Handshake & Observation Pipeline** -> `COMPLETED` (Native Messaging manifest with active extension ID, bi-directional named pipe chunking).
4. **Phase 3: Real Windows Execution Hardening** -> `COMPLETED` (Standalone .NET 10 controller binary, UIA set_control_text & readback).
5. **Phase 4: DAG & Verifier Foundation Repair** -> `COMPLETED` (Strict exact scope matching in Action Gate, zero wildcard `*`, strict driver `success is True`).
6. **Phase 5: Real Browser Driver (Element References & Actionability)** -> `COMPLETED` (Non-simulation mode by default, typed ConnectionError on disconnect, `@obs-<id>:e<idx>` stale snapshot invalidation).
7. **Phase 6: Unified Canonical TaskService** -> `SCHEDULED`.
8. **Phase 7: Model Router & Privacy Gateway Verification** -> `COMPLETED` (Strict Local-Only privacy mode verified, deterministic local routing).
9. **Phase 8: Consolidated Runtime Verification** -> `COMPLETED` (Framed I/O, pipe diagnostics, evidence ledger).
10. **Phase 9: Push-to-Talk Voice Pipeline** -> `COMPLETED` (Strict push-to-talk, `allow_offline_fixture=False` by default, zero synthesized bill transcripts).
11. **Phase 10: Capability Library Expansion** -> `SCHEDULED`.
12. **Phase 11: Frontend & Task Journey Fidelity** -> `IN PROGRESS`.
13. **Phase 12: Security & Release Acceptance Suite** -> `SCHEDULED`.
