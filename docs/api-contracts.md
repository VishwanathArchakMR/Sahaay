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
