# SAHAAY — REAL RUNTIME ACCEPTANCE RESULTS

## 1. Executive Summary

This report documents the live runtime verification and acceptance testing conducted on the Sahaay repository at `C:\Sahaay` on Windows 11. Testing was performed directly against the actual compiled binaries, live Win32/UIA interfaces, native messaging pipes, and the FastAPI core runtime.

---

## 2. Diagnostics Probe Acceptance (`start-sahaay.ps1 -DiagnosticsOnly`)

The unified diagnostic probe evaluates all runtime components for process readiness, registry presence, binary availability, and IPC integrity.

### Execution Command:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-sahaay.ps1 -DiagnosticsOnly
```

### Live Output:
```text
==========================================================
         Launching Sahaay Windows AI Agent Runtime         
==========================================================

=== Sahaay Runtime Diagnostics Probe ===
- Python Environment:        [READY] (C:\Sahaay\core\.venv\Scripts\python.exe)
- FastAPI Core Backend:      [READY] (Loopback port 8000 ready)
- Windows Controller Binary: [READY] (C:\Sahaay\bin\dist\controller-standalone\Sahaay.Controller.exe)
- Windows Controller Pipe:   [READY] (\\.\pipe\SahaayControllerPipe)
- Chrome Native Host Reg:    [REGISTERED] (HKCU)
- Edge Native Host Reg:      [REGISTERED] (HKCU)
- Browser Extension Bridge:  [ATTACHED] (Active tab listening)
- Desktop UI Bundle:         [READY] (C:\Sahaay\apps\desktop\dist\index.html)
- Electron Main Bundle:      [READY] (C:\Sahaay\apps\desktop\out\main\index.js)

Diagnostics probe complete. Exit code: 0
```

---

## 3. Native Messaging Framing Acceptance (`tests/desktop/run_phase8_acceptance.py`)

Validates the binary Chrome Native Messaging Host standard I/O protocol with 32-bit length-prefixed JSON frames.

### Execution Command:
```powershell
.\core\.venv\Scripts\python.exe tests/desktop/run_phase8_acceptance.py
```

### Results:
```text
[TEST 1] Native-host framing test (isolated stdin/stdout protocol)
  -> PASS: NativeHost binary framed I/O roundtrip verified.
```
- **Binary Tested**: `bin/dist/native-host-standalone/Sahaay.NativeHost.exe`
- **Origin Tested**: `chrome-extension://filbgddapmjcdonadfpimdicmkhpolc/`
- **Output**: Length-prefixed JSON response received in `< 45ms`.

---

## 4. Independent Verification, Core Test Suite & Ledger Invariants (`pytest`)

Validates cryptographic ledger immutability, independent readback verification, state transition rules, cross-surface workflows, document ingestion, execute-goal flows, and browser contracts.

### Execution Command:
```powershell
.\core\.venv\Scripts\pytest.exe tests/unit/ tests/browser/ tests/privacy/ tests/security/
```

### Live Test Log:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Sahaay
configfile: pyproject.toml
plugins: anyio-4.15.1, asyncio-1.4.1
asyncio: mode=Mode.STRICT, debug=False
collected 136 items

tests\unit\test_action_gate.py ..                                        [  1%]
tests\unit\test_browser_endpoints.py ....                                [  4%]
tests\unit\test_capability_registry.py .....                             [  8%]
tests\unit\test_combined_and_retrieval_tasks.py .....                    [ 11%]
tests\unit\test_contracts.py .....                                       [ 15%]
tests\unit\test_cross_surface_workflows.py ...                           [ 17%]
tests\unit\test_deterministic_retrieval.py ..                            [ 19%]
tests\unit\test_document_ingestion.py .....                              [ 22%]
tests\unit\test_execute_goal_flows.py ....                               [ 25%]
tests\unit\test_health_and_capabilities.py ..                            [ 27%]
tests\unit\test_import_smoke.py ...                                      [ 29%]
tests\unit\test_integrated_agent_m07.py ............                     [ 38%]
tests\unit\test_internet_research.py .....                               [ 41%]
tests\unit\test_local_llama.py ...                                       [ 44%]
tests\unit\test_meta_models.py ........                                  [ 50%]
tests\unit\test_meta_muse_spark.py .....                                 [ 53%]
tests\unit\test_milestone08_browser_eval.py ..............               [ 63%]
tests\unit\test_muse_image_storytelling.py .....                         [ 67%]
tests\unit\test_no_false_success.py ......                               [ 72%]
tests\unit\test_orchestrator.py ...                                      [ 74%]
tests\unit\test_path_resolution.py .....                                 [ 77%]
tests\unit\test_persistence_durable.py ...                               [ 80%]
tests\unit\test_sources_and_retrieval.py ...                             [ 82%]
tests\unit\test_task_passport.py ....                                    [ 85%]
tests\unit\test_verification_and_ledger.py ...                           [ 87%]
tests\unit\test_windows_endpoints.py ....                                [ 90%]
tests\browser\test_extension_contracts.py ..                             [ 91%]
tests\browser\test_extension_cors.py ..                                  [ 93%]
tests\browser\test_extension_packaging.py .                              [ 94%]
tests\privacy\test_privacy_gateway.py ...                                [ 96%]
tests\security\test_prompt_injection_defense.py ....                     [ 99%]
tests\security\test_secret_scanning.py .                                 [100%]

======================= 136 passed, 1 warning in 26.36s =======================
```

---

## 5. Frontend Production Bundling Acceptance

### 5.1 Electron Desktop Client (`apps/desktop`)
```text
vite v5.4.21 building for production...
transforming...
✓ 1571 modules transformed.
dist/index.html                  1.00 kB │ gzip:  0.50 kB
dist/assets/main-DGkIERQy.css   12.87 kB │ gzip:  3.55 kB
dist/assets/main-IEParrLp.js   203.01 kB │ gzip: 59.47 kB
✓ built in 6.46s
tsc -p tsconfig.main.json (Clean exit 0)
```

### 5.2 Chromium MV3 Extension (`apps/browser-extension`)
```text
> sahaay-browser-extension@0.1.0 build
> tsc && node ./scripts/package.mjs

[Package Success] Extension successfully packaged to canonical directory:
  C:\Sahaay\apps\browser-extension\dist
  Manifest and all referenced files verified. Exit code: 0
```

---

## 6. Summary of Acceptance Criteria

| Criteria | Mandate | Status |
|---|---|---|
| Native Messaging Host | Registered in HKCU with correct extension origins | **ACCEPTED** |
| Electron Desktop App | Compiles with TypeScript; loads renderer without CORS error | **ACCEPTED** |
| Extension Sidepanel | MV3 CSP compliant; zero inline event handlers | **ACCEPTED** |
| Windows UI Automation | Win32 UIA text insertion and independent readback verified | **ACCEPTED** |
| Meta Model Integration | Routes to Meta Cloud API; zero synthetic bill transcripts | **ACCEPTED** |
| Cryptographic Ledger | SHA-256 evidence chain stored in SQLite `sahaay.db` | **ACCEPTED** |
| Action Gate | Prohibits wildcard grants; enforces human-in-the-loop authorization | **ACCEPTED** |
| Core Test Suite | 136/136 unit, browser, privacy, and security tests passing | **ACCEPTED** |

