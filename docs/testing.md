# Sahaay Testing & Quality Baseline Guide

## 1. Test Suite Architecture

The automated test suite across Python and .NET validates the security invariants and state machine of Sahaay:

| Test Module | Coverage Scope | Command |
| :--- | :--- | :--- |
| `tests/unit/test_health_and_capabilities.py` | Validates health diagnostics and proves `/capabilities` reports only genuine available features | `pytest tests/unit/test_health_and_capabilities.py` |
| `tests/unit/test_contracts.py` | Verifies Pydantic contract validation rejects malformed types and out-of-range fields | `pytest tests/unit/test_contracts.py` |
| `tests/unit/test_orchestrator.py` | Verifies state machine transitions, rejects illegal transitions, and ensures cancellation blocks future actions | `pytest tests/unit/test_orchestrator.py` |
| `tests/unit/test_action_gate.py` | Verifies Action Gate denies shell execution, unknown actions, and out-of-scope targets | `pytest tests/unit/test_action_gate.py` |
| `tests/privacy/test_privacy_gateway.py` | Verifies Local-Only Mode fails closed, classifies PII/Credentials, and blocks leaks | `pytest tests/privacy/test_privacy_gateway.py` |
| `tests/unit/test_sources_and_retrieval.py` | Verifies source authorization, fail-closed revocation, and provenance derivation chains | `pytest tests/unit/test_sources_and_retrieval.py` |
| `tests/unit/test_verification_and_ledger.py` | Enforces the invariant: **Model self-attestation is rejected**, tests state conflicts, and validates Evidence Ledger | `pytest tests/unit/test_verification_and_ledger.py` |
| `tests/unit/test_windows_endpoints.py` | Verifies `/api/v1/windows` discovery, active foreground query, UI inspection, text setting, and graceful offline fallback | `pytest tests/unit/test_windows_endpoints.py` |
| `tests/unit/test_browser_endpoints.py` | Verifies real tab observation ingestion, bounded scroll action authorization, postcondition verification, and cancellation denial | `pytest tests/unit/test_browser_endpoints.py` |
| `tests/unit/test_deterministic_retrieval.py` | Verifies deterministic keyword search, snippet extraction, and exclusion of revoked sources (zero AI models) | `pytest tests/unit/test_deterministic_retrieval.py` |
| `tests/unit/test_document_ingestion.py` | Validates local file parsing (.txt, .md, .pdf), page/paragraph chunking, checksum verification, 10MB limit, and sensitive path denial | `pytest tests/unit/test_document_ingestion.py` |
| `tests/unit/test_combined_and_retrieval_tasks.py` | Verifies retrieval-only action blocking, combined verification-before-action flow, and conflict-induced user handoff | `pytest tests/unit/test_combined_and_retrieval_tasks.py` |
| `tests/security/test_prompt_injection_defense.py` | Validates untrusted content isolation; verifies prompt-injection in pages/docs cannot grant permissions, change tasks, or run commands | `pytest tests/security/test_prompt_injection_defense.py` |
| `tests/browser/test_extension_contracts.py` | Verifies extension message schema, command allowlist (`fill_form_fields`, `get_field_values`), and 1MB size limit | `pytest tests/browser/test_extension_contracts.py` |
| `tests/desktop/test_native_host_contracts.py`| Verifies native host stdio 4-byte framing and command allowlist | `pytest tests/desktop/test_native_host_contracts.py` |
| `tests/security/test_secret_scanning.py` | Scans all repository files to ensure no API keys, private keys, or tokens are committed | `pytest tests/security/test_secret_scanning.py` |
| `tests/unit/test_meta_models.py` | Validates MetaClient, Muse Spark Indic language understanding/planning, Muse Wonder computer tool call parsing, Voice transcription confirmation, SAM 3.1 visual grounding, and Privacy Gateway | `pytest tests/unit/test_meta_models.py` |
| `tests/unit/test_local_llama.py` | Validates local Llama runtime lifecycle, hardware profiling (CPU, RAM, GPU/CUDA), loopback binding, and truthful missing-weights status reporting | `pytest tests/unit/test_local_llama.py` |
| `tests/unit/test_cross_surface_workflows.py` | Validates Browser → Desktop and Desktop → Browser end-to-end execution, provenance recording, independent verification, and diagnostics | `pytest tests/unit/test_cross_surface_workflows.py` |
| `apps/windows-companion/tests` (.NET) | Verifies native host 4-byte message framing, oversized payload rejection, origin allowlist, Named Pipe protocol, and SetControlText/GetControlText validation | `dotnet test apps/windows-companion/Sahaay.sln` |

---

## 2. Running Quality Checks

### Run All Test Suites via Master Script
```powershell
.\scripts\run-tests.ps1
```

### Run Python Test Suite
```powershell
$env:PYTHONPATH = "core/src"
.\core\.venv\Scripts\pytest.exe tests
```

### Run .NET Companion Test Suite
```powershell
$env:PATH = "$env:LOCALAPPDATA\Microsoft\dotnet;$env:PATH"
dotnet test apps\windows-companion\Sahaay.sln
```

### Run Python Linting & Formatting (Ruff)
```powershell
.\core\.venv\Scripts\ruff.exe check core tests
.\core\.venv\Scripts\ruff.exe format --check core tests
```

### Typecheck & Build Desktop Renderer
```powershell
cd apps\desktop
npm run typecheck
npm run build
```

