# Sahaay Testing & Quality Baseline Guide

## 1. Test Suite Architecture

The automated test suite in `tests/` validates the security invariants and state machine of Sahaay:

| Test Module | Coverage Scope | Command |
| :--- | :--- | :--- |
| `tests/unit/test_health_and_capabilities.py` | Validates health diagnostics and proves `/capabilities` reports only genuine available features | `pytest tests/unit/test_health_and_capabilities.py` |
| `tests/unit/test_contracts.py` | Verifies Pydantic contract validation rejects malformed types and out-of-range fields | `pytest tests/unit/test_contracts.py` |
| `tests/unit/test_orchestrator.py` | Verifies state machine transitions, rejects illegal transitions, and ensures cancellation blocks future actions | `pytest tests/unit/test_orchestrator.py` |
| `tests/unit/test_action_gate.py` | Verifies Action Gate denies shell execution, unknown actions, and out-of-scope targets | `pytest tests/unit/test_action_gate.py` |
| `tests/privacy/test_privacy_gateway.py` | Verifies Local-Only Mode fails closed, classifies PII/Credentials, and blocks leaks | `pytest tests/privacy/test_privacy_gateway.py` |
| `tests/unit/test_sources_and_retrieval.py` | Verifies source authorization, fail-closed revocation, and provenance derivation chains | `pytest tests/unit/test_sources_and_retrieval.py` |
| `tests/unit/test_verification_and_ledger.py` | Enforces the invariant: **Model self-attestation is rejected**, tests state conflicts, and validates Evidence Ledger | `pytest tests/unit/test_verification_and_ledger.py` |
| `tests/browser/test_extension_contracts.py` | Verifies extension message schema, command allowlist, and 1MB size limit | `pytest tests/browser/test_extension_contracts.py` |
| `tests/desktop/test_native_host_contracts.py`| Verifies native host stdio 4-byte framing and command allowlist | `pytest tests/desktop/test_native_host_contracts.py` |
| `tests/security/test_secret_scanning.py` | Scans all repository files to ensure no API keys, private keys, or tokens are committed | `pytest tests/security/test_secret_scanning.py` |

---

## 2. Running Quality Checks

### Run All Pytest Tests
```powershell
.\core\.venv\Scripts\pytest.exe tests
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

## 3. Scaffolding vs. Real End-to-End Testing

> [!IMPORTANT]
> Test scaffolding is not the same as testing the full product.
> - **Exercised & Tested in Build 01**: Backend REST API, database schema, Task Orchestrator state machine, Action Gate deterministic authorization, Privacy Gateway fail-closed policy, Source revocation, Evidence Ledger, Secret scanning, Browser Extension build, and Desktop Electron/React build.
> - **Explicitly Scaffolding in Build 01**: Windows UI Automation control, live browser tab DOM extraction, and multimodal model inference. These are marked as `UNIMPLEMENTED` / `BLOCKED` until real adapters and models are connected in future stages.
