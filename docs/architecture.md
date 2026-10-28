# Sahaay Architecture & System Design

## 1. Product Definition
Sahaay is an installed Windows desktop AI agent engineered to assist users with two equal core capabilities across their real computer:
1. **Information Retrieval & Context Understanding**: Seamlessly find information, extract structured context from permitted local files, browser tabs, and desktop applications, distinguish facts from inferences, and communicate uncertainty with source-linked provenance.
2. **Computer and Browser Task Execution**: Execute bounded actions across real applications, real browser sessions, and the local file system with independent verification.

Sahaay operates through **one unified system**: one conversation/task interface, one context/provenance model, one orchestrator, one deterministic permission system, one Action Gate, and one immutable evidence ledger.

---

## 2. Frozen Architecture Overview

```
 +-----------------------------------------------------------------------+
 |                     Sahaay Desktop Interface (Electron)               |
 |              React 18 + TypeScript + Secure Preload/IPC               |
 +-----------------------------------+-----------------------------------+
                                     | HTTP/WebSocket (127.0.0.1)
                                     | Authenticated with X-Sahaay-Token
                                     v
 +-----------------------------------------------------------------------+
 |                 Sahaay Core Backend (FastAPI Monolith)                |
 |                                                                       |
 |   +---------------------------------------------------------------+   |
 |   | Task Orchestrator & State Machine (OBSERVE -> RECORD)         |   |
 |   +---------------------------------------------------------------+   |
 |   | Action Gate (Deterministic Operation Allowlist & Risk Rating) |   |
 |   +---------------------------------------------------------------+   |
 |   | Privacy Gateway (Fail-Closed, Data Classification, Local-Only)|   |
 |   +---------------------------------------------------------------+   |
 |   | Context Store & Provenance Ledger (Fact Types & Lineage)      |   |
 |   +---------------------------------------------------------------+   |
 |   | Independent Verification Engine & Evidence Ledger             |   |
 |   +---------------------------------------------------------------+   |
 |   | SQLite Persistence (Sessions, Grants, Tasks, Facts, Evidence) |   |
 +------------------+--------------------------------+-------------------+
                    |                                |
                    v                                v
+-----------------------------------+  +---------------------------------+
| Windows Native Companion (C#/.NET)|  | Browser Integration Bridge      |
| - Sahaay.Controller (Daemon)      |  | - Manifest V3 Extension         |
| - Sahaay.NativeHost (Stdio Bridge)|  | - Content Scripts & Popups      |
| - Windows UI Automation           |  | - Playwright (Owned Tests)      |
| - Controlled Screenshot Capture   |  | - Strict Origin & Size Limits   |
| - Strictly Allowlisted Ops        |  |                                 |
+-----------------------------------+  +---------------------------------+
```

---

## 3. Core Execution Sequence
All task executions follow a deterministic, audited state sequence:

$$\text{OBSERVE} \longrightarrow \text{PROPOSE} \longrightarrow \text{AUTHORIZE} \longrightarrow \text{EXECUTE} \longrightarrow \text{VERIFY} \longrightarrow \text{RECORD}$$

1. **OBSERVE**: Capture state from authorized browser tabs, desktop windows, or permitted files.
2. **PROPOSE**: Planning models or heuristics propose bounded actions adhering to `ActionContract`.
3. **AUTHORIZE**: The deterministic **Action Gate** evaluates proposed actions against active session consent grants and the strict operation allowlist. Unpermitted actions, shell commands, and out-of-scope targets are denied immediately.
4. **EXECUTE**: Authorized native controller or browser extension drivers perform the physical action.
5. **VERIFY**: The **Independent Verifier** performs an objective postcondition inspection (e.g., DOM property check, hash check, window title verification).
   * **Critical Invariant**: Model self-attestation is NEVER sufficient proof of completion.
6. **RECORD**: The **Evidence Ledger** creates an immutable record linking task, step, observation, action, policy decision, execution result, and independent verification outcome.

---

## 4. Privacy Gateway Architecture
Every external inference request must pass through the internal **Privacy Gateway**:
- **Local-Only Mode**: When enabled (`SAHAAY_PRIVACY_LOCAL_ONLY_MODE=true`), all outbound inference requests fail closed.
- **Data Classification**: Classifies payloads into `PUBLIC`, `INTERNAL`, `SENSITIVE_PII`, `CREDENTIAL`, or `HIGHLY_RESTRICTED`. Credentials and unredacted PII are blocked from external transmission.
- **Consent Decoupling**: Policy authorization and consent grants are decoupled from model prompts.
- **Stage 01 Baseline**: No external provider endpoints are enabled in Stage 01.

