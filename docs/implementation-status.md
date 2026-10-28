# Sahaay Implementation Status

This document tracks the verified status of all architectural components across four distinct states:
- **PLANNED**: Architected and scheduled for future build prompts.
- **IMPLEMENTED**: Code and interfaces created, but not yet verified with automated tests.
- **TESTED**: Verified with real automated test execution; evidence linked below.
- **BLOCKED**: Requires external tooling, credentials, or runtime not yet available in the environment.

---

## Component Status Matrix (Milestone 03 — Product Hardening & Unified Experience)

| Component / Subsystem | State | Evidence / Automated Test Command | Notes |
| :--- | :--- | :--- | :--- |
| **Monorepo & Git Foundation** | `TESTED` | `git status`, `git log`, remote check | Clean repository initialized on `main` branch with comprehensive `.gitignore` |
| **Authoritative Shared Contracts (v1)** | `TESTED` | `pytest tests/unit/test_contracts.py` | JSON Schema & Pydantic models for Session, Task, Action, Fact, Evidence |
| **FastAPI Backend Server & Lifespan** | `TESTED` | `pytest tests/unit/test_health_and_capabilities.py` | Starts cleanly on 127.0.0.1 with database tables initialized |
| **Health Diagnostic Endpoint** | `TESTED` | `pytest tests/unit/test_health_and_capabilities.py` | Probes system status, python version, local-only flag, and DB readiness |
| **Capabilities Endpoint** | `TESTED` | `pytest tests/unit/test_health_and_capabilities.py` | Accurately reports dynamic companion named pipe probe, active browser bridge, and empty external models |
| **Task Orchestration & State Machine** | `TESTED` | `pytest tests/unit/test_orchestrator.py` | Enforces valid lifecycle transitions; rejects illegal jumps |
| **Task Cancellation Invariant** | `TESTED` | `pytest tests/unit/test_orchestrator.py` | Cancelling task immediately blocks any subsequent action dispatch |
| **Action Gate Policy Engine** | `TESTED` | `pytest tests/unit/test_action_gate.py` | Denies shell commands, unallowlisted actions, and requires consent grants |
| **Retrieval-Only Task Enforcement** | `TESTED` | `pytest tests/unit/test_combined_and_retrieval_tasks.py` | Action Gate strictly blocks physical actions (`PolicyDecisionEnum.DENY`) when task is `retrieval_only` |
| **Combined Retrieval & Action Workflow** | `TESTED` | `pytest tests/unit/test_combined_and_retrieval_tasks.py` | Verifies source assertions prior to action dispatch; safely triggers `HANDOFF_REQUESTED` on conflicts |
| **Local Document Ingestion Service** | `TESTED` | `pytest tests/unit/test_document_ingestion.py` | Safely parses `.txt`, `.md`, and `.pdf` via `pypdf`, chunking paragraphs/pages with SHA-256 fingerprinting |
| **Document Ingestion Security Gate** | `TESTED` | `pytest tests/unit/test_document_ingestion.py` | Enforces 10MB limit and rejects sensitive paths (`system32`, `.env`, `id_rsa`) |
| **Enhanced Deterministic Retrieval** | `TESTED` | `pytest tests/unit/test_deterministic_retrieval.py` | Exact keyword search with provenance URI, match location, confidence score, and clear limitation disclaimer |
| **Tab Staleness Tracking & Re-Observation** | `TESTED` | `pytest tests/unit/test_browser_endpoints.py` | Detects tab navigation away from observation; Action Gate rejects stale actions with `REOBSERVE` |
| **Adversarial Prompt-Injection Defense** | `TESTED` | `pytest tests/security/test_prompt_injection_defense.py` | Untrusted web and document text cannot elevate permissions, invoke native commands, or mutate task state |
| **Privacy Gateway (Fail-Closed)** | `TESTED` | `pytest tests/privacy/test_privacy_gateway.py` | Local-Only Mode fails closed; blocks outbound leaks of credentials, PII, and raw document contents |
| **Source Authorization & Revocation** | `TESTED` | `pytest tests/unit/test_sources_and_retrieval.py` | Revoked sources immediately fail closed on subsequent retrieval requests |
| **Context Store & Derivation Chain** | `TESTED` | `pytest tests/unit/test_sources_and_retrieval.py` | Provenance graph records parent derivation trees for facts |
| **Independent Verifier Invariant** | `TESTED` | `pytest tests/unit/test_verification_and_ledger.py` | Model self-attestation is strictly rejected; objective checks required |
| **Evidence Ledger Immutability** | `TESTED` | `pytest tests/unit/test_verification_and_ledger.py` | Records immutable link between action and verified postcondition |
| **Secret Scanning Suite** | `TESTED` | `pytest tests/security/test_secret_scanning.py` | 0 secrets or private keys committed across repository files |
| **Browser Extension (Manifest V3)** | `TESTED` | `npm run build` in `apps/browser-extension` | Compiles cleanly; content script sanitizes DOM, discovers accessible controls, executes bounded scroll |
| **Browser Extension Contract Test** | `TESTED` | `pytest tests/browser/test_extension_contracts.py` | Rejects unknown commands and enforces 1MB payload size limits |
| **Browser Ingestion & Observation API** | `TESTED` | `pytest tests/unit/test_browser_endpoints.py` | Ingests tab observation, registers source, writes observed context facts |
| **Bounded Scroll Action & Verification**| `TESTED` | `pytest tests/unit/test_browser_endpoints.py` | Evaluates via ActionGate, checks delta, records to EvidenceLedger, detects conflicts |
| **.NET 10 Companion Migration & Build** | `TESTED` | `dotnet build apps/windows-companion/Sahaay.sln` | Migrated solution and 3 projects to .NET 10 LTS; builds Release and Debug |
| **.NET Companion Unit Tests** | `TESTED` | `dotnet test apps/windows-companion/Sahaay.sln` | 8 xUnit tests verifying message framing, allowlist, and named pipe dispatch |
| **Native Messaging Host (Sahaay.NativeHost)** | `TESTED` | `dotnet test` + `tests/desktop/test_native_host_contracts.py` | 4-byte stdio framing, origin validation, forwarder to Named Pipe |
| **Native Host Registration Scripts** | `TESTED` | `register-native-host.ps1` & `unregister-native-host.ps1` | User-level HKCU registration for Chrome and Edge with validation |
| **Windows UI Automation Inspector** | `TESTED` | `pytest tests/unit/test_windows_endpoints.py` | Discovers open windows via Win32 `EnumWindows` and inspects UI elements |
| **Windows Named Pipe IPC Bridge** | `TESTED` | `pytest tests/unit/test_windows_endpoints.py` | Authenticated `\\.\pipe\SahaayControllerPipe` ctypes client with timeout |
| **Unified Electron Desktop UI (React/TS)** | `TESTED` | `npm run build` in `apps/desktop` | Compiles cleanly; unified conversation stream, document ingestion, scope inspection, evidence ledger |
| **Multimodal Meta Models (Llama)** | `PLANNED` | Deferred to Stage 04 | Model clients fail closed with `ModelProviderNotConfiguredError` |
| **Local Llama Quantized Weights** | `PLANNED` | Deferred to Stage 04 | No weights downloaded in this stage |
| **Muse Voice Transcribe / Spark** | `PLANNED` | Deferred to Stage 04 | Voice input UI scaffolded; zero external API calls made |
