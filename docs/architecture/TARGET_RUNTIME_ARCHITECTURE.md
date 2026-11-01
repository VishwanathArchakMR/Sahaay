# SAHAAY — TARGET RUNTIME ARCHITECTURE SPECIFICATION

## 1. System Topology Overview

Sahaay operates as a distributed, high-performance, local-loopback multi-process system engineered specifically for Windows 10/11 and Chromium-based browsers (Chrome / Edge).

```mermaid
graph TB
    subgraph Frontend Surface Layer
        Electron[Electron 30+ Desktop Client<br/>Aurora Glass React 18 UI]
        Sidepanel[Chromium MV3 Extension Sidepanel<br/>DOM Observer & Fast Action Trigger]
    end

    subgraph Core Coordination & Safety Tier
        FastAPI[FastAPI Backend Engine<br/>Uvicorn Loopback Port 8000]
        Privacy[Privacy Gateway<br/>PII Redactor & Secret Scanner]
        Gate[Action Gate<br/>Least-Privilege Policy Evaluator]
        DAG[Task DAG Engine<br/>Topological Dependency Scheduler]
        Verifier[Independent Verifier<br/>Readback Assertion Engine]
    end

    subgraph Operating System & Browser Execution Tier
        NativeHost[Sahaay.NativeHost.exe<br/>Standard I/O Native Messaging Bridge]
        WinController[Sahaay.Controller.exe<br/>Named Pipe UI Automation Server]
        WinUIA[Windows Desktop Applications<br/>Notepad, Calc, File Explorer via UIA]
        ChromeTabs[Active Chromium Browser Tabs<br/>Content Scripts & Accessibility Nodes]
    end

    subgraph Meta Cloud Model Tier
        MetaVoice[Meta SeamlessStreaming / Whisper Voice]
        MuseSpark[Meta Muse Spark 1.3 Reasoning & DAG Planning]
        MuseWonder[Meta Muse Wonder 1.0 Visual Verification]
        SAM[Meta SAM 3.1 UI Segmentation & Grounding]
    end

    subgraph Persistent Provenance Tier
        SQLite[(SQLite Durable Storage<br/>Tasks, Grants, SHA-256 Ledger)]
    end

    Electron -- HTTP Loopback + X-Sahaay-Token --> FastAPI
    Sidepanel -- HTTP Loopback + X-Sahaay-Token --> FastAPI
    Sidepanel -- chrome.runtime.connectNative --> NativeHost
    NativeHost -- IPC Loopback --> FastAPI
    FastAPI -- Named Pipe: \\.\pipe\SahaayControllerPipe --> WinController
    WinController --> WinUIA
    FastAPI --> Privacy
    Privacy -- Encrypted Outbound HTTPS --> MuseSpark
    Privacy -- Encrypted Outbound HTTPS --> MetaVoice
    Privacy -- Encrypted Outbound HTTPS --> MuseWonder
    FastAPI --> Gate
    Gate --> DAG
    DAG --> WinController
    DAG --> Sidepanel
    DAG --> Verifier
    Verifier --> WinController
    Verifier --> Sidepanel
    Verifier --> SQLite
```

---

## 2. Core Subsystems and IPC Contracts

### 2.1 Electron Desktop Client
- **Runtime**: Electron 30.x with Node 20+ and Chromium.
- **Frontend Framework**: React 18 with TypeScript and Vite.
- **Visual Design**: Liquid Flow Aurora Glass aesthetic (translucent glassmorphism, dynamic glow gradients, responsive typography).
- **Communication**: Interacts with FastAPI backend via authenticated HTTP loopback (`http://127.0.0.1:8000/api/v1`) using bearer pairing tokens passed via Electron preload scripts.

### 2.2 Chromium MV3 Extension
- **Manifest Version**: Manifest V3 compliant.
- **Components**:
  - `background.ts`: Service worker managing extension lifecycle and native messaging port connections.
  - `sidepanel.ts`: Interactive HTML5 sidebar providing in-browser assistance without covering page content.
  - `content.ts`: Injected script extracting visible text, semantic accessibility trees, and form inputs.
