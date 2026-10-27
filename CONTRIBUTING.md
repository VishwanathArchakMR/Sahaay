# Contributing to Sahaay

Thank you for contributing to Sahaay. Please review our architectural invariants, coding guidelines, and pull request policies before submitting code.

---

## 1. Architectural Invariants
Every contribution must strictly adhere to these finalized design rules:
1. **Unified System**: Do not build disconnected products for chat and computer use. Every feature must integrate into the common task orchestrator, context model, Action Gate, and Evidence Ledger.
2. **Deterministic Action Gate**: Models propose; deterministic code authorizes. No webpage, PDF, or model output may expand task scope or execute unallowlisted operations.
3. **No Shell Execution**: General-purpose command line and PowerShell execution are strictly prohibited from exposure to models or public APIs.
4. **Privacy Fail-Closed**: In Local-Only Mode, external network requests must fail closed. Credential patterns must never be transmitted externally.
5. **Independent Verification**: A model declaring its own success is never acceptable proof of completion.

---

## 2. Development Workflow
1. Check existing environment diagnostics:
   ```powershell
   .\scripts\verify-environment.ps1
   ```
2. Make targeted modifications within the appropriate monorepo workspace (`apps/desktop`, `apps/browser-extension`, `apps/windows-companion`, or `core`).
3. Run automated tests and code linters before committing:
   ```powershell
   .\scripts\run-tests.ps1
   ```
4. Verify that `docs/implementation-status.md` is updated accurately whenever component status shifts between `PLANNED`, `IMPLEMENTED`, `TESTED`, and `BLOCKED`.
5. Ensure no secrets, API keys, or private files are staged.

---

## 3. Commit Message Conventions
Follow Conventional Commits format:
- `feat:` New capability or endpoint
- `fix:` Bug fix or security remediation
- `chore:` Maintenance, setup, or baseline initialization
- `docs:` Documentation updates
- `test:` Unit or integration test additions
