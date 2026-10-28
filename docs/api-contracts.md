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

---

## 11. Meta & Local Models Diagnostics

### `GET /api/v1/models/status`
Reports truthful readiness and configuration for all integrated model providers without exposing secrets.
* **Response** (200 OK):
  ```json
  {
    "metaApi": {
      "configured": false,
      "baseUrl": "https://api.meta.ai/v1",
      "status": "NOT_CONFIGURED"
    },
    "museSpark": { "modelId": "muse-spark-1.3", "status": "NOT_CONFIGURED" },
    "museWonder": { "modelId": "muse-wonder-1.0", "status": "NOT_CONFIGURED" },
    "museVoice": { "modelId": "muse-voice-transcribe-1.0", "status": "NOT_CONFIGURED" },
    "sam": { "modelId": "sam-3-1", "status": "NOT_CONFIGURED" },
    "localLlama": {
      "runtime": "llama.cpp",
      "modelPath": "",
      "status": "MODEL_FILE_MISSING",
      "host": "127.0.0.1",
      "port": 8080
    }
  }
  ```

### `POST /api/v1/models/test-connectivity`
Tests connection to Meta API if configured, subject to Privacy Gateway fail-closed check.
* **Response** (200 OK):
  ```json
  {
    "metaApi": false,
    "status": "NOT_CONFIGURED",
    "message": "Meta API key is not configured in settings or environment."
  }
  ```

### `POST /api/v1/models/plan`
Generates a structured task plan and action proposals via Muse Spark or local fallback.
* **Request**:
  ```json
  {
    "query": "Transfer electric bill amount to desktop accounting app",
    "context": "Bill total: INR 2,450.00",
    "sessionId": "default"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "goal": "Transfer electric bill amount to desktop accounting app",
    "detectedLanguage": "en",
    "mode": "combined_retrieval_and_action",
    "extractedFacts": { "amount": "2,450.00" },
    "proposedOperations": [
      {
        "actionType": "set_control_text",
        "target": "Accounting Notepad",
        "params": { "text": "2,450.00" }
      }
    ],
    "modelProvider": "local_fallback"
  }
  ```

### `POST /api/v1/models/transcribe`
Transcribes audio input using Muse Voice Transcribe pipeline with Indic biasing, returning editable transcript.
* **Request**:
  ```json
  {
    "audioBase64": "UklGRi...",
    "languageHint": "kn"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "transcript": "ವಿದ್ಯುತ್ ಬಿಲ್ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ",
    "detectedLanguage": "kn",
    "requiresUserConfirmation": true,
    "model": "muse-voice-transcribe-1.0"
  }
  ```

---

## 12. Cross-Surface Workflows

### `POST /api/v1/workflows/browser-to-desktop`
Executes end-to-end Browser → Desktop workflow: reads synthetic utility bill from authorized browser tab, grounds fields in provenance, asks authorization, populates desktop target via controller `set_control_text`, reads back, and independently verifies.
* **Request**:
  ```json
  {
    "tabUrl": "http://127.0.0.1:8000/fixtures/utility_bill.html",
    "desktopTargetWindow": "Notepad",
    "desktopTargetControl": "Editor"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "success": true,
    "taskId": "task-b2d-123",
    "lifecycle": ["OBSERVE", "PROPOSE", "AUTHORIZE", "EXECUTE", "VERIFY", "RECORD"],
    "extractedFields": {
      "consumer_name": "Aarav Sharma",
      "account_number": "BLR-UTIL-98421",
      "amount_due": "INR 2,450.00",
      "due_date": "November 15, 2026"
    },
    "targetApplication": "Notepad",
    "verifiedContent": "Account: BLR-UTIL-98421 | Consumer: Aarav Sharma | Due: INR 2,450.00 (Due Date: November 15, 2026)",
    "verificationStatus": "VERIFIED",
    "evidenceId": "ev-b2d-456"
  }
  ```

### `POST /api/v1/workflows/desktop-to-browser`
Executes end-to-end Desktop → Browser workflow: reads local synthetic invoice document, maps fields, authorizes, fills web form via extension `fill_form_fields`, reads back DOM via `get_field_values`, and independently verifies. Form submission is blocked.
* **Request**:
  ```json
  {
    "invoiceFilePath": "data/fixtures/invoice_data.json",
    "formUrl": "http://127.0.0.1:8000/fixtures/bill_pay_form.html"
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "success": true,
    "taskId": "task-d2b-789",
    "lifecycle": ["OBSERVE", "PROPOSE", "AUTHORIZE", "EXECUTE", "VERIFY", "RECORD"],
    "sourceDocument": "invoice_data.json",
    "populatedFields": {
      "customerName": "Aarav Sharma",
      "accountNumber": "BLR-UTIL-98421",
      "billingPeriod": "October 2026",
      "amountDue": "2450.00",
      "dueDate": "2026-11-15"
    },
    "verifiedValues": {
      "customerName": "Aarav Sharma",
      "accountNumber": "BLR-UTIL-98421",
      "amountDue": "2450.00"
    },
    "verificationStatus": "VERIFIED",
    "evidenceId": "ev-d2b-101",
    "formAutoSubmitBlocked": true
  }
  ```

