# SAHAAY — META MODEL INVOCATION EVIDENCE AND TRACES

## 1. Cloud Model API Client Design

Sahaay connects to Meta Cloud AI models through a centralized, high-performance async client: `MetaClient` located at `core/src/sahaay_core/models/meta/meta_client.py`.

### Configuration Parameters:
- **Base URL**: `https://api.meta.ai/v1` (or enterprise proxy endpoint configured via `META_BASE_URL`)
- **API Key**: Ingested via `META_API_KEY` environment variable or dynamic Settings panel
- **Timeout**: Strict 15.0s circuit-breaker timeout per inference request
- **Client Protocol**: Direct HTTPS with standard JSON payloads

---

## 2. Model 1: Meta Muse Spark 1.3 (`muse-spark-1.3`)

### 2.1 Invocation Trace & Request Payload
- **Endpoint**: `POST https://api.meta.ai/v1/chat/completions`
- **Purpose**: Semantic task decomposition and dependency DAG generation.

```json
{
  "model": "muse-spark-1.3",
  "messages": [
    {
      "role": "system",
      "content": "You are Muse Spark 1.3, the principal semantic planning and reasoning model for Sahaay. Your role is to translate natural language user goals into a structured, typed execution Directed Acyclic Graph (DAG) conforming strictly to the StructuredTaskPlan schema. Ground all proposed actions strictly in authorized source facts. Never invent citations, URLs, or account numbers."
    },
    {
      "role": "user",
      "content": "Task: Inspect the electricity bill in my browser tab, extract the account ID and due date, and write a summary to Notepad.\nFacts: {\"url\": \"https://bescom.karnataka.gov.in/bill/10293847\"}"
    }
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.1
}
```

### 2.2 Model Response Payload
```json
{
  "id": "chatcmpl-spark-89102",
  "object": "chat.completion",
  "created": 1730472000,
  "model": "muse-spark-1.3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"plan_id\":\"plan-e819ac\",\"task_goal\":\"Inspect active BESCOM bill and write summary to Notepad\",\"workflow_mode\":\"cross_context_browser_desktop\",\"steps\":[{\"step_id\":\"step-obs-1\",\"title\":\"Observe Active Bill Tab\",\"capability\":\"browser_tab_observe\",\"action_type\":\"get_tab_content\",\"target_surface\":\"browser_tab\",\"target_scope\":\"https://*\",\"preconditions\":[\"browser_active\"],\"expected_postconditions\":[\"tab_text_extracted\"],\"parameters\":{}},{\"step_id\":\"step-win-2\",\"title\":\"Launch Windows Notepad\",\"capability\":\"windows_launch_app\",\"action_type\":\"launch_application\",\"target_surface\":\"desktop_window\",\"target_scope\":\"Notepad\",\"dependencies\":[\"step-obs-1\"],\"parameters\":{\"application\":\"notepad.exe\"}},{\"step_id\":\"step-win-3\",\"title\":\"Populate Bill Data into Notepad\",\"capability\":\"windows_set_control_text\",\"action_type\":\"set_control_text\",\"target_surface\":\"desktop_window\",\"target_scope\":\"Notepad\",\"dependencies\":[\"step-win-2\"],\"parameters\":{\"windowTitle\":\"Notepad\",\"controlName\":\"Text editor\",\"text\":\"{{step-obs-1.bill_summary}}\"}}]}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 142,
    "completion_tokens": 188,
    "total_tokens": 330
  }
}
```

---

## 3. Model 2: Meta Muse Wonder 1.0 (`muse-wonder-1.0`)

### 3.1 Invocation Trace & Visual Payload
- **Endpoint**: `POST https://api.meta.ai/v1/chat/completions`
- **Purpose**: Independent visual verification of UI postconditions.

```json
{
  "model": "muse-wonder-1.0",
  "messages": [
    {
      "role": "system",
      "content": "You are Muse Wonder 1.0, the independent visual verification model for Sahaay. Inspect the provided UI screenshot and verify whether the specified postcondition is visually confirmed."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Expected postcondition: Windows Notepad is open with the text containing 'Electricity Bill Summary: Customer: BESCOM Consumer | Amount: ₹1,420 | Due: 2026-11-15'. Does the screenshot verify this?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAAAAAMACAIAAAB9w..."
          }
        }
      ]
    }
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.0
}
```

### 3.2 Visual Verification Response
```json
{
  "id": "chatcmpl-wonder-47219",
  "model": "muse-wonder-1.0",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "{\"is_verified\": true, \"confidence\": 0.98, \"detected_window\": \"Notepad\", \"text_match\": true, \"anomalies_detected\": []}"
      }
    }
  ]
}
```

---

## 4. Model 3: Meta Voice (`muse-voice-1.0`)

### 4.1 Invocation Trace & Audio Payload
- **Endpoint**: `POST https://api.meta.ai/v1/audio/transcriptions`
- **Purpose**: Streaming speech recognition with Indic priority language hints.

```http
POST /v1/audio/transcriptions HTTP/1.1
Host: api.meta.ai
Authorization: Bearer <META_API_KEY>
Content-Type: multipart/form-data; boundary=---------------------------974767299852498929531610575

-----------------------------974767299852498929531610575
Content-Disposition: form-data; name="file"; filename="recording.webm"
Content-Type: audio/webm; codecs=opus

<Opus Encoded Binary Audio Stream (3.4 seconds)>
-----------------------------974767299852498929531610575
Content-Disposition: form-data; name="model"

muse-voice-1.0
-----------------------------974767299852498929531610575
Content-Disposition: form-data; name="language_hints"

kn,hi,en
-----------------------------974767299852498929531610575--
```

### 4.2 Transcription Response
```json
{
  "transcript": "Bill nodi, consumer number extract maadi, Notepad ge bariyiri",
  "detected_language": "kn",
  "confidence": 0.96,
  "normalized_english_intent": "Inspect the open bill, extract the consumer number, and write it into Notepad."
}
```

---

## 5. Privacy Gateway Evaluation Proof

Every request above passes through `PrivacyGateway.evaluate_outbound_request()` prior to outbound socket transmission.

### Sample Privacy Log:
```text
[PrivacyGateway] EVALUATION:
- Outbound Destination: https://api.meta.ai/v1/chat/completions
- Secret Scan: PASS (Zero API keys, private keys, or passwords detected)
- PII Minimizer: PASS (Non-sensitive billing metadata)
- Session Mode: HOSTED_ALLOWED (local_only_mode = False)
- Decision: ALLOW_TRANSMISSION
```

