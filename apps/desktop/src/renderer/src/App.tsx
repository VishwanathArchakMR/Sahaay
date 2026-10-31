import React, { useEffect, useState, useRef } from "react";
import {
  Mic,
  Send,
  Pause,
  Globe,
  Monitor,
  Folder,
  LayoutGrid,
  Clock,
  Settings,
  PlusCircle,
  Home,
  CheckCircle2,
  RefreshCw,
  Search,
  FileText,
  Sparkles,
  ArrowRight,
  Camera,
  Bell,
  Activity,
  X,
} from "lucide-react";

const API_BASE = "http://127.0.0.1:8000/api/v1";

let dynamicApiToken = "";
if (typeof window !== "undefined" && (window as any).sahaay?.getApiToken) {
  (window as any).sahaay.getApiToken().then((t: string) => {
    if (t) dynamicApiToken = t;
  });
}

const getApiHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (dynamicApiToken) {
    headers["X-Sahaay-Token"] = dynamicApiToken;
  } else {
    headers["X-Sahaay-Token"] = "dev-local-sahaay-token";
  }
  return headers;
};

const API_HEADERS = getApiHeaders();

type TaskFlowState =
  | "IDLE"
  | "OBSERVE"
  | "RETRIEVE"
  | "PROPOSE"
  | "AUTHORIZE"
  | "EXECUTE_B2D"
  | "EXECUTE_D2B"
  | "VERIFY"
  | "VERIFIED"
  | "FAILED"
  | "HANDOFF";

interface MilestoneCardData {
  stepId: string;
  stepIndex: number;
  title: string;
  operation: string;
  source?: string;
  destination?: string;
  status: string;
  description: string;
  evidenceId?: string;
  isVerified: boolean;
  imageUrl?: string;
  parameters?: Record<string, any>;
}

interface TaskPassportData {
  taskId: string;
  workflowMode: string;
  direction?: string;
  status: string;
  sourceUrl?: string;
  targetWindow?: string;
  summary: string;
  milestones: MilestoneCardData[];
  provenanceSha256?: string;
  verifiedTimestamp?: string;
}

interface ModelsStatusReport {
  museSpark?: { isConfigured: boolean; baseUrl: string; model: string; status: string };
  metaHosted?: {
    isConfigured: boolean;
    baseUrl: string;
    models: {
      museSpark: { id: string; role: string; ready: boolean };
      museWonder: { id: string; role: string; ready: boolean };
      museVoice: { id: string; role: string; ready: boolean };
      sam31: { id: string; role: string; ready: boolean };
    };
  };
  localLlama?: {
    status: string;
    isReady: boolean;
    hardwareProfile?: { cpuCores: number; gpuDetected?: boolean; gpuName?: string };
  };
  systemIntegrations?: {
    browserExtension: string;
    nativeMessaging: string;
    windowsCompanion: string;
    sqliteLedger: string;
  };
  privacyMode?: {
    localOnlyMode: boolean;
    hostedModelsPermitted: boolean;
  };
}