- **Security**: Strict Content Security Policy (`script-src 'self'`), zero inline script handlers, zero eval.

### 2.3 FastAPI Core Backend
- **Framework**: FastAPI (Python 3.11/3.12) running under Uvicorn on `127.0.0.1:8000`.
- **Role**: Central coordinator managing session lifecycles, capability registries, task state machines, model routing, and persistent evidence ledgers.
- **Security**: CORS restricted to loopback origins and authorized extension IDs; request token verification middleware on all endpoints except health probes.

### 2.4 C# Windows UI Automation Controller (`Sahaay.Controller.exe`)
- **Technology**: .NET 8 / C# Windows Desktop Runtime.
- **IPC Protocol**: Windows Named Pipe: `\\.\pipe\SahaayControllerPipe`.
- **Capabilities**:
  - `LaunchApplication`: Process start and window handle resolution.
  - `SetControlText`: Direct UI Automation `ValuePattern` / `TextPattern` invocation without clipboard hijacking.
  - `ClickControl`: `InvokePattern` / physical coordinate click simulation.
  - `GetActiveWindow` / `InspectTree`: Accessible tree traversal and control hierarchy enumeration.
- **Performance**: Sub-5ms response time over duplex named pipe with length-prefixed JSON messaging.

### 2.5 Chrome Native Messaging Host (`Sahaay.NativeHost.exe`)
- **Technology**: .NET 8 console application implementing Chrome Native Messaging standard I/O protocol (32-bit little-endian message length prefix followed by UTF-8 JSON).
- **Registration**: Registered in `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.sahaay.nativehost`.
- **Bridge Function**: Connects Chrome extensions directly to Sahaay backend without requiring WebSocket servers or open TCP ports.

---

## 3. Security and Privacy Boundaries

```mermaid
flowchart LR
    UserInput[User Voice / Prompt] --> Redaction[Privacy Gateway]
    subgraph Privacy Gateway Boundary
        Redaction --> SecretScan{Secret Scanner}
        SecretScan -- Token / Password / Key --> Reject[Block / Redact]
        SecretScan -- Clean --> PIIFilter[PII Minimizer]
        PIIFilter --> PrivacyDecision{Mode Check}
        PrivacyDecision -- Local-Only Active --> LocalPlanner[Local Grounded Logic]
        PrivacyDecision -- Hosted Allowed --> Outbound[Meta Cloud API Endpoint]
    end
    Outbound --> MetaCloud[Meta Cloud Model]
    LocalPlanner --> ActionGate
    MetaCloud --> ActionGate
    subgraph Action Gate Boundary
        ActionGate --> ScopeCheck{Scope Check}
        ScopeCheck -- Explicit Match --> Execute[Execute Action]
        ScopeCheck -- No Grant / Wildcard Blocked --> Handoff[Request Human Approval]
    end
```

### 3.1 Privacy Gateway (Fail-Closed Default)
- Scans all outbound prompts and contextual facts for secrets, API tokens, passwords, private keys, and high-sensitivity PII before network transmission.
- Evaluates `local_only_mode`. When enabled, blocks all outbound traffic immediately and routes requests to deterministic local planning routines.

### 3.2 Action Gate (Zero-Wildcard Authorization)
- Every proposed execution step must obtain an affirmative `ALLOW` policy decision from `ActionGate.evaluate()`.
- Prohibits wildcard (`*`) capability grants for destructive actions.
- Scopes are matched against exact application names (e.g. `Notepad`) or specific URL origins.
- Unmatched actions transition the task to `HANDOFF_REQUESTED`, surfacing the **APPROVE / TAKE OVER** controls in the user interface.

### 3.3 Independent Verification & Cryptographic Ledger
- Sahaay strictly decouples action execution from action verification.
- An action is never assumed successful based on the model's self-attestation or driver return code alone.
- The `IndependentVerifier` reads back postcondition state (e.g., querying the active Notepad text box via UI Automation `ValuePattern` to verify the written content matches the extracted text).
- Verified results are serialized, hashed (SHA-256), and appended to the immutable SQLite ledger (`sahaay.db`).

