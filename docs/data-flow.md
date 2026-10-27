# Sahaay Data Flow & Provenance Architecture

## 1. End-to-End Data Flow Overview

```
User Voice / Typed Prompt
         │
         ▼
[Electron Desktop UI]
         │ (HTTP/WS with X-Sahaay-Token)
         ▼
[FastAPI Core Backend]
         │
         ├──► 1. Register / Validate Session & Consent
         │
         ├──► 2. OBSERVE (Fetch Scoped Context)
         │       ├── Local File Adapter (Hash & Content Extraction)
         │       ├── Browser Extension (Sanitized DOM Excerpt)
         │       └── Native Companion (Window Discovery & State)
         │
         ├──► 3. STORE CONTEXT FACTS & PROVENANCE
         │       └── Context Store (FactType: source-extracted, observed, inferred)
         │
         ├──► 4. PROPOSE ACTION (Plan Step)
         │       └── Action Contract (Type, Target, Parameters, ExpectedPostcondition)
         │
         ├──► 5. AUTHORIZE (Action Gate Evaluation)
         │       ├── Operation Allowlist Check
         │       ├── Shell Command Detection (Blocked)
         │       └── Session Consent Scope Check
         │           ├── ALLOW ──► Proceed to Driver
         │           ├── CLARIFY ──► Prompt User in UI
         │           └── DENY ──► Abort Step
         │
         ├──► 6. EXECUTE (Driver Execution)
         │       └── Native Driver / Browser Extension Executes Bounded Action
         │
         ├──► 7. VERIFY (Independent State Verification)
         │       ├── Invariant: Model self-attestation is REJECTED
         │       └── Objective state check (DOM, File Checksum, or Window Status)
         │
         └──► 8. RECORD EVIDENCE
                 └── Evidence Ledger (Immutable link: Task -> Step -> Action -> Result -> Verification)
```

---

## 2. Fact Classification & Provenance Tracking
Sahaay distinguishes seven explicit fact types in the Context Store:
1. `user-provided`: Direct instructions, goals, or constraints provided by the logged-in user.
2. `source-extracted`: Raw facts parsed from authorized local files, documents, or data tables.
3. `observed`: Dynamic state observed directly from active browser tabs or Windows UI elements.
4. `normalized`: Standardized representations (e.g., converted currencies, normalized dates).
5. `inferred`: Deductions or summaries synthesized by reasoning components.
6. `uncertain`: Statements with incomplete evidence or lower confidence scores (< 0.8).
7. `conflicting`: Information where two permitted sources contradict each other.

### Derivation Trees
Every derived or inferred fact stores an array of `derivationIds` referencing parent facts.
Calling `store.get_derivation_chain(fact_id)` walks the graph back to initial `source-extracted` or `observed` facts, enabling the UI to show the user exactly why and how an answer was derived.

---

## 3. Evidence Ledger Integrity
Every completed step records an `EvidenceReference` linking:
- `taskId`
- `stepId`
- `actionId`
- `observationId`
- `verificationResultId` (`VERIFIED`, `FAILED`, `UNVERIFIED`, `CONFLICT`, or `NOT_ATTEMPTED`)
- `narrative` summary
The Evidence Ledger prevents retrospective alteration of past action records.

---

## 4. Stage 02 Browser Action & Verification Flow
For the bounded browser scroll action:
1. **Observe Precondition**: Ingests pre-action scroll coordinates $(X_0, Y_0)$ and document dimensions from the authorized tab.
2. **Action Proposal**: Creates `ActionContract` with type `SCROLL_BROWSER_TAB` targeting tab URL with parameter `deltaY`.
3. **Action Gate Authorization**: Confirms session consent, active task status, and verified target scope.
4. **Driver Execution**: Extension content script executes `window.scrollBy({ top: deltaY, behavior: 'instant' })`.
5. **Postcondition Observation**: Captures post-action scroll coordinates $(X_1, Y_1)$.
6. **Independent Verification**: Calculates actual $\Delta Y = Y_1 - Y_0$.
   - If $\Delta Y \neq 0$ and sign matches requested direction: `VERIFIED`.
   - If $\Delta Y == 0$: flags `CONFLICT` (e.g. at document boundary or unscrollable viewport).
   - Rejects any self-attesting completion message.
7. **Audit Record**: Records immutable entry to `EvidenceLedger` linking task, step, delta, and verification state.