export function App(): React.JSX.Element {
  // Navigation & View state
  const [activeNav, setActiveNav] = useState<
    "home" | "tasks" | "computer" | "browser" | "files" | "apps" | "voice" | "history" | "settings"
  >("home");
  const [selectedContexts, setSelectedContexts] = useState<Set<string>>(
    new Set(["Computer", "Browser", "Files", "Apps", "Voice"])
  );

  // Session & Privacy
  const [sessionId, setSessionId] = useState<string>("");
  const [localOnlyMode, setLocalOnlyMode] = useState<boolean>(true);

  // Active Task & Status
  const [taskState, setTaskState] = useState<TaskFlowState>("IDLE");
  const [activeTaskId, setActiveTaskId] = useState<string>("");
  const [statusNarrative, setStatusNarrative] = useState<string>(
    "Sahaay agent is idle. Ready for voice or text prompt."
  );

  // Health & Diagnostics
  const [isBackendReachable, setIsBackendReachable] = useState<boolean>(false);
  const [modelsStatus, setModelsStatus] = useState<ModelsStatusReport | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isProbing, setIsProbing] = useState<boolean>(false);

  // Persistent Tasks Ledger
  const [tasksList, setTasksList] = useState<Array<{
    taskId: string;
    sessionId: string;
    goal: string;
    taskType: string;
    status: string;
    createdAt: string;
    completedAt?: string;
  }>>([]);

  // Composer & Voice
  type MicState =
    | "PERMISSION_REQUIRED"
    | "READY"
    | "RECORDING"
    | "PROCESSING"
    | "TRANSCRIBED"
    | "FAILED"
    | "UNAVAILABLE";
  const [userPrompt, setUserPrompt] = useState<string>("");
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [micState, setMicState] = useState<MicState>("READY");
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);

  // Task Passport & History
  const [taskPassport, setTaskPassport] = useState<TaskPassportData | null>(null);
  const [timeline, setTimeline] = useState<
    Array<{
      id: string;
      timestamp: string;
      step: string;
      state: TaskFlowState;
      title: string;
      details: string;
      provenanceHash?: string;
    }>
  >([]);

  const recordingIntervalRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    initSession();
    runDiagnosticsProbe();
    const interval = setInterval(runDiagnosticsProbe, 5000);
    return () => clearInterval(interval);
  }, []);

  const initSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({ localOnlyMode }),
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.sessionId);
        setIsBackendReachable(true);
        addTimelineEntry(
          "IDLE",
          "Session Initialized",
          `Session: ${data.sessionId.slice(0, 8)}... (${data.localOnlyMode ? "Local-Only Mode" : "Hosted Allowed"})`
        );
      } else {
        setIsBackendReachable(false);
      }
    } catch {
      setIsBackendReachable(false);
    }
  };

  const runDiagnosticsProbe = async () => {
    setIsProbing(true);
    try {
      const res = await fetch(`${API_BASE}/health`, { headers: getApiHeaders() });
      setIsBackendReachable(res.ok);
    } catch {
      setIsBackendReachable(false);
    }

    try {
      const res = await fetch(`${API_BASE}/models/status`, { headers: getApiHeaders() });
      if (res.ok) {
        const data = await res.json();
        setModelsStatus(data);
        if (data.privacyMode?.localOnlyMode !== undefined) {
          setLocalOnlyMode(data.privacyMode.localOnlyMode);
        }
      }
    } catch {
      // offline probe
    }

    try {
      const res = await fetch(`${API_BASE}/tasks?limit=20`, { headers: getApiHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTasksList(data);
        }
      }
    } catch {
      // offline tasks probe
    }
    setIsProbing(false);
  };

  const toggleLocalOnlyMode = async () => {
    const newMode = !localOnlyMode;
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({ localOnlyMode: newMode }),
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.sessionId);
        setLocalOnlyMode(data.localOnlyMode);
        addTimelineEntry(
          "IDLE",
          "Privacy Mode Toggled",
          `Local-Only Mode is now: ${newMode ? "ACTIVE" : "DISABLED"}`
        );
      }
    } catch (e) {
      console.error("Failed to toggle privacy mode:", e);
    }
  };

  const addTimelineEntry = (
    state: TaskFlowState,
    title: string,
    details: string,
    provenanceHash?: string
  ) => {
    setTimeline((prev) => [
      {
        id: crypto.randomUUID(),
        timestamp: new Date().toLocaleTimeString(),
        step: state,
        state,
        title,
        details,
        provenanceHash,
      },
      ...prev.slice(0, 19),
    ]);
  };

  const fetchTaskPassport = async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/passport`, { headers: API_HEADERS });
      if (res.ok) {
        const data = await res.json();
        setTaskPassport(data);
      }
    } catch (err) {
      console.warn("Could not fetch Task Passport:", err);
    }
  };

  const toggleContext = (ctx: string) => {
    setSelectedContexts((prev) => {
      const next = new Set(prev);
      if (next.has(ctx)) next.delete(ctx);
      else next.add(ctx);
      return next;
    });
  };

  // Execution Handlers
  const fetchTasksList = async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks?limit=20`, { headers: getApiHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTasksList(data);
        }
      }
    } catch {
      // offline tasks probe
    }
  };

  const triggerPromptExecution = async (promptText: string) => {
    if (!promptText.trim()) return;
    const lower = promptText.toLowerCase();

    // Reset voice/mic state if left hanging
    if (isRecording || micState === "RECORDING" || micState === "PROCESSING") {
      setIsRecording(false);
      setMicState("READY");
    }

    // Workflow mode detection
    const isAskMode =
      lower.startsWith("find") ||
      lower.startsWith("search") ||
      lower.startsWith("what") ||
      lower.startsWith("summarize") ||
      lower.startsWith("read") ||
      lower.startsWith("extract");
    const isDoMode =
      lower.startsWith("open") ||
      lower.startsWith("calculate") ||
      lower.startsWith("launch") ||
      lower.startsWith("write") ||
      lower.startsWith("fill");
    const workflowMode = isAskMode ? "ask" : isDoMode ? "do" : "combined_retrieval_and_action";

    setTaskState("PROPOSE");
    setStatusNarrative(`Formulating plan for: "${promptText}" (${workflowMode.toUpperCase()})...`);
    addTimelineEntry("PROPOSE", `Goal: "${promptText.slice(0, 48)}..."`, "Decomposing task with Muse Spark");

    try {
      setTaskState("EXECUTE_B2D");
      setStatusNarrative("Executing task across authorized Windows & Browser capabilities...");

      const res = await fetch(`${API_BASE}/workflows/execute-goal`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({
          sessionId: sessionId || "00000000-0000-0000-0000-000000000001",
          goal: promptText,
          workflowMode,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Server returned ${res.status}`);

      if (data.taskId) {
        setActiveTaskId(data.taskId);
        await fetchTaskPassport(data.taskId);
      }

      if ((data.status === "VERIFIED" || data.status === "COMPLETED") && data.isVerified) {
        setTaskState("VERIFIED");
        const facts = data.accumulatedFacts || {};
        const summary =
          facts.bill_summary ||
          facts.deadline_summary ||
          facts.key_findings ||
          facts.calculation_result ||
          `Task completed successfully with ${data.completedSteps}/${data.totalSteps} steps verified.`;

        setStatusNarrative(`VERIFIED: ${summary}`);
        addTimelineEntry("VERIFIED", `Task Verified (${data.completedSteps}/${data.totalSteps} Steps)`, summary);
      } else if (data.status === "FAILED") {
        setTaskState("FAILED");
        setStatusNarrative(`TASK FAILED: ${data.error || "Verification failed."}`);
        addTimelineEntry("FAILED", "Task Failed", data.error || "Postcondition check failed");
      } else {
        setTaskState("HANDOFF");
        setStatusNarrative(`STATUS: ${data.status} — Awaiting human authorization.`);
        addTimelineEntry("HANDOFF", `Status: ${data.status}`, "Action Gate requested approval");
      }
      await fetchTasksList();
    } catch (err: any) {
      setTaskState("FAILED");
      setStatusNarrative(`Execution error: ${err.message}`);
      addTimelineEntry("FAILED", "Error", err.message);
      await fetchTasksList();
    }
  };

  const handleStopExecution = async () => {
    if (activeTaskId) {
      await fetch(`${API_BASE}/tasks/${activeTaskId}/cancel`, {
        method: "POST",
        headers: getApiHeaders(),
      }).catch(() => {});
    }
    setTaskState("IDLE");
    setStatusNarrative("Task execution stopped by user.");
  };

  // Voice recording toggle
  const toggleRecording = async () => {
    if (isRecording) {
      if (recordingIntervalRef.current) clearInterval(recordingIntervalRef.current);
      setIsRecording(false);
      setRecordingSeconds(0);
      setMicState("PROCESSING");
      setStatusNarrative("Processing microphone audio with speech-to-text...");

      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    } else {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          setMicState("UNAVAILABLE");
          setStatusNarrative("Microphone is not supported in this environment.");
          return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        audioChunksRef.current = [];

        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/wav";

        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
        };

        recorder.onstop = async () => {
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
          }

          if (audioChunksRef.current.length === 0) {
            setMicState("FAILED");
            setStatusNarrative("No audio captured from microphone.");
            return;
          }

          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType || "audio/wav" });
          const formData = new FormData();
          formData.append("file", audioBlob, "recording.wav");
          formData.append("languageHints", "kn,hi,en");
          if (sessionId) formData.append("sessionId", sessionId);

          try {
            const res = await fetch(`${API_BASE}/models/transcribe`, {
              method: "POST",
              headers: dynamicApiToken
                ? { "X-Sahaay-Token": dynamicApiToken }
                : { "X-Sahaay-Token": "dev-local-sahaay-token" },
              body: formData,
            });

            if (res.ok) {
              const data = await res.json();
              if (data.status === "BLOCKED_BY_PRIVACY") {
                setMicState("FAILED");
                setStatusNarrative(
                  "Hosted voice transcription is blocked because Local-Only Mode is active. Switch to hosted mode in Settings or type your request."
                );
              } else if (data.status === "NOT_CONFIGURED") {
                setMicState("FAILED");
                setStatusNarrative(
                  "Meta API key is not configured for voice transcription. Type your task or configure credentials in Settings."
                );
              } else if (data.transcript && data.transcript.trim()) {
                setMicState("TRANSCRIBED");
                setUserPrompt(data.transcript);
                setStatusNarrative(`Transcript: "${data.transcript}". Review or edit before sending.`);
              } else {
                setMicState("FAILED");
                setStatusNarrative(
                  `Voice transcription returned no speech (${data.error || "empty transcript"}).`
                );
              }
            } else {
              setMicState("FAILED");
              setStatusNarrative(`Voice transcription service returned error ${res.status}.`);
            }
          } catch (fetchErr: any) {
            setMicState("FAILED");
            setStatusNarrative(`Voice transcription network error: ${fetchErr.message}`);
          }
        };

        recorder.start(250);
        setIsRecording(true);
        setMicState("RECORDING");
        setRecordingSeconds(0);
        recordingIntervalRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
        setStatusNarrative("Microphone listening... Speak your task clearly.");
      } catch (err: any) {
        setMicState("PERMISSION_REQUIRED");
        setStatusNarrative(`Microphone access error: ${err.message}`);
        setIsRecording(false);
      }
    }
  };

  return (
    <div className="app-shell">
      {/* Ambient Liquid Flow Aurora Backdrop */}
      <div className="aurora-backdrop" aria-hidden="true" />

      {/* 1. Left Translucent Navigation Rail */}
      <aside className="nav-rail glass-surface">
        <div>
          {/* Logo & Brand */}
          <div className="brand-header">
            <svg className="brand-logo-svg" width="28" height="28" viewBox="0 0 32 32" fill="none">
              <path
                d="M7 16C7 11.0294 11.0294 7 16 7C20.9706 7 25 11.0294 25 16C25 20.9706 20.9706 25 16 25"
                stroke="url(#desktop-logo-grad)"
                strokeWidth="3.2"
                strokeLinecap="round"
              />
              <path
                d="M12 21C10.5 19.5 10 17 11 15C12 13 14.5 12 17 12.5C19.5 13 21 15 20.5 17.5C20 20 17.5 21.5 15 21"
                stroke="#8AF5CF"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <defs>
                <linearGradient id="desktop-logo-grad" x1="7" y1="7" x2="25" y2="25" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#8AF5CF" />
                  <stop offset="0.5" stopColor="#35D8C6" />
                  <stop offset="1" stopColor="#55D8FF" />
                </linearGradient>
              </defs>
            </svg>
            <span style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: "bold", color: "#fff" }}>
              Sahaay
            </span>
          </div>

          {/* Navigation Links */}
          <nav className="nav-links-list">
            <button
              onClick={() => setActiveNav("home")}
              className={`nav-rail-item ${activeNav === "home" ? "active" : ""}`}
              style={{ justifyContent: "space-between" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Home size={16} />
                <span>Home</span>
              </div>
              {activeNav === "home" && <ArrowRight size={14} color="var(--sahaay-mint)" />}
            </button>

            <button
              onClick={() => {
                setActiveNav("home");
                setUserPrompt("");
              }}
              className="nav-rail-item"
            >
              <PlusCircle size={16} color="var(--sahaay-cyan)" />
              <span>New Task</span>
            </button>

            <button
              onClick={() => setActiveNav("computer")}
              className={`nav-rail-item ${activeNav === "computer" ? "active" : ""}`}
            >
              <Monitor size={16} />
              <span>Computer</span>
            </button>

            <button
              onClick={() => setActiveNav("browser")}
              className={`nav-rail-item ${activeNav === "browser" ? "active" : ""}`}
            >
              <Globe size={16} />
              <span>Browser</span>
            </button>

            <button
              onClick={() => setActiveNav("files")}
              className={`nav-rail-item ${activeNav === "files" ? "active" : ""}`}
            >
              <Folder size={16} />
              <span>Files</span>
            </button>

            <button
              onClick={() => setActiveNav("apps")}
              className={`nav-rail-item ${activeNav === "apps" ? "active" : ""}`}
            >
              <LayoutGrid size={16} />
              <span>Apps</span>
            </button>

            <button
              onClick={() => toggleRecording()}
              className={`nav-rail-item ${isRecording ? "active" : ""}`}
            >
              <Mic size={16} color="var(--sahaay-mint)" />
              <span>Voice</span>
            </button>

            <button
              onClick={() => setActiveNav("history")}
              className={`nav-rail-item ${activeNav === "history" ? "active" : ""}`}
            >
              <Clock size={16} />
              <span>History</span>
            </button>

            <button
              onClick={() => setIsSettingsOpen(true)}
              className="nav-rail-item"
            >
              <Settings size={16} />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Mascot 3D Orb Pod */}
        <div className="mascot-orb-container">
          <div className="mascot-orb">
            <div className="mascot-orb-eyes">
              <div className="mascot-eye" />
              <div className="mascot-eye" />
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "12px", fontWeight: "600", color: "#fff" }}>Sahaay</div>
            <div style={{ fontSize: "10px", color: "var(--sahaay-mint)" }}>Ready to help</div>
          </div>
        </div>
      </aside>

      {/* 2. Main Workspace */}
      <div className="workspace-main">
        {/* Top Header / Status bar */}
        <header className="top-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", fontFamily: "var(--font-mono)" }}>
              SESSION: {sessionId ? sessionId.slice(0, 8) : "INITIALIZING"}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Local Mode Pill */}
            <button
              onClick={toggleLocalOnlyMode}
              className="glass-control"
              style={{ padding: "4px 12px", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontWeight: 500 }}
              title="Toggle Local-Only Privacy Mode"
            >
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: localOnlyMode ? "var(--sahaay-mint)" : "var(--sahaay-cyan)",
                  boxShadow: localOnlyMode ? "0 0 8px #8AF5CF" : "none",
                }}
              />
              <span>{localOnlyMode ? "Local Mode" : "Hosted Mode"}</span>
            </button>

            {/* Diagnostics toggle */}
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="glass-control"
              style={{ padding: "6px", display: "flex", alignItems: "center", justifyContent: "center" }}
              title="System Diagnostics"
            >
              <Activity size={16} color="var(--sahaay-cyan)" />
            </button>
          </div>
        </header>

        {/* Workspace Content */}
        <main className="workspace-scrollable">
          {/* A. Hero Greeting */}
          <section className="hero-section">
            <h1 className="hero-title">Good Morning,</h1>
            <h2 className="hero-subtitle">How can I help you today?</h2>

            {/* Quick Category Chips */}
            <div className="chips-row">
              <button
                onClick={() => setUserPrompt("Search recent invoices and summarize key facts")}
                className="glass-control chip-btn"
              >
                <Search size={14} color="var(--sahaay-mint)" />
                <span>Find information</span>
              </button>
              <button
                onClick={() => setUserPrompt("Read local invoice statement and extract details")}
                className="glass-control chip-btn"
              >
                <CheckCircle2 size={14} color="var(--sahaay-teal)" />
                <span>Work with files</span>
              </button>
              <button
                onClick={() => setUserPrompt("Summarize active web browser tab to Notepad")}
                className="glass-control chip-btn"
              >
                <Globe size={14} color="var(--sahaay-cyan)" />
                <span>Use browser</span>
              </button>
              <button
                onClick={() => setUserPrompt("Open Notepad and write project summary")}
                className="glass-control chip-btn"
              >
                <LayoutGrid size={14} color="var(--sahaay-blue)" />
                <span>Open apps</span>
              </button>
              <button
                onClick={() => setUserPrompt("Transfer bill details from browser to desktop")}
                className="glass-control chip-btn"
              >
                <Sparkles size={14} color="var(--sahaay-mint)" />
                <span>Automate tasks</span>
              </button>
            </div>
          </section>

          {/* B. Main Frosted Glass Task Composer */}
          <section className="glass-surface-strong composer-card">
            <div className="composer-top">
              <textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    triggerPromptExecution(userPrompt);
                  }
                }}
                rows={2}
                placeholder="Type your task here or speak..."
                className="composer-textarea"
              />
              {userPrompt && (
                <button
                  onClick={() => setUserPrompt("")}
                  style={{ background: "none", border: "none", color: "var(--sahaay-text-subtle)", cursor: "pointer", padding: "4px" }}
                >
                  <X size={16} />
                </button>
              )}
            </div>

            {/* Middle Row: Waveform & Mic State */}
            <div className="composer-bottom">
              <div className="context-pills">
                {["Computer", "Browser", "Files", "Apps", "Voice"].map((ctx) => {
                  const isSelected = selectedContexts.has(ctx);
                  return (
                    <button
                      key={ctx}
                      onClick={() => toggleContext(ctx)}
                      className={`glass-control context-pill ${isSelected ? "selected" : ""}`}
                      style={{ opacity: isSelected ? 1 : 0.6 }}
                    >
                      {ctx === "Computer" && <Monitor size={12} color="var(--sahaay-cyan)" />}
                      {ctx === "Browser" && <Globe size={12} color="var(--sahaay-teal)" />}
                      {ctx === "Files" && <Folder size={12} color="var(--sahaay-mint)" />}
                      {ctx === "Apps" && <LayoutGrid size={12} color="var(--sahaay-blue)" />}
                      {ctx === "Voice" && <Mic size={12} color="var(--sahaay-mint)" />}
                      <span>{ctx}</span>
                    </button>
                  );
                })}
              </div>

              {/* Waveform & Send Button */}
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div
                  onClick={toggleRecording}
                  className={`waveform-container ${isRecording ? "anim-waveform" : ""}`}
                  style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", padding: "4px 8px", borderRadius: "8px" }}
                  title={isRecording ? `Recording (${recordingSeconds}s)... Click to stop` : `Microphone state: ${micState}. Click to toggle.`}
                >
                  <div className="waveform-bar" style={{ height: isRecording ? "14px" : "6px" }} />
                  <div className="waveform-bar" style={{ height: isRecording ? "20px" : "8px" }} />
                  <div className="waveform-bar" style={{ height: isRecording ? "10px" : "5px" }} />
                  <div className="waveform-bar" style={{ height: isRecording ? "18px" : "7px" }} />
                  <div className="waveform-bar" style={{ height: isRecording ? "12px" : "6px" }} />
                  {isRecording ? (
                    <span style={{ fontSize: "10px", color: "var(--sahaay-mint)", fontFamily: "var(--font-mono)", marginLeft: "4px" }}>
                      {recordingSeconds}s
                    </span>
                  ) : micState === "PROCESSING" ? (
                    <span style={{ fontSize: "10px", color: "var(--sahaay-cyan)", fontFamily: "var(--font-mono)", marginLeft: "4px" }}>
                      Transcribing...
                    </span>
                  ) : null}
                </div>

                <button
                  onClick={() => triggerPromptExecution(userPrompt)}
                  disabled={!userPrompt.trim()}
                  className="btn-aurora-send"
                  title="Execute Task"
                >
                  <Send size={16} color="#041B23" />
                </button>
              </div>
            </div>
          </section>

          {/* C. Live Task Execution Inspector */}
          {taskState !== "IDLE" && (
            <section className="glass-surface task-inspector-box">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="badge badge-success">{taskState}</span>
                  <span style={{ fontSize: "11px", color: "var(--sahaay-cyan)", fontFamily: "var(--font-mono)" }}>
                    Task ID: {activeTaskId ? activeTaskId.slice(0, 8) : "Orchestrating..."}
                  </span>
                </div>
                <button
                  onClick={handleStopExecution}
                  className="btn btn-danger"
                  style={{ padding: "4px 10px", fontSize: "11px" }}
                >
                  <Pause size={12} /> Stop Task
                </button>
              </div>

              {/* 6-Stage Lifecycle Display */}
              <div className="lifecycle-grid">
                {[
                  { label: "1. Observe", active: true },
                  { label: "2. Propose", active: taskState !== "OBSERVE" },
                  { label: "3. Authorize", active: taskState !== "OBSERVE" && taskState !== "PROPOSE" },
                  { label: "4. Execute", active: taskState.startsWith("EXECUTE") || taskState === "VERIFY" || taskState === "VERIFIED" },
                  { label: "5. Verify", active: taskState === "VERIFY" || taskState === "VERIFIED" },
                  { label: "6. Record", active: taskState === "VERIFIED" },
                ].map((s, idx) => (
                  <div
                    key={idx}
                    className={`lifecycle-stage ${s.active ? "active" : "inactive"}`}
                  >
                    {s.label}
                  </div>
                ))}
              </div>

              {/* Narrative Output */}
              <div style={{ padding: "10px 14px", background: "rgba(6, 24, 34, 0.8)", borderRadius: "12px", border: "1px solid rgba(174, 255, 245, 0.15)", display: "flex", alignItems: "flex-start", gap: "10px", fontSize: "12px" }}>
                <Activity size={16} color="var(--sahaay-mint)" style={{ flexShrink: 0, marginTop: "2px" }} />
                <p style={{ flex: 1, color: "var(--sahaay-text)" }}>{statusNarrative}</p>
              </div>

              {/* Task Passport Details */}
              {taskPassport && (
                <div style={{ padding: "12px 14px", background: "rgba(6, 24, 34, 0.9)", borderRadius: "12px", border: "1px solid rgba(174, 255, 245, 0.2)", display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--sahaay-cyan)" }}>
                    <span>TASK PASSPORT: {taskPassport.taskId.slice(0, 8)}...</span>
                    <span>{taskPassport.workflowMode}</span>
                  </div>
                  <p style={{ color: "#fff", fontWeight: 500 }}>{taskPassport.summary}</p>
                  {taskPassport.milestones && taskPassport.milestones.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "4px" }}>
                      {taskPassport.milestones.map((m) => (
                        <div key={m.stepId} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", borderRadius: "8px", background: "rgba(255, 255, 255, 0.04)" }}>
                          <span style={{ color: "#fff" }}>{m.title}</span>
                          <span className="badge badge-success" style={{ fontSize: "10px" }}>{m.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {taskPassport.provenanceSha256 && (
                    <span style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", fontFamily: "var(--font-mono)" }}>
                      Evidence SHA-256: {taskPassport.provenanceSha256}
                    </span>
                  )}
                </div>
              )}
            </section>
          )}

          {/* D. Lower 3 Frosted Glass Cards or History View */}
          {activeNav === "history" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>Execution History & Provenance Ledger</h3>
                <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--sahaay-mint)" }}>{timeline.length} Recorded Events</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "500px", overflowY: "auto" }}>
                {timeline.length === 0 ? (
                  <p style={{ fontSize: "12px", color: "var(--sahaay-text-subtle)" }}>No executions recorded in this session yet.</p>
                ) : (
                  timeline.map((entry) => (
                    <div key={entry.id} style={{ padding: "10px 14px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.05)", display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontWeight: 600, color: "#fff" }}>{entry.title}</span>
                        <span style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", fontFamily: "var(--font-mono)" }}>{entry.timestamp}</span>
                      </div>
                      <p style={{ color: "var(--sahaay-text-muted)" }}>{entry.details}</p>
                      {entry.provenanceHash && (
                        <span style={{ fontSize: "10px", color: "var(--sahaay-cyan)", fontFamily: "var(--font-mono)" }}>
                          Hash: {entry.provenanceHash.slice(0, 32)}...
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>
          ) : (
            <section className="cards-grid">
              {/* Card 1: Active Tasks in Progress */}
              <div className="glass-surface grid-card">
                <div>
                  <div className="card-title-row">
                    <h3 className="card-title">Tasks in Progress</h3>
                    <span style={{ fontSize: "11px", color: "var(--sahaay-text-subtle)" }}>
                      {tasksList.filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED").length} active
                    </span>
                  </div>

                  {tasksList.filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED").length === 0 ? (
                    <div style={{ padding: "20px 10px", textAlign: "center", color: "var(--sahaay-text-subtle)", fontSize: "12px" }}>
                      No active tasks in progress. Enter a prompt above to start an automated task.
                    </div>
                  ) : (
                    <div className="card-items-list">
                      {tasksList
                        .filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED")
                        .slice(0, 3)
                        .map((task) => (
                          <div
                            key={task.taskId}
                            onClick={() => {
                              setActiveTaskId(task.taskId);
                              fetchTaskPassport(task.taskId);
                            }}
                            className="task-progress-item"
                            style={{ cursor: "pointer" }}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "12px" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                                <Activity size={14} color="var(--sahaay-cyan)" style={{ flexShrink: 0 }} />
                                <span style={{ fontWeight: 500, color: "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {task.goal}
                                </span>
                              </div>
                              <span className="badge badge-success" style={{ fontSize: "10px", flexShrink: 0 }}>
                                {task.status}
                              </span>
                            </div>
                            <div style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", fontFamily: "var(--font-mono)", marginTop: "4px" }}>
                              ID: {task.taskId.slice(0, 8)}... • Type: {task.taskType}
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Card 2: Recent tasks (Real SQLite Persistent Ledger) */}
              <div className="glass-surface grid-card">
                <div>
                  <div className="card-title-row">
                    <h3 className="card-title">Recent Tasks</h3>
                    <span style={{ fontSize: "11px", color: "var(--sahaay-mint)", fontFamily: "var(--font-mono)" }}>
                      Verified (SQLite)
                    </span>
                  </div>

                  {tasksList.filter((t) => t.status === "COMPLETED" || t.status === "FAILED" || t.status === "CANCELLED").length === 0 ? (
                    <div style={{ padding: "20px 10px", textAlign: "center", color: "var(--sahaay-text-subtle)", fontSize: "12px" }}>
                      No previous tasks recorded in SQLite ledger. Completed tasks will appear here.
                    </div>
                  ) : (
                    <div className="card-items-list" style={{ gap: "6px" }}>
                      {tasksList
                        .filter((t) => t.status === "COMPLETED" || t.status === "FAILED" || t.status === "CANCELLED")
                        .slice(0, 4)
                        .map((task) => (
                          <div
                            key={task.taskId}
                            onClick={() => {
                              setActiveTaskId(task.taskId);
                              fetchTaskPassport(task.taskId);
                            }}
                            className="recent-task-row"
                            style={{ cursor: "pointer" }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden", flex: 1 }}>
                              <CheckCircle2
                                size={14}
                                color={task.status === "COMPLETED" ? "var(--sahaay-success)" : "var(--sahaay-danger)"}
                                style={{ flexShrink: 0 }}
                              />
                              <span style={{ color: "#fff", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", fontSize: "12px" }}>
                                {task.goal}
                              </span>
                            </div>
                            <span
                              className={`badge ${task.status === "COMPLETED" ? "badge-success" : "badge-danger"}`}
                              style={{ fontSize: "9px", flexShrink: 0, marginLeft: "6px" }}
                            >
                              {task.status}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Card 3: Quick Actions */}
              <div className="glass-surface grid-card">
                <div>
                  <div className="card-title-row">
                    <h3 className="card-title">Quick Actions</h3>
                  </div>

                  <div className="card-items-list" style={{ gap: "4px" }}>
                    <button
                      onClick={() => triggerPromptExecution("Summarize this page and save to Notepad")}
                      className="quick-action-btn"
                    >
                      <FileText size={14} color="var(--sahaay-mint)" />
                      <span>Summarize this page</span>
                    </button>

                    <button
                      onClick={() => triggerPromptExecution("Open Notepad and write summary of bills")}
                      className="quick-action-btn"
                    >
                      <Monitor size={14} color="var(--sahaay-teal)" />
                      <span>Open Notepad</span>
                    </button>

                    <button
                      onClick={() => triggerPromptExecution("Read local invoice statement and extract details")}
                      className="quick-action-btn"
                    >
                      <Folder size={14} color="var(--sahaay-cyan)" />
                      <span>Analyze a file</span>
                    </button>

                    <button
                      onClick={() => triggerPromptExecution("Take a screenshot and inspect active window")}
                      className="quick-action-btn"
                    >
                      <Camera size={14} color="var(--sahaay-blue)" />
                      <span>Take a screenshot</span>
                    </button>

                    <button
                      onClick={() => triggerPromptExecution("Search my files for utility bill")}
                      className="quick-action-btn"
                    >
                      <Search size={14} color="var(--sahaay-mint)" />
                      <span>Search my files</span>
                    </button>

                    <button
                      onClick={() => triggerPromptExecution("Set a reminder to review project budget at 5 PM")}
                      className="quick-action-btn"
                    >
                      <Bell size={14} color="var(--sahaay-warning)" />
                      <span>Set a reminder</span>
                    </button>
                  </div>
                </div>
              </div>
            </section>
          )}
        </main>
      </div>

      {/* 3. System Diagnostics & Settings Modal */}
      {isSettingsOpen && (
        <div className="modal-overlay">
          <div className="glass-surface-strong modal-window">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Activity size={18} color="var(--sahaay-cyan)" />
                <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff" }}>System Diagnostics & Runtime Integrity</h3>
              </div>
              <button onClick={() => setIsSettingsOpen(false)} style={{ background: "none", border: "none", color: "var(--sahaay-text-subtle)", cursor: "pointer", padding: "4px" }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "12px" }}>
              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>FastAPI Backend (http://127.0.0.1:8000)</span>
                <span className={`badge ${isBackendReachable ? "badge-success" : "badge-danger"}`}>
                  {isBackendReachable ? "ONLINE" : "OFFLINE"}
                </span>
              </div>

              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Windows Controller Companion</span>
                <span className="badge badge-success">
                  {modelsStatus?.systemIntegrations?.windowsCompanion || "READY"}
                </span>
              </div>

              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Browser Native Messaging Host</span>
                <span className="badge badge-cyan">
                  {modelsStatus?.systemIntegrations?.nativeMessaging || "REGISTERED"}
                </span>
              </div>

              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Meta Model Routing</span>
                <span className="badge badge-neutral">
                  {modelsStatus?.metaHosted?.isConfigured ? "MUSE SPARK READY" : "LOCAL DETERMINISTIC"}
                </span>
              </div>

              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Privacy Mode</span>
                <span className="badge badge-success">
                  {localOnlyMode ? "STRICT LOCAL-ONLY" : "HOSTED PERMITTED"}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", paddingTop: "8px" }}>
              <button
                onClick={() => {
                  runDiagnosticsProbe();
                }}
                disabled={isProbing}
                className="btn btn-secondary text-xs"
              >
                <RefreshCw size={14} className={isProbing ? "animate-spin" : ""} /> Refresh Probe
              </button>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="btn btn-primary text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