---

## 5. Storage Architecture
- **Persistent Relational DB**: SQLite managed asynchronously via SQLAlchemy/aiosqlite (`data/storage/sahaay.db`).
- **Temporary Media Storage**: Managed, separate directory (`data/temp_media/`) for transient captures and screenshots, protected from public exposure.

---

## 6. Windows Companion & Browser Bridge Architecture (.NET 10 LTS)
- **Sahaay.Controller**: Dedicated Windows daemon compiled on .NET 10 LTS (`net10.0-windows`). Uses Win32 `EnumWindows` and `System.Windows.Automation` to discover visible application windows and inspect accessible element hierarchies without polling loops or arbitrary shell execution. Exposes an authenticated local named pipe server at `\\.\pipe\SahaayControllerPipe` strictly scoped to the interactive user session.
- **Sahaay.NativeHost**: Native messaging bridge conforming to Google Chrome and Microsoft Edge native messaging protocol (4-byte length-prefixed stdio framing). Validates calling extension origin against explicit allowlists, enforces 1MB payload limits, and forwards approved typed commands to the controller named pipe.
- **Browser Extension (Manifest V3)**: Operates on real open Chrome and Edge tabs. Content scripts extract bounded visible page text, discover accessible interactive elements, and execute bounded actions (e.g. `scroll_tab`) via `window.scrollBy`.
- **Tab Staleness Tracking**: Tracks active observation versions and detects URL navigation. If the user navigates away from an observed page, subsequent action proposals return `PolicyDecisionEnum.REOBSERVE` to prevent blind or misdirected interactions.
- **Deterministic Information Retrieval**: Local keyword search engine (`POST /api/v1/sources/search`) operating over ingested browser and file facts in the Context Store, extracting relevant snippets and preserving full source URI provenance, match location, and confidence scores without AI models.

---

## 7. Local Document Ingestion Engine
- **Supported Formats**: User-selected `.txt`, `.md` (Markdown), and `.pdf` (via `pypdf` extraction).
- **Security Boundary**: Files must be explicitly designated by the user. Root directory scans, sensitive system paths (`system32`, `.env`, `id_rsa`), and files exceeding 10MB are strictly blocked.
- **Chunking & Provenance**: Text is chunked into logical units (paragraphs for text/markdown, pages for PDF) with line or page location metadata, recorded under a unique SHA-256 content checksum.
- **Data Lifecycle**: Extracted text is stored in the local SQLite Context Store under the task's permission boundary. Document contents are never transmitted externally.

---

## 8. Unified Task & Conversation Workflow Engine
Sahaay supports three deterministic operational workflows through one single orchestrator and Action Gate:
1. **Retrieval-Only Workflow**: Answers factual queries across ingested browser tabs and local files. The Action Gate strictly denies all physical actions (`PolicyDecisionEnum.DENY`).
2. **Action-Only Workflow**: Dispatches bounded, reversible operations (e.g. bounded scroll) through the verified invariant `OBSERVE -> PROPOSE -> AUTHORIZE -> EXECUTE -> VERIFY -> RECORD`.
3. **Combined Workflow**: Verifies prerequisite factual assertions in source observations before dispatching dependent physical actions (`POST /api/v1/tasks/{id}/combined/verify-and-scroll`). If matching is ambiguous or facts conflict, the system transitions safely to `HANDOFF_REQUESTED`.

---

## 9. Unified Desktop Interface (Electron + React)
- **Unified Conversation & Task Stream**: Chronological feed displaying user requests, ingested source metadata, deterministic retrieval snippets, Action Gate policy decisions, and verified execution cards.
- **Active Authorized Scope Drawer**: Live display of authorized browser tabs (with stale badges), active local documents (with revocation controls), and foreground Windows applications.
- **Omni-Input Bar**: Single input area with mode switches (`Retrieval-Only`, `Action-Only`, `Combined Workflow`), document attachment triggers, and scaffolded voice input.
- **Truthful Status Presentation**: Clear disclaimer cards stating that semantic synthesis requires Meta model integration (Milestone 04) and showing deterministic keyword extractions only.

