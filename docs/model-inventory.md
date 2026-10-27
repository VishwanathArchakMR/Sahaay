# Sahaay Model Inventory & Provider Plan

## 1. Stage 01 Status: Planned / Deferred
In accordance with Build 01 specifications, **no live model integrations are enabled, no external inference calls are permitted, no provider API keys are requested, and no large model weights are downloaded.**
All model provider clients (`MetaClient`, `SparkOpenClient`, `LocalLlamaClient`) are implemented as clean, mock-free fail-closed interfaces raising `ModelProviderNotConfiguredError`.

---

## 2. Planned Model Roles & Capabilities

| Model Designation | Architecture / Basis | Planned Role in Sahaay | Status in Stage 01 |
| :--- | :--- | :--- | :--- |
| **Muse Voice Transcribe** | Voice Recognition & ASR | Streaming transcription of user voice commands in the desktop app | **PLANNED** (Interface defined; no live model) |
| **Muse Spark** | Fast Reasoning & Planning | High-speed multi-step task planning, heuristic decomposition, and prompt formatting | **PLANNED** (Interface defined; no live model) |
| **Muse Wonder** | Deep Multimodal Reasoning | Complex cross-document analysis, browser tab reasoning, and fact synthesis | **PLANNED** (Interface defined; no live model) |
| **SAM 3.1 / Muse Image** | Multimodal Grounding & Vision | Visual segmentation and bounding-box coordinate prediction for desktop UI controls | **PLANNED** (Interface defined; no live model) |
| **Muse Spark Open** | Open Weight Planning | Local fallback planning and offline task formulation | **PLANNED** (Interface defined; no live model) |
| **Meta Llama (3.3 / 3.2)** | Multimodal Foundation | Core question answering and structured fact extraction through Privacy Gateway | **PLANNED** (Interface defined; no live model) |
| **Local Llama (GGUF / ONNX)** | Local Quantized Inference | Fully offline inference when Local-Only Mode is enforced | **PLANNED** (Interface defined; no weights downloaded) |

---

## 3. Privacy Gateway Enforcement
When models are connected in future stages:
1. Every external request must pass through `PrivacyGateway.evaluate_outbound_request`.
2. Outbound data must be classified. Payloads containing detected credentials fail closed.
3. Consent grants must be checked for purpose and target domain.
4. If `SAHAAY_PRIVACY_LOCAL_ONLY_MODE=true`, all external model calls fail closed immediately.
