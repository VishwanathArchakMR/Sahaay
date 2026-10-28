# Sahaay Core API Contracts (v1)

Base URL: `http://127.0.0.1:8000/api/v1`  
Authentication Header: `X-Sahaay-Token: <LAUNCH_TOKEN>`

---

## 1. Health & Capabilities

### `GET /api/v1/health`
Returns system operational status and runtime diagnostics. Publicly accessible for health probes.
* **Response** (200 OK):
  ```json
  {
    "status": "healthy",
    "systemVersion": "0.1.0-foundation",
    "pythonVersion": "3.12.8",
    "localOnlyMode": true,
    "timestamp": "2026-10-27T18:40:00Z",
    "databaseReady": true
  }
  ```

### `GET /api/v1/capabilities`
Truthfully reports only what capabilities are actually available in the current environment.
* **Response** (200 OK):
  ```json
  {
    "systemVersion": "0.1.0-foundation",
    "desktopAutomationAvailable": false,
    "browserAutomationAvailable": false,
    "modelsAvailable": [],
    "activeCapabilities": [
      "session_management",
      "consent_grant_lifecycle",
      "task_state_machine",
      "action_gate_authorization",
      "privacy_gateway_fail_closed",
      "provenance_context_store",
      "source_authorization_and_revocation",
      "independent_verification_engine",
      "evidence_ledger"
    ]
  }
  ```

---

## 2. Sessions & Consent

### `POST /api/v1/sessions`
* **Request**:
  ```json
  {
    "localOnlyMode": true,
    "metadata": {}
  }
  ```
* **Response** (201 Created): Returns initialized `Session` object.

### `POST /api/v1/sessions/{session_id}/grants`
* **Request**:
  ```json
  {
    "scope": "read_file:C:\\docs",
    "purpose": "Document review",
    "targetDomainOrPath": "C:\\docs"
  }
  ```
* **Response** (201 Created): Returns `ConsentGrant` object.

---

## 3. Tasks & State Machine

### `POST /api/v1/tasks`
* **Request**:
  ```json
  {
    "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "goal": "Review quarterly report and summarize findings",
    "taskType": "combined_retrieval_and_action"
  }
  ```
* **Response** (201 Created): Returns `TaskContract` with status `CREATED`.

### State Lifecycle Routes
* `POST /api/v1/tasks/{task_id}/transition`: Transition status (`PLANNING`, `OBSERVING`, `PROPOSING`, `AUTHORIZING`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `FAILED`).
* `POST /api/v1/tasks/{task_id}/pause`: Transition status to `PAUSED`.
* `POST /api/v1/tasks/{task_id}/resume`: Resume paused task to `OBSERVING`.
* `POST /api/v1/tasks/{task_id}/cancel`: Immediate cancellation; permanently blocks future action dispatch.
* `POST /api/v1/tasks/{task_id}/handoff`: Transition status to `HANDOFF_REQUESTED`.

---

## 4. Actions & Verification

### `POST /api/v1/actions/propose`
Evaluates an action through the deterministic Action Gate.
* **Request**:
  ```json
  {
    "taskId": "...",
    "stepId": "...",
    "action": {
      "actionType": "read_file",
      "target": "C:\\data\\report.pdf",
      "parameters": {},
      "expectedPostcondition": "File text loaded",
      "estimatedRisk": "READ_ONLY"
    }
  }
  ```
* **Response** (200 OK): Returns `PolicyDecision` (`ALLOW`, `DENY`, `CLARIFY`, `HANDOFF`, `REOBSERVE`).

### `POST /api/v1/actions/verify`
Performs independent postcondition verification and writes to Evidence Ledger.
* **Request**:
  ```json
  {
    "taskId": "...",
    "stepId": "...",
    "action": { ... },
    "executionResult": {
      "isSuccess": true,
      "durationMs": 120.0
    },
    "observedPostconditionData": { "state": "File text loaded" },
    "isModelSelfAttestation": false
  }
  ```
* **Response** (200 OK): Returns `VerificationResult` (`VERIFIED`, `FAILED`, `UNVERIFIED`, `CONFLICT`).

---

## 5. Sources & Context Retrieval

### `POST /api/v1/sources`
Registers a permitted file, browser tab, or application window.
* **Request**:
  ```json
  {
    "sourceType": "local_file",
    "uri": "C:\\reports\\q3.csv",
    "title": "Q3 Financials"
  }
  ```

### `DELETE /api/v1/sources/{source_id}`
Revokes source permission. All subsequent retrieval requests for this source fail closed.

### `POST /api/v1/sources/facts`
Records an extracted or observed fact linked to a source.

### `POST /api/v1/sources/query`
Retrieves facts within authorized source scope.

---

## 6. Audit & Evidence

### `GET /api/v1/audit/evidence/task/{task_id}`
Returns all immutable `EvidenceReference` records for a task.

