# Sahaay Model Inventory & Provider Architecture (Milestone 06)

## 1. Active Model Roles & Providers

In Milestone 06, Sahaay uses the **Meta Model API** (`https://api.meta.ai/v1`) as its primary hosted AI provider. Baseten has been completely removed. Meta Muse Spark 1.3 is the primary hosted task planner, Meta Muse Image powers Task Passport illustrations, Meta Muse Voice Transcribe provides speech-to-text, and Meta Muse Wonder provides screenshot-based computer-use proposals, complemented by optional Local Llama 3.2 3B.

| Model Designation | Basis / Provider | Active Role in Sahaay | Operational Status |
| :--- | :--- | :--- | :--- |
| **Muse Spark 1.3** | `muse-spark-1.3` via **Meta Model API** (`https://api.meta.ai/v1`) | Primary hosted task reasoning and structured planning, validated against central Capability Registry | **INTEGRATED & TESTED** (Requires `MODEL_API_KEY`; deterministic local fallback when offline) |
| **Muse Image** | `muse-image-1.0` via **Meta Model API** (`https://api.meta.ai/v1/images/generations`) | Visual storytelling for Task Passports, step illustrations, and visual workflow routes | **INTEGRATED & TESTED** (Requires `MODEL_API_KEY`; obsidian vector SVG fallback when offline) |
| **Muse Wonder** | `muse-wonder-1.0` via Meta Model API | Computer-use action proposal parsing with strict Action Gate boundary enforcement | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **Muse Voice Transcribe** | `muse-voice-transcribe-1.0` via Meta Model API | Speech transcription with language biasing and mandatory editable confirmation dialog | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **SAM 3.1** | `sam-3.1` via Meta Model API | Visual grounding of UI elements and bounding box translation | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **Local Llama 3.2 3B** | Quantized GGUF via `llama-server.exe` loopback (`127.0.0.1:8080`) | Offline planning and fact extraction when Local-Only Mode is active | **INTEGRATED & TESTED** (Lifecycle manager probes weights & hardware) |

---

## 2. Central Meta Model API Provider Configuration

A single authoritative credential configuration is used across the Meta hosted model suite:

1. **Meta Model API (`MODEL_API_KEY`)**:
   - Base URL: `https://api.meta.ai/v1` (configurable via `META_API_BASE_URL`)
   - Header: `Authorization: Bearer $MODEL_API_KEY`
   - Primary Models:
     - `muse-spark-1.3` (Task reasoning & planning)
     - `muse-image-1.0` (Milestone storytelling & Task Passport)
     - `muse-voice-transcribe-1.0` (Speech-to-text with Kannada/Hindi/English biasing)
     - `muse-wonder-1.0` (Computer-use visual action proposal)
     - `sam-3.1` (Element visual segmentation)
   - Schema enforcement: Local Pydantic validation of `StructuredTaskPlan` against the central Capability Registry.
   - Security & Fail-closed: Never hardcodes credentials. When unconfigured or offline, truthfully reports `NOT_CONFIGURED` or `LOCAL_FALLBACK`. Abstract prompts scrub PII/credentials before transmission.

---

## 3. Privacy Gateway Invariants
1. Every external request must pass through `PrivacyGateway.evaluate_outbound_request`.
2. Outbound data is classified; payloads containing detected credentials fail closed.
3. If `SAHAAY_PRIVACY_LOCAL_ONLY_MODE=true`, all external calls fail closed unconditionally.
4. Generated artwork does not change verification state: deterministic checks in SQLite evidence records remain authoritative.