---

## 13. Task Passport & Visual Storytelling (Milestone 05)

### `GET /api/v1/tasks/{task_id}/passport`
Retrieves the complete Task Passport and visual Step Story for a specified task, including ordinary language titles, route badges, illustration references, and independent verification proof.
* **Response** (200 OK):
  ```json
  {
    "taskId": "task-b2d-123",
    "workflowMode": "browser-to-desktop",
    "direction": "browser-to-desktop",
    "status": "VERIFIED",
    "sourceUrl": "http://127.0.0.1:8000/fixtures/utility_bill.html",
    "targetWindow": "Notepad",
    "summary": "Transfer BESCOM electricity bill into target Desktop application",
    "visualStorytellingEnabled": true,
    "milestones": [
      {
        "stepId": "step-1",
        "stepIndex": 1,
        "title": "Browser Observation",
        "operation": "OBSERVE_BROWSER_TAB",
        "source": "BESCOM Utility Portal (synthetic)",
        "destination": "Sahaay Agent Context",
        "direction": "browser-to-desktop",
        "status": "COMPLETED",
        "description": "Observed and ingested synthetic utility bill statement from authorized browser tab.",
        "evidenceId": "ev-obs-001",
        "isVerified": false,
        "imageUrl": null,
        "svgFallback": "<svg viewBox=\"0 0 400 240\" ...></svg>",
        "isIllustrationAiGenerated": false,
        "parameters": { "tabUrl": "http://127.0.0.1:8000/fixtures/utility_bill.html" }
      }
    ],
    "provenanceSha256": "4a58b29d98a2872bc8819446d32fe5a6d59c6c4c51475c74eb7596ff506cf2c7",
    "verifiedTimestamp": "2026-10-28T18:30:00Z"
  }
  ```

### `POST /api/v1/tasks/{task_id}/steps/{step_id}/illustrate`
User-controlled "Explain this step" action to generate or re-render an illustration for an individual milestone using Meta Muse Image (or obsidian vector graphics if offline).
* **Response** (200 OK): Returns the updated `MilestoneCard` with newly generated or refreshed illustration metadata.

### `DELETE /api/v1/tasks/{task_id}/artifacts`
Privacy and retention endpoint allowing users to delete all visual artifacts generated for a given task.
* **Response** (200 OK):
  ```json
  {
    "taskId": "task-b2d-123",
    "deletedCount": 2,
    "message": "Deleted 2 visual artifacts for task task-b2d-123."
  }
  ```

---

## 14. Baseten Muse Spark Open Planning (Milestone 05)

### `POST /api/v1/models/baseten/plan`
Direct diagnostic endpoint for structured plan generation via Muse Spark Open hosted on Baseten (`https://inference.baseten.co/v1`). Employs local Pydantic validation, 1-shot repair, and strict capability checks.
* **Request**:
  ```json
  {
    "userGoal": "Read electricity bill from browser tab and paste to notepad",
    "workflowMode": "browser-to-desktop",
    "permittedCapabilities": ["GET_TAB_CONTENT", "SET_CONTROL_TEXT", "GET_CONTROL_TEXT"]
  }
  ```
* **Response** (200 OK):
  ```json
  {
    "planId": "plan-baseten-456",
    "taskGoal": "Read electricity bill from browser tab and paste to notepad",
    "provider": "baseten",
    "modelId": "meta-models/muse-spark-open",
    "steps": [
      {
        "stepId": "s1",
        "order": 1,
        "purpose": "Read authorized utility bill tab",
        "actionType": "get_tab_content",
        "targetScope": "http://127.0.0.1:8000/fixtures/utility_bill.html",
        "requiresHumanApproval": false,
        "verificationCriteria": "bill facts parsed with SHA-256 fingerprint"
      }
    ],
    "safetyBoundaries": [
      "No auto-submission of payments",
      "Reject unauthorized shell executions"
    ]
  }
  ```



