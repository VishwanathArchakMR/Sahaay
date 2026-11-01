# SAHAAY — FRONTEND BUTTON AND INTERACTION AUDIT

## 1. Overview and Core Philosophy

In accordance with Section 11 of the Master Directive, the Sahaay user interface is consolidated around **three primary interaction controls**:

1. **TALK / VOICE**: Default primary interaction button. Activates the microphone and streams audio to Meta Voice (SeamlessStreaming / Whisper) for natural language reasoning.
2. **TYPE / SEND**: Direct alternative composer button for text-first input, dispatching to the identical backend task engine.
3. **APPROVE / TAKE OVER**: Contextual control displayed dynamically in the Task Inspector only when human authorization (Action Gate) or manual handoff is requested.

Every interactive element across the Desktop application (`apps/desktop/src/renderer/src/App.tsx`) and the Chromium Extension Sidepanel (`apps/browser-extension/src/sidepanel/sidepanel.ts`) has been audited and classified below into:
- **Verified Working (Real Backend Endpoint)**
- **Wired to Orchestrator (Unified Prompt Execution)**
- **Decorative Elements Demoted/Removed**

---

## 2. Desktop Application Interface Audit (`App.tsx`)

### 2.1 The 3 Primary Interaction Controls

| Control | Location | Bound Handler | Real Backend Endpoint | Verification Evidence |
|---|---|---|---|---|
| **TALK / VOICE** | Task Composer & Left Rail | `toggleRecording()` | `POST /api/v1/models/transcribe` | Real Web Audio API stream recorded in chunks, posted to FastAPI backend, transcribed via Meta Cloud or Indic language processor. |
| **TYPE / SEND** | Task Composer | `triggerPromptExecution(userPrompt)` | `POST /api/v1/workflows/execute-goal` | Formulates `ExecuteGoalRequest`, establishes session, triggers 6-stage lifecycle, and polls `/api/v1/tasks/{id}`. |
| **APPROVE / TAKE OVER** | Contextual Task Inspector | `handleApproveAction()` / `handleTakeOver()` | `POST /api/v1/sessions/{id}/grants` / `POST /api/v1/tasks/{id}/handoff` | Displays when `taskState === "HANDOFF"`. Issues explicit non-wildcard capability grants or relinquishes control. |

### 2.2 Navigation Rail Buttons

| Button | Label | Action / Behavior | Classification |
|---|---|---|---|
| `Home` | Home | Swaps main viewport to active task composer and cards grid. | Verified Working |
| `New Task` | New Task | Resets composer prompt and clears active inspector view. | Verified Working |
| `Computer` | Computer | Focuses on Windows desktop automation context filter. | Wired to Context Filter |
| `Browser` | Browser | Focuses on active Chromium tab context filter. | Wired to Context Filter |
| `Files` | Files | Focuses on local document ingestion context filter. | Wired to Context Filter |
| `Apps` | Apps | Focuses on installed Windows applications context filter. | Wired to Context Filter |
| `Voice` | Voice | Toggles microphone audio capture. | Verified Working |
| `History` | History | Renders live SQLite evidence history from backend `/api/v1/tasks`. | Verified Working |
| `Diagnostics` | Diagnostics | Opens live telemetry panel with real connection probes. | Verified Working |
| `Settings` | Settings | Opens system settings modal showing model routing & privacy tier. | Verified Working |

### 2.3 Task Suggestion Chips (Hero Section)

All chips are wired to populate the composer input with concrete actionable requests:

| Chip Text | Injected Goal | Handled Capability |
|---|---|---|
| `Find information` | `"Search recent invoices and summarize key facts"` | Document Ingestion / Retrieval |
| `Work with files` | `"Read local invoice statement and extract details"` | OCR & Local File Parsing |
| `Use browser` | `"Summarize active web browser tab to Notepad"` | Cross-Context Browser to Windows |
| `Open apps` | `"Open Notepad and write project summary"` | Windows UI Automation |
| `Automate tasks` | `"Transfer bill details from browser to desktop"` | Autonomous Cross-Surface Workflow |

### 2.4 Quick Action Cards (Bottom Grid)

| Action Button | Dispatched Payload | Real Backend Execution Path |
|---|---|---|
| `Summarize this page` | `"Summarize this page and save to Notepad"` | `POST /api/v1/workflows/cross-context-bill-notepad` |
| `Open Notepad` | `"Open Notepad and write summary of bills"` | `POST /api/v1/actions` -> `launch_application` |
| `Analyze a file` | `"Read local invoice statement and extract details"` | `POST /api/v1/workflows/execute-goal` |
| `Take a screenshot` | `"Take a screenshot and inspect active window"` | `POST /api/v1/models/multimodal-inspect` |
| `Search my files` | `"Search my files for utility bill"` | `POST /api/v1/workflows/execute-goal` |
| `Set a reminder` | `"Set a reminder to review project budget at 5 PM"` | `POST /api/v1/workflows/execute-goal` |

### 2.5 Diagnostics & Telemetry Panel Controls

| Button | Action | Real Endpoint |
|---|---|---|
| `Refresh Probes` | Re-checks backend health and model status | `GET /api/v1/health`, `GET /api/v1/models/status` |
| `Copy Diagnostics` | Exports full runtime status JSON to clipboard | Local state aggregation |
| `Export Report` | Downloads timestamped JSON file to disk | Browser blob download |
| `Execution Trace / Server Logs` | Toggles between execution timeline and live backend logs | `GET /api/v1/diagnostics/logs` |

---

## 3. Browser Extension Sidepanel Audit (`sidepanel.ts`)

| Element | Location | Bound Event | Backend Target | Status |
|---|---|---|---|---|
| `Summarize Page` | Context Card | `click` -> `handleSummarizeToNotepad()` | `POST /api/v1/workflows/cross-context-bill-notepad` | **Verified Working**: Extracts active DOM text, launches Notepad, sets text, and verifies via UI Automation. |
| `Sync Tab` | Header | `click` -> `captureTabContext()` | Extension Chrome Tabs API | **Verified Working**: Re-queries active tab URL and title. |
| `Send Prompt` | Composer | `click` / `Enter` -> `handleGeneralPrompt()` | `POST /api/v1/workflows/execute-goal` | **Verified Working**: Dispatches arbitrary browser/computer goals to backend orchestrator. |
| `Details / View Result` | Status Badge Card | `addEventListener("click")` | SQLite ledger proof modal | **Verified Working**: CSP-compliant modal display of cryptographic proof. |
| `Voice Input` | Composer | `click` -> `toggleVoice()` | MediaStream -> `/api/v1/models/transcribe` | **Verified Working**: Streams audio to backend transcription. |

---

## 4. Elimination of Decorative and Fake Elements

1. **Removed Non-Functional Alert Stubs**:
   - Replaced inline `onclick="alert(...)"` which previously violated CSP and offered no runtime value with dynamic DOM listeners that link directly to task ledger IDs.
2. **Eliminated Premature "Completed" Indicators**:
   - Tasks that fail execution or validation are now truthfully presented with a red alert banner displaying the specific error detail, preventing false positives.
3. **Harmonized Privacy Mode Indicator**:
   - The "Local Mode" / "Hosted Mode" header pill toggles the live session configuration via `POST /api/v1/sessions` rather than functioning as a cosmetic toggle.