---

## 7. Windows Companion Controller

### `GET /api/v1/windows`
Enumerate open visible application windows via Win32 `EnumWindows` and UI Automation.
* **Response** (200 OK):
  ```json
  {
    "isConnected": true,
    "windows": [
      {
        "hwnd": 123456,
        "title": "Document - WordPad",
        "processName": "wordpad.exe",
        "bounds": { "x": 100, "y": 100, "width": 800, "height": 600 }
      }
    ],
    "count": 1
  }
  ```

### `GET /api/v1/windows/active`
Retrieve the current foreground window.

### `POST /api/v1/windows/inspect`
Inspect accessible UI Automation elements for a given HWND.
* **Request**:
  ```json
  { "hwnd": 123456 }
  ```

### `POST /api/v1/windows/observe`
Capture structured UI Automation tree and optional screenshot for an authorized window.

---

## 8. Browser Bridge & Active Tab Tracking

### `POST /api/v1/browser/observe`
Ingest real observation from authorized browser tab, register as source, record observation version, and register context facts.
* **Request**:
  ```json
  {
    "url": "https://example.com/docs",
    "title": "Example Docs",
    "scrollPosition": { "x": 0, "y": 150 },
    "documentDimensions": { "width": 1280, "height": 3400 },
    "visibleTextExcerpt": "Documentation content...",
    "accessibleElements": []
  }
  ```

### `GET /api/v1/browser/active-observation`
Retrieve currently tracked tab state, observation version, and whether tab navigation has rendered the observation stale (`isStale: true`).

### `POST /api/v1/browser/action/scroll`
Propose, authorize via Action Gate (evaluating staleness, task type, and boundaries), execute bounded scroll, and independently verify postcondition.
* **Request**:
  ```json
  {
    "sessionId": "...",
    "taskId": "...",
    "stepId": "...",
    "url": "https://example.com/docs",
    "requestedDeltaY": 300,
    "preScrollY": 150,
    "postScrollY": 450
  }
  ```
* **Response**: Returns authorization status, `actualDeltaY`, `verificationStatus` (`VERIFIED`/`CONFLICT`/`REOBSERVE`), and `evidenceId`.

---

## 9. Local Document Ingestion & Deterministic Retrieval

### `POST /api/v1/sources/ingest-file`
User-initiated safe ingestion of authorized local files (`.txt`, `.md`, `.pdf`). Performs path security validation, size enforcement (<10MB), paragraph and page chunking, and SHA-256 fingerprinting.
* **Request**:
  ```json
  {
    "filePath": "C:\\docs\\quarterly_report.pdf",
    "description": "User authorized financial summary"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "success": true,
    "sourceId": "src-doc-12345",
    "filePath": "C:\\docs\\quarterly_report.pdf",
    "fileName": "quarterly_report.pdf",
    "fileSizeBytes": 45020,
    "checksumSha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "totalChunks": 12,
    "pageCount": 4,
    "message": "Successfully ingested and indexed 12 text chunks."
  }
  ```

### `POST /api/v1/sources/search`
Perform deterministic keyword search over ingested facts with match location, rich source provenance, and confidence scoring (zero AI inference).
* **Request**:
  ```json
  {
    "query": "revenue growth",
    "sourceType": null
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "query": "revenue growth",
    "totalMatches": 2,
    "results": [
      {
        "factId": "fact-doc-001",
        "factType": "document_chunk",
        "sourceId": "src-doc-12345",
        "sourceType": "local_document",
        "sourceUri": "file:///C:/docs/quarterly_report.pdf",
        "sourceTitle": "quarterly_report.pdf",
        "observedAt": "2026-10-28T10:00:00Z",
        "matchedSnippet": "...showing strong revenue growth across all segments...",
        "confidenceScore": 1.0,
        "matchLocation": "Page 2",
        "isUntrustedContent": true
      }
    ],
    "isModelInference": false,
    "limitationNotice": "Showing deterministic keyword extracts only. Semantic synthesis requires Meta model integration (Milestone 04)."
  }
  ```

---

## 10. Combined Retrieval & Action Workflow

### `POST /api/v1/tasks/{task_id}/combined/verify-and-scroll`
Verifies that a required factual assertion is present in ingested source facts before authorizing and dispatching an active computer action. Fails safely with `HANDOFF_REQUESTED` if preconditions are not met or if data conflicts.
* **Request**:
  ```json
  {
    "requiredTextInSource": "Web APIs",
    "scrollDeltaY": 300,
    "url": "https://developer.mozilla.org/en-US/docs/Web/API"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "taskStatus": "COMPLETED",
    "preconditionMet": true,
    "verifiedExcerpt": "Web APIs are typically used with JavaScript...",
    "actionEvidenceId": "ev-scroll-9876",
    "actualDeltaY": 300,
    "message": "Precondition verified in source and action executed successfully."
  }
  ```

