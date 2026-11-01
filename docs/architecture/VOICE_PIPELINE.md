# SAHAAY — VOICE PIPELINE ARCHITECTURE

## 1. High-Level Voice Design

Sahaay is designed as a **voice-first Windows companion**. Rather than requiring users to type complex multi-step instructions, the voice pipeline captures spoken intent in English, Kannada, Hindi, and Indian English code-switched phrases, streaming the audio directly to Meta's Cloud speech recognition models (SeamlessStreaming / Whisper).

```mermaid
flowchart LR
    Mic[Laptop Microphone] --> WebAudio[Web Audio API / MediaRecorder]
    WebAudio --> FormUpload[Multipart Form Upload /models/transcribe]
    FormUpload --> Privacy[Privacy Gateway Scan]
    Privacy --> MetaClient[MetaClient HTTPS POST]
    MetaClient --> MetaASR[Meta SeamlessStreaming / Whisper]
    MetaASR --> IndicGrounding[Indic Language Normalizer]
    IndicGrounding --> Orchestrator[Task Orchestrator / DAG Planner]
```

---

## 2. Capture and Streaming Protocol

### 2.1 Audio Ingestion in Frontend
- **Interface**: Implemented in both the Electron desktop UI (`App.tsx`) and the extension sidepanel (`sidepanel.ts`).
- **Web Audio Configuration**:
  ```ts
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : "audio/wav";
  const recorder = new MediaRecorder(stream, { mimeType });
  recorder.start(250); // 250ms chunk collection
  ```
- **Visual Waveform**: Liquid aurora dynamic waveform provides instant feedback while recording, displaying elapsed recording time.

### 2.2 Wire Transport Protocol
- Audio chunks are compiled into an in-memory `Blob` upon user completion or pause.
- Transported via HTTP POST to:
  `POST http://127.0.0.1:8000/api/v1/models/transcribe`
- Headers:
  `X-Sahaay-Token: <bearer-pairing-token>`
- Body: `multipart/form-data`:
  - `file`: `recording.webm` (binary audio stream)
  - `languageHints`: `"kn,hi,en"` (Indic priority hints)
  - `sessionId`: `<active-session-uuid>`

---

## 3. Backend Processing & Meta Model Ingestion

### 3.1 Endpoint Routing (`api/v1/models.py`)
1. **Privacy Pre-Check**:
   `PrivacyGateway.evaluate_outbound_request()` validates that the session allows hosted models and that the audio metadata does not violate safety boundaries.
2. **Audio Decoding**:
   The audio bytes are verified for header integrity (`WEBM` or `RIFF/WAV`).
3. **Meta Voice Model Ingestion**:
   `MuseVoiceAdapter.transcribe_audio_stream()` routes the payload to Meta's Cloud audio transcription endpoint:
   ```python
   api_res = await self.client.post_endpoint(
       "audio/transcriptions",
       files={"file": (filename, audio_stream, content_type)},
       data={
           "model": "muse-voice-1.0",
           "language_hints": "kn,hi,en",
           "response_format": "json",
       },
   )
   ```

### 3.2 Indic Code-Switching Normalization
- The returned transcript is parsed by `muse_spark.py` to identify Indic phrases:
  - **Kannada Keywords**: `nodri`, `nodi`, `haaki`, `maadi`, `hege`, `idu`, `ella`, `bariri`, `eshtu`, `billu`.
  - **Hindi Keywords**: `dekho`, `nikalo`, `daalo`, `karo`, `batao`, `yeh`, `likho`, `kitna`, `bijli`.
- The semantic intent is mapped to atomic computer-use operations while preserving all domain entity names (e.g., BESCOM, consumer ID, due date).

---

## 4. Elimination of Synthetic Fallbacks (Defect 10.1 Resolution)

In previous iterations, when Meta Cloud API keys were omitted, the voice adapter returned a synthetic fallback string:
```text
"Find the account number in this open bill, then write the consumer ID and due date into a new file called bill_summary.txt on my desktop"
```
**This synthetic fallback has been completely removed**:
- In `core/src/sahaay_core/models/meta/muse_voice.py`, `allow_offline_fixture` is set strictly to `False`.
- If the Meta API client is unconfigured, the endpoint truthfully returns:
  ```json
  {
    "status": "NOT_CONFIGURED",
    "transcript": "",
    "error": "Meta Cloud API credentials are not configured for voice transcription. Please enter your API key in Settings or use the text composer."
  }
  ```
- If Local-Only Mode is active:
  ```json
  {
    "status": "BLOCKED_BY_PRIVACY",
    "transcript": "",
    "error": "Hosted voice transcription is blocked because Local-Only Mode is active. Switch to hosted mode in Settings or type your request."
  }
  ```
This ensures complete auditability and truth in model attestation.

