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
