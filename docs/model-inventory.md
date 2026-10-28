# Sahaay Model Inventory & Provider Architecture (Milestone 05)

## 1. Active Model Roles & Providers

In Milestone 05, Sahaay integrates **Baseten Muse Spark Open** as its actual structured planner, **Meta Muse Image** for visual storytelling and Task Passports, alongside the existing Meta Model suite and Local Llama 3.2 3B runtime.

| Model Designation | Basis / Provider | Active Role in Sahaay | Operational Status |
| :--- | :--- | :--- | :--- |
| **Muse Spark Open** | `meta-models/muse-spark-open` via **Baseten** (`https://inference.baseten.co/v1`) | Structured task planning, decomposed step dependencies, and Action Gate capability mapping | **INTEGRATED & TESTED** (Requires `BASETEN_API_KEY`; deterministic fallback when offline) |
| **Muse Image** | `muse-image-1.0` via **Meta Model API** (`https://api.meta.ai/v1/images/generations`) | Visual storytelling for Task Passports, step illustrations, and visual workflow routes | **INTEGRATED & TESTED** (Requires `MODEL_API_KEY`; obsidian vector SVG fallback when offline) |
| **Muse Spark** | `muse-spark-1.3` via Meta Model API | Indic semantic reasoning, multilingual intent decomposition (Kannada, Hindi, English) | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **Muse Wonder** | `muse-wonder-1.0` via Meta Model API | Computer-use action proposal parsing with strict Action Gate boundary enforcement | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **Muse Voice Transcribe** | `muse-voice-transcribe-1.0` via Meta Model API | Speech transcription with language biasing and mandatory editable confirmation dialog | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **SAM 3.1** | `sam-3-1` via Meta Model API | Visual grounding of UI elements and bounding box translation | **INTEGRATED & TESTED** (Mock/Live adaptive) |
| **Local Llama 3.2 3B** | Quantized GGUF via `llama-server.exe` loopback (`127.0.0.1:8080`) | Offline planning and fact extraction when Local-Only Mode is active | **INTEGRATED & TESTED** (Lifecycle manager probes weights & hardware) |

---

## 2. Independent Provider Credentials

The providers are architecturally isolated with separate environment variables and consent policies:

1. **Baseten Provider (`BASETEN_API_KEY`)**:
   - Outbound endpoint: `https://inference.baseten.co/v1/chat/completions`
   - Default model: `meta-models/muse-spark-open` (configurable via `BASETEN_MUSE_SPARK_MODEL`)
   - Schema enforcement: Local Pydantic validation of `StructuredTaskPlan` with 1-shot repair.
   - Fail-closed behavior: When unconfigured, truthfully reports `LOCAL_FALLBACK`.

2. **Meta Model API (`MODEL_API_KEY` or `META_LLAMA_API_KEY`)**:
   - Outbound endpoint: `https://api.meta.ai/v1/images/generations`
   - Default model: `muse-image-1.0` (configurable via `MUSE_IMAGE_MODEL`)
   - Prompt minimization: Abstract visual metaphors only; raw PII/credentials are scrubbed before transmission.
   - Fail-closed behavior: When unconfigured, generates obsidian/liquid vector SVG fallback inline.

---

## 3. Privacy Gateway Invariants
1. Every external request must pass through `PrivacyGateway.evaluate_outbound_request`.
2. Outbound data is classified; payloads containing detected credentials fail closed.
3. If `SAHAAY_PRIVACY_LOCAL_ONLY_MODE=true`, all external calls fail closed unconditionally.
4. Generated artwork does not change verification state: deterministic checks in SQLite evidence records remain authoritative.

