# Sahaay (सहाय)

**A voice-first, system-wide Windows AI agent engineered for verified information retrieval and computer action execution.**

---

## Overview

Sahaay is an installed Windows desktop AI agent that helps users retrieve information, understand context, and complete authorized tasks across their real computer.

Sahaay delivers two equal core capabilities through a unified architecture:
1. **Information Retrieval & Context Understanding**: Seamlessly find information, extract context from permitted local files, browser tabs, and desktop applications, distinguish facts from inferences, and communicate uncertainty with source-linked provenance.
2. **Computer and Browser Task Execution**: Execute bounded actions across real applications, real browser sessions, and the local file system with independent verification.

### Core Architecture Invariant:
$$\text{OBSERVE} \longrightarrow \text{PROPOSE} \longrightarrow \text{AUTHORIZE} \longrightarrow \text{EXECUTE} \longrightarrow \text{VERIFY} \longrightarrow \text{RECORD}$$

* Models propose actions.
* The deterministic **Action Gate** authorizes actions against active consent grants and strict allowlists. General-purpose shell execution is permanently disabled.
* The **Privacy Gateway** enforces fail-closed local-only data minimization.
* The **Independent Verifier** checks postconditions. Model self-attestation is strictly rejected.
* The **Evidence Ledger** maintains an immutable audit trail.

---

## Repository Structure

```
sahaay/
├── apps/
│   ├── desktop/                # Electron + React + TypeScript Desktop UI
│   ├── browser-extension/      # Manifest V3 Chrome/Edge Browser Extension Bridge
│   └── windows-companion/      # C#/.NET Native Windows Controller & Native Messaging Host
├── core/                       # Python FastAPI Backend Orchestrator & Policy Engine
├── shared/
│   └── schemas/                # Authoritative JSON Schemas for v1 Contracts
├── tests/                      # Automated Test Suite (Unit, Privacy, Security, Contracts)
├── docs/                       # Technical Specifications, Threat Model, & Implementation Status
└── scripts/                    # Setup, Launch, and Validation PowerShell Scripts
```

---

## Quick Start

### Prerequisites
- Windows 10/11 (x64)
- Python 3.12+ (uv package manager recommended)
- Node.js v20+ / v22+
- .NET 8.0+ SDK (for compiling C# Native Companion)

### Setup & Launch
```powershell
# 1. Automated environment setup
.\scripts\setup.ps1

# 2. Run all quality checks & tests
.\scripts\run-tests.ps1

# 3. Start Backend Orchestrator (http://127.0.0.1:8000)
.\scripts\start-backend.ps1

# 4. Start Electron Desktop Application
.\scripts\start-desktop.ps1
```

---

## Documentation Index

- [Architecture & Design](docs/architecture.md)
- [Threat Model & Security](docs/threat-model.md)
- [Data Flow & Provenance](docs/data-flow.md)
- [Model Inventory & Strategy](docs/model-inventory.md)
- [Permissions & Privacy](docs/permissions-and-privacy.md)
- [API Contracts (v1)](docs/api-contracts.md)
- [Windows Setup Guide](docs/setup-windows.md)
- [Testing & Quality Guide](docs/testing.md)
- [Implementation Status](docs/implementation-status.md)

---

## License

Proprietary / Internal. All rights reserved.
