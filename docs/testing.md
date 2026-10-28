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
| `tests/unit/test_windows_endpoints.py` | Verifies `/api/v1/windows` discovery, active foreground query, UI inspection, and graceful offline fallback | `pytest tests/unit/test_windows_endpoints.py` |
| `tests/unit/test_browser_endpoints.py` | Verifies real tab observation ingestion, bounded scroll action authorization, postcondition verification, and cancellation denial | `pytest tests/unit/test_browser_endpoints.py` |
| `tests/unit/test_deterministic_retrieval.py` | Verifies deterministic keyword search, snippet extraction, and exclusion of revoked sources (zero AI models) | `pytest tests/unit/test_deterministic_retrieval.py` |
| `tests/unit/test_document_ingestion.py` | Validates local file parsing (.txt, .md, .pdf), page/paragraph chunking, checksum verification, 10MB limit, and sensitive path denial | `pytest tests/unit/test_document_ingestion.py` |
| `tests/unit/test_combined_and_retrieval_tasks.py` | Verifies retrieval-only action blocking, combined verification-before-action flow, and conflict-induced user handoff | `pytest tests/unit/test_combined_and_retrieval_tasks.py` |
| `tests/security/test_prompt_injection_defense.py` | Validates untrusted content isolation; verifies prompt-injection in pages/docs cannot grant permissions, change tasks, or run commands | `pytest tests/security/test_prompt_injection_defense.py` |
| `tests/browser/test_extension_contracts.py` | Verifies extension message schema, command allowlist, and 1MB size limit | `pytest tests/browser/test_extension_contracts.py` |
| `tests/desktop/test_native_host_contracts.py`| Verifies native host stdio 4-byte framing and command allowlist | `pytest tests/desktop/test_native_host_contracts.py` |
| `tests/security/test_secret_scanning.py` | Scans all repository files to ensure no API keys, private keys, or tokens are committed | `pytest tests/security/test_secret_scanning.py` |
| `apps/windows-companion/tests` (.NET) | Verifies native host 4-byte message framing, oversized payload rejection, origin allowlist, and Named Pipe protocol | `dotnet test apps/windows-companion/Sahaay.sln` |

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

## 3. Real Execution Verification (Milestone 03 — Product Hardening & Unified Experience)

> [!NOTE]
> - **Exercised & Tested in Milestone 03**:
>   - Unified Desktop Experience: Single task and conversation console with mode switcher (`retrieval_only`, `action_only`, `combined_verify_action`), active scope drawer, and immutable evidence ledger.
>   - Local Document Ingestion: Safe local file parsing for `.txt`, `.md`, and `.pdf` via `pypdf`, chunking paragraphs/pages, extracting SHA-256 fingerprints, and blocking sensitive paths.
>   - Deterministic Retrieval: Exact keyword matching with confidence scoring, match location, rich source provenance, and clear limitation disclaimer.
>   - Tab Staleness Tracking: Navigation detection requiring re-observation (`PolicyDecisionEnum.REOBSERVE`) before allowing tab-specific actions.
>   - Combined Workflows: Verifying prerequisite facts in sources before executing actions; halting with user handoff on contradiction.
>   - Adversarial Defense: Untrusted webpage and document content cannot grant permissions, invoke native commands, or modify task state.
>   - .NET 10 LTS native companion build (`Sahaay.Contracts`, `Sahaay.Controller`, `Sahaay.NativeHost`).
>   - Authenticated `\\.\pipe\SahaayControllerPipe` IPC bridge and HKCU registration scripts (`register-native-host.ps1`).
>   - Full automated test suite: 50 Python tests, 8 .NET companion tests, browser extension typecheck, and desktop app build passing with zero errors.
> - **Explicitly Deferred to Stage 04**: Multimodal Meta model inference (Llama, Muse Transcribe, Muse Spark). All external model API calls remain disabled and fail closed.