### Typecheck & Build Browser Extension
```powershell
cd apps\browser-extension
npm run typecheck
npm run build
```

---

## 3. Real Execution Verification (Milestone 04 — Meta Models, Local Runtime & Liquid Glass UI)

> [!NOTE]
> - **Exercised & Tested in Milestone 04**:
>   - **Meta Provider Adapters**: Real async client for `https://api.meta.ai/v1`, bearer token redaction, bounded retries, connectivity check.
>   - **Muse Spark**: Multilingual Indic semantic understanding (Kannada, Hindi, code-switched), grounded context extraction, contradiction detection, and structured typed planning.
>   - **Muse Wonder**: Computer-use adapter parsing Meta Responses API `computer` tool protocol, strictly validating coordinate boundaries against screen resolution, and mapping proposals to typed ActionContracts.
>   - **Muse Voice Transcribe**: Speech-to-text pipeline with Indic language biasing and mandatory editable transcript confirmation dialog prior to any execution.
>   - **SAM 3.1**: Visual element grounding adapter mapping target element descriptions to bounding boxes and center coordinates with observation versions.
>   - **Local Llama 3.2 3B Runtime**: Process management on `127.0.0.1:8080`, hardware profiling (CPU, RAM, NVIDIA RTX 3050 CUDA detection), truthful status reporting (`MODEL_FILE_MISSING`, `READY`, etc.).
>   - **Browser → Desktop Execution**: Synthetic BESCOM bill ingested from browser tab, facts grounded in SHA-256 provenance, populated into desktop target via controller `set_control_text`, read back and verified.
>   - **Desktop → Browser Execution**: Synthetic invoice ingested from local JSON, fields mapped and populated into web form via extension `fill_form_fields`, verified readback (`get_field_values`), auto-submit blocked.
>   - **Liquid Glass Living Execution Surface**: Deep obsidian background, translucent glassmorphism, living liquid-flow canvas animated to live backend events (`IDLE`, `OBSERVE`, `RETRIEVE`, `PROPOSE`, `AUTHORIZE`, `EXECUTE`, `VERIFY`, `VERIFIED`, `FAILED`/`HANDOFF`), full `prefers-reduced-motion` support.
>   - **Full Automated Suite**: 64 Python tests, 9 .NET companion tests, browser extension build, and desktop app build passing with zero errors.

---

## 4. Manual Real-Environment Acceptance Checklist

For evaluators verifying on a live Windows machine:

1. **Application Startup & Database Readiness**:
   - Start backend: `uvicorn sahaay_core.main:app --host 127.0.0.1 --port 8000`.
   - Verify `GET http://127.0.0.1:8000/api/v1/health` returns `status: "healthy"` and `databaseReady: true`.
2. **Local Llama Readiness**:
   - If `llama-server.exe` and `Llama-3.2-3B-Instruct-Q4_K_M.gguf` are installed, configure paths in settings.
   - Verify `GET http://127.0.0.1:8000/api/v1/models/status` transitions to `READY`. If not installed, verify it truthfully reports `MODEL_FILE_MISSING` or `RUNTIME_MISSING`.
3. **Meta Model Live Inference Test**:
   - When `MODEL_API_KEY` is provided, run `POST http://127.0.0.1:8000/api/v1/models/test-connectivity`. Verify `status: "CONNECTED"`.
   - Without key, verify truthful status `NOT_CONFIGURED` without leaking credentials.
4. **Voice Transcription with Editable Confirmation**:
   - In Desktop UI, click the microphone button. Speak a phrase or select synthetic audio.
   - Verify the transcription appears in an editable modal dialog requiring explicit user approval before execution.
5. **Windows Controller UI Automation**:
   - Launch Windows Companion: `dotnet run --project apps/windows-companion/Sahaay.Controller`.
   - Verify UI elements and open windows are discoverable via `GET http://127.0.0.1:8000/api/v1/windows`.
6. **Browser Tab Observation via Native Host**:
   - Load unpacked extension into Chrome/Edge; run `register-native-host.ps1`.
   - Open `http://127.0.0.1:8000/fixtures/utility_bill.html`.
   - Ingest observation via `POST http://127.0.0.1:8000/api/v1/browser/tabs/active/observe`.
7. **Browser → Desktop Workflow Execution**:
   - Run 1-click Browser → Desktop runner in UI or `POST http://127.0.0.1:8000/api/v1/workflows/browser-to-desktop`.
   - Observe live liquid flow transitions: `OBSERVE -> PROPOSE -> AUTHORIZE -> EXECUTE -> VERIFY -> VERIFIED`.
   - Verify extracted fields (`BLR-UTIL-98421`, `Aarav Sharma`, `INR 2,450.00`) are verified in the desktop target.
8. **Desktop → Browser Workflow Execution**:
   - Run 1-click Desktop → Browser runner in UI or `POST http://127.0.0.1:8000/api/v1/workflows/desktop-to-browser`.
   - Verify web form is populated and verified. Verify form is NOT automatically submitted.
9. **Independent Verification & Evidence Ledger**:
   - Check SQLite database table `evidence_records`. Verify entry has `verification_status: "VERIFIED"` based on actual data readback, not model self-attestation.
10. **Error, Denial & Cancellation Recovery**:
    - Deny an authorization request or cancel a task. Verify the liquid surface transitions to `CANCELLED`/`FAILED` and all future actions are blocked.
