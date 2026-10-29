import React, { useEffect, useState, useRef } from "react";
import {
  Shield,
  Mic,
  Send,
  Pause,
  Play,
  Cpu,
  Globe,
  AppWindow,
  ArrowRight,
  ArrowLeftRight,
  RefreshCw,
  Layers,
  Sparkles,
  Activity,
  Check,
  Radio,
  Sliders,
  Volume2,
  Compass,
  Wand2,
  Trash2,
  ChevronDown,
  ChevronRight,
  Info,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Database,
  Terminal,
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
  direction?: string;
  status: string;
  description: string;
  evidenceId?: string;
  isVerified: boolean;
  imageUrl?: string;
  svgFallback?: string;
  isIllustrationAiGenerated: boolean;
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
  visualStorytellingEnabled: boolean;
  milestones: MilestoneCardData[];
  provenanceSha256?: string;
  verifiedTimestamp?: string;
}

interface ModelsStatusReport {
  museSpark?: {
    isConfigured: boolean;
    baseUrl: string;
    model: string;
    status: string;
  };
  museImage?: {
    isConfigured: boolean;
    baseUrl: string;
    model: string;
    status: string;
  };
  storytelling?: {
    enabled: boolean;
    budget: number;
  };
  metaHosted: {
    isConfigured: boolean;
    baseUrl: string;
    models: {
      museSpark: { id: string; role: string; ready: boolean };
      museWonder: { id: string; role: string; ready: boolean };
      museVoice: { id: string; role: string; ready: boolean };
      sam31: { id: string; role: string; ready: boolean };
    };
  };
  localLlama: {
    status: string;
    message: string;
    isReady: boolean;
    modelPath: string;
    serverBinary: string;
    serverHost: string;
    port: number;
    hardwareProfile?: {
      cpuCores: number;
      accelerationBackend: string;
      gpuDetected?: boolean;
      gpuName?: string;
      vram?: string;
    };
  };
  systemIntegrations?: {
    browserExtension: string;
    nativeMessaging: string;
    windowsCompanion: string;
    sqliteLedger: string;
  };
  privacyMode: {
    localOnlyMode: boolean;
    hostedModelsPermitted: boolean;
  };
}

export interface SupervisorReport {
  backend: { name: string; status: string; pid?: number; endpoint: string; details: string; restartCount: number };
  controller: { name: string; status: string; pid?: number; endpoint: string; details: string; restartCount: number };
  nativeHost: { name: string; status: string; endpoint: string; details: string };
  overallReady: boolean;
  platform: string;
}

export interface BackendHealthReport {
  status: string;
  systemVersion: string;
  pythonVersion: string;
  localOnlyMode: boolean;
  databaseReady: boolean;
  timestamp: string;
}

export function App(): React.JSX.Element {
  // Session & Core state
  const [sessionId, setSessionId] = useState<string>("");
  const [localOnlyMode, setLocalOnlyMode] = useState<boolean>(true);

  // Active task & Liquid-flow state
  const [taskState, setTaskState] = useState<TaskFlowState>("IDLE");
  const [activeTaskId, setActiveTaskId] = useState<string>("");
  const [statusNarrative, setStatusNarrative] = useState<string>(
    "Sahaay agent is idle. Ready for voice or text prompt."
  );

  // Runtime diagnostics & health state
  const [isBackendReachable, setIsBackendReachable] = useState<boolean>(false);
  const [backendHealth, setBackendHealth] = useState<BackendHealthReport | null>(null);
  const [supervisorReport, setSupervisorReport] = useState<SupervisorReport | null>(null);
  const [micStatus, setMicStatus] = useState<"READY" | "PROMPT" | "DENIED" | "NOT_SUPPORTED">("PROMPT");
  const [lastProbedTime, setLastProbedTime] = useState<string>("");
  const [isProbing, setIsProbing] = useState<boolean>(false);

  // Models diagnostics
  const [modelsStatus, setModelsStatus] = useState<ModelsStatusReport | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isTestingConn, setIsTestingConn] = useState<boolean>(false);
  const [testConnResult, setTestConnResult] = useState<any>(null);

  // Unified composer
  const [userPrompt, setUserPrompt] = useState<string>("");
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [transcriptConfirmation, setTranscriptConfirmation] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string>("kn,hi,en");

  // Evidence & Provenance timeline
  const [timeline, setTimeline] = useState<Array<{
    id: string;
    timestamp: string;
    step: string;
    state: TaskFlowState;
    title: string;
    details: string;
    provenanceHash?: string;
  }>>([]);

  // Active execution results
  const [lastWorkflowResult, setLastWorkflowResult] = useState<any>(null);

  // Task Passport & Visual Storytelling state
  const [taskPassport, setTaskPassport] = useState<TaskPassportData | null>(null);
  const [activeRightTab, setActiveRightTab] = useState<"passport" | "timeline">("passport");
  const [expandedStepIds, setExpandedStepIds] = useState<Set<string>>(new Set());
  const [illustratingStepId, setIllustratingStepId] = useState<string | null>(null);

  const recordingIntervalRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // 1. Initialize session and probe diagnostics
  useEffect(() => {
    initSession();
    runDiagnosticsProbe();
    const interval = setInterval(() => {
      runDiagnosticsProbe();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const runDiagnosticsProbe = async () => {
    setIsProbing(true);
    setLastProbedTime(new Date().toLocaleTimeString());

    // 1. Probe supervisor via Electron IPC
    if (typeof window !== "undefined" && (window as any).sahaay?.getRuntimeHealth) {
      try {
        const rep = await (window as any).sahaay.getRuntimeHealth();
        setSupervisorReport(rep);
      } catch (e) {
        console.warn("Supervisor IPC unavailable:", e);
      }
    }

    // 2. Probe FastAPI Backend /health
    try {
      const res = await fetch(`${API_BASE}/health`, { headers: getApiHeaders() });
      if (res.ok) {
        const data = await res.json();
        setBackendHealth(data);
        setIsBackendReachable(true);
      } else {
        setIsBackendReachable(false);
      }
    } catch {
      setIsBackendReachable(false);
    }

    // 3. Probe Models & Integrations
    try {
      const res = await fetch(`${API_BASE}/models/status`, { headers: getApiHeaders() });
      if (res.ok) {
        const data = await res.json();
        setModelsStatus(data);
        setLocalOnlyMode(data.privacyMode?.localOnlyMode ?? true);
      }
    } catch {
      // offline probe
    }

    // 4. Probe Microphone Permission
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMicStatus("NOT_SUPPORTED");
      } else if (navigator.permissions && (navigator.permissions as any).query) {
        const p = await (navigator.permissions as any).query({ name: "microphone" });
        if (p.state === "granted") setMicStatus("READY");
        else if (p.state === "denied") setMicStatus("DENIED");
        else setMicStatus("PROMPT");
      } else {
        setMicStatus("PROMPT");
      }
    } catch {
      setMicStatus("PROMPT");
    }

    setIsProbing(false);
  };

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
        setLocalOnlyMode(data.localOnlyMode);
        setIsBackendReachable(true);
        addTimelineEntry("IDLE", "Session Initialized", `Session ID: ${data.sessionId.slice(0, 8)}... (${data.localOnlyMode ? "Local-only mode active" : "Hosted models permitted"})`);
      } else {
        setIsBackendReachable(false);
      }
    } catch (err) {
      setIsBackendReachable(false);
      console.warn("Backend not yet reachable on loopback:", err);
    }
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
        addTimelineEntry("IDLE", "Privacy Mode Toggled", `Local-Only Mode is now: ${newMode ? "ACTIVE" : "DISABLED"}`);
        await runDiagnosticsProbe();
      }
    } catch (e) {
      console.error("Failed to toggle privacy mode:", e);
    }
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

  const toggleStepExpanded = (stepId: string) => {
    setExpandedStepIds((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      return next;
    });
  };

  const handleIllustrateStep = async (stepId: string) => {
    if (!activeTaskId) return;
    setIllustratingStepId(stepId);
    try {
      const res = await fetch(`${API_BASE}/tasks/${activeTaskId}/steps/${stepId}/illustrate`, {
        method: "POST",
        headers: API_HEADERS,
      });
      if (res.ok) {
        await fetchTaskPassport(activeTaskId);
      }
    } catch (err) {
      console.error("Illustration generation failed:", err);
    } finally {
      setIllustratingStepId(null);
    }
  };

  const handleClearArtifacts = async () => {
    if (!activeTaskId) return;
    try {
      const res = await fetch(`${API_BASE}/tasks/${activeTaskId}/artifacts`, {
        method: "DELETE",
        headers: API_HEADERS,
      });
      if (res.ok) {
        await fetchTaskPassport(activeTaskId);
      }
    } catch (err) {
      console.error("Failed to delete artifacts:", err);
    }
  };

  const addTimelineEntry = (state: TaskFlowState, title: string, details: string, provenanceHash?: string) => {
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

  // 2. Cross-Surface Workflow 1: Browser -> Desktop (BESCOM Bill to Notepad)
  const triggerBrowserToDesktopWorkflow = async (isFixture: boolean = true) => {
    if (!sessionId) await initSession();
    setTaskState("OBSERVE");
    setStatusNarrative(
      isFixture
        ? "FIXTURE RUN: Ingesting synthetic BESCOM electricity bill fixture..."
        : "OBSERVE: Reading active authorized browser tab..."
    );
    addTimelineEntry(
      "OBSERVE",
      isFixture ? "Fixture Test Harness" : "Browser Observation",
      isFixture ? "Reading synthetic utility bill fixture" : "Reading active browser tab"
    );

    try {
      setTaskState("AUTHORIZE");
      setStatusNarrative("Action Gate evaluating execution policy and destination window boundary...");

      const res = await fetch(`${API_BASE}/workflows/browser-to-desktop`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({
          sessionId,
          instruction: "Transfer BESCOM electricity bill into target Desktop application",
          targetHwnd: isFixture ? 0 : 1,
          targetControlId: "Edit",
          isFixtureMode: isFixture,
        }),
      });

      const data = await res.json();
      setLastWorkflowResult(data);
      if (data.taskId) {
        setActiveTaskId(data.taskId);
        fetchTaskPassport(data.taskId);
      }

      if (data.status === "VERIFIED" && data.isVerified) {
        setTaskState("VERIFIED");
        setStatusNarrative(
          isFixture
            ? "FIXTURE VERIFIED: Controlled test harness confirmed expected postconditions."
            : "VERIFIED: Independent verifier read back live state from Windows target and confirmed exact match."
        );
        addTimelineEntry(
          "VERIFIED",
          isFixture ? "Fixture Transfer Verified" : "Live Windows Execution Verified",
          `Customer: ${data.sourceProvenance?.extractedFields?.consumer_name} | Amount: ${data.sourceProvenance?.extractedFields?.amount_due}`,
          data.sourceProvenance?.sha256
        );
      } else if (data.status === "HANDOFF") {
        setTaskState("HANDOFF");
        setStatusNarrative("AUTHORIZATION NEEDED: Action Gate denied execution because explicit user consent is required.");
        addTimelineEntry("HANDOFF", "Consent Required", data.detail || "Action Gate requires user authorization");
      } else {
        setTaskState("FAILED");
        setStatusNarrative(`EXECUTION FAILED: ${data.error || data.detail || "Verification failed."}`);
        addTimelineEntry("FAILED", "Task Failed", data.error || data.detail || "Failed verification");
      }
    } catch (err: any) {
      setTaskState("FAILED");
      setStatusNarrative(`Execution error: ${err.message}`);
      addTimelineEntry("FAILED", "Error", err.message);
    }
  };

  // 3. Cross-Surface Workflow 2: Desktop -> Browser (Local Invoice to Web Form)
  const triggerDesktopToBrowserWorkflow = async (isFixture: boolean = true) => {
    if (!sessionId) await initSession();
    setTaskState("OBSERVE");
    setStatusNarrative(
      isFixture
        ? "FIXTURE RUN: Reading authorized invoice statement fixture..."
        : "OBSERVE: Reading authorized local invoice document..."
    );
    addTimelineEntry(
      "OBSERVE",
      isFixture ? "Fixture Document" : "Local Document Ingestion",
      "Reading invoice data"
    );

    try {
      setTaskState("AUTHORIZE");
      setStatusNarrative("Action Gate evaluating form population action. Auto-submit blocked.");

      const res = await fetch(`${API_BASE}/workflows/desktop-to-browser`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({
          sessionId,
          instruction: "Populate utility pay web form from local invoice document",
          isFixtureMode: isFixture,
        }),
      });

      const data = await res.json();
      setLastWorkflowResult(data);
      if (data.taskId) {
        setActiveTaskId(data.taskId);
        fetchTaskPassport(data.taskId);
      }

      if (data.status === "VERIFIED" && data.isVerified) {
        setTaskState("VERIFIED");
        setStatusNarrative(
          "VERIFIED: Web form populated and verified against source document! Auto-submission blocked per safety rules."
        );
        addTimelineEntry(
          "VERIFIED",
          isFixture ? "Fixture Form Population Verified" : "Live Browser Form Population Verified",
          `Customer: ${data.formMapping?.customerName} | Amount: ${data.formMapping?.amountDue} (Auto-submission blocked)`,
          data.sourceProvenance?.sha256
        );
      } else if (data.status === "HANDOFF") {
        setTaskState("HANDOFF");
        setStatusNarrative("AUTHORIZATION NEEDED: Action Gate denied form modification. User consent required.");
        addTimelineEntry("HANDOFF", "Consent Required", data.detail || "User authorization required");
      } else {
        setTaskState("FAILED");
        setStatusNarrative(`EXECUTION FAILED: ${data.error || data.detail || "Verification failed."}`);
        addTimelineEntry("FAILED", "Task Failed", data.error || data.detail || "Failed verification");
      }
    } catch (err: any) {
      setTaskState("FAILED");
      setStatusNarrative(`Execution error: ${err.message}`);
      addTimelineEntry("FAILED", "Error", err.message);
    }
  };

  // 4. Voice Input & Truthful Status Handling
  const toggleRecording = async () => {
    if (isRecording) {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
      setIsRecording(false);
      setRecordingSeconds(0);

      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    } else {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          setStatusNarrative("Microphone access is not supported in this environment.");
          return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        audioChunksRef.current = [];

        const recorder = new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.onstop = async () => {
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
          }

          const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          audioChunksRef.current = [];

          const isVoiceReady = Boolean(modelsStatus?.metaHosted?.models?.museVoice?.ready);
          const isConfigured = Boolean(modelsStatus?.metaHosted?.isConfigured);

          if (!isConfigured || !isVoiceReady) {
            setStatusNarrative(
              `Recorded microphone audio (${(audioBlob.size / 1024).toFixed(1)} KB), but Meta Muse Voice Transcribe is not configured in backend. Type in composer or set MODEL_API_KEY.`
            );
            setTranscriptConfirmation(null);
            return;
          }

          setStatusNarrative("Transcribing audio through Meta Muse Voice Transcribe...");
          try {
            const formData = new FormData();
            formData.append("file", audioBlob, "audio.webm");
            formData.append("languageHints", selectedLanguage || "kn,hi,en");

            const res = await fetch(`${API_BASE}/models/transcribe`, {
              method: "POST",
              headers: API_HEADERS,
              body: formData,
            });

            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              throw new Error(err.detail || `HTTP ${res.status}`);
            }

            const data = await res.json();
            if (data.transcript && data.transcript.trim()) {
              setTranscriptConfirmation(data.transcript.trim());
              setStatusNarrative(`Transcript recognized: "${data.transcript.trim()}". Please confirm or edit.`);
            } else {
              setStatusNarrative("No clear speech detected in audio stream.");
            }
          } catch (err: any) {
            setStatusNarrative(`Voice transcription error: ${err.message}`);
          }
        };

        recorder.start(250);
        setIsRecording(true);
        setRecordingSeconds(0);
        recordingIntervalRef.current = setInterval(() => {
          setRecordingSeconds((s) => s + 1);
        }, 1000);
        setStatusNarrative("Microphone active. Recording speech... Click mic again to stop.");
      } catch (err: any) {
        setStatusNarrative(`Microphone access denied or unavailable: ${err.message}`);
        setIsRecording(false);
      }
    }
  };

  const handleConfirmTranscript = (confirmedText: string) => {
    setUserPrompt(confirmedText);
    setTranscriptConfirmation(null);
    triggerPromptExecution(confirmedText);
  };

  const triggerPromptExecution = async (promptText: string) => {
    if (!promptText.trim()) return;
    const lower = promptText.toLowerCase();

    // Ensure active session
    let currSessionId = sessionId;
    if (!currSessionId) {
      try {
        const sRes = await fetch(`${API_BASE}/sessions`, {
          method: "POST",
          headers: getApiHeaders(),
          body: JSON.stringify({ localOnlyMode }),
        });
        if (sRes.ok) {
          const sData = await sRes.json();
          currSessionId = sData.sessionId;
          setSessionId(sData.sessionId);
        }
      } catch (e) {
        console.error("Could not initialize session:", e);
      }
    }

    // Determine workflowMode: ask (retrieval-only), do (action-only), or combined
    const isAskMode =
      lower.startsWith("find") ||
      lower.startsWith("search") ||
      lower.startsWith("what") ||
      lower.startsWith("summarize") ||
      lower.startsWith("read") ||
      lower.startsWith("extract") ||
      lower.startsWith("check") ||
      lower.includes("report") ||
      lower.includes("notes");

    const isDoMode =
      lower.startsWith("open") ||
      lower.startsWith("calculate") ||
      lower.startsWith("launch") ||
      lower.startsWith("write") ||
      lower.startsWith("fill") ||
      lower.startsWith("click");

    const workflowMode = isAskMode ? "ask" : (isDoMode ? "do" : "combined_retrieval_and_action");

    setTaskState("PROPOSE");
    setStatusNarrative(`Formulating dependency-aware plan for: "${promptText}" (${workflowMode.toUpperCase()} mode)...`);
    addTimelineEntry("PROPOSE", `Goal: "${promptText.slice(0, 48)}..."`, `Decomposing into execution DAG using Meta Muse Spark / deterministic engine`);

    try {
      setTaskState("EXECUTE_B2D");
      setStatusNarrative("Executing dependency-aware task DAG across authorized capabilities...");

      const res = await fetch(`${API_BASE}/workflows/execute-goal`, {
        method: "POST",
        headers: getApiHeaders(),
        body: JSON.stringify({
          sessionId: currSessionId,
          goal: promptText,
          workflowMode,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Server returned ${res.status}`);
      }

      setLastWorkflowResult(data);
      if (data.taskId) {
        setActiveTaskId(data.taskId);
        await fetchTaskPassport(data.taskId);
      }

      if (data.status === "VERIFIED" && data.isVerified) {
        setTaskState("VERIFIED");
        const facts = data.accumulatedFacts || {};
        const summaryText =
          facts.deadline_summary ||
          facts.bill_summary ||
          facts.key_findings ||
          facts.extracted_text ||
          facts.calculation_result ||
          `Task completed successfully with ${data.completedSteps}/${data.totalSteps} steps verified.`;

        setStatusNarrative(`VERIFIED: ${summaryText}`);
        addTimelineEntry(
          "VERIFIED",
          `Task Verified (${data.completedSteps}/${data.totalSteps} Steps)`,
          summaryText,
          data.evidenceIds?.[0] || undefined
        );
      } else if (data.status === "FAILED") {
        setTaskState("FAILED");
        setStatusNarrative(`TASK FAILED: ${data.error || "Step postcondition verification failed."}`);
        addTimelineEntry("FAILED", "Execution Halted", data.error || "Postcondition check failed");
      } else {
        setTaskState("HANDOFF");
        setStatusNarrative(`STATUS: ${data.status} — ${data.error || "Awaiting authorization or manual step."}`);
        addTimelineEntry("HANDOFF", `Status: ${data.status}`, `Workflow ended with status ${data.status}`);
      }
    } catch (err: any) {
      setTaskState("FAILED");
      setStatusNarrative(`Execution error: ${err.message}`);
      addTimelineEntry("FAILED", "Request Error", err.message);
    }
    setUserPrompt("");
  };

  const handleStopExecution = async () => {
    if (activeTaskId) {
      try {
        await fetch(`${API_BASE}/tasks/${activeTaskId}/cancel`, {
          method: "POST",
          headers: getApiHeaders(),
        });
      } catch (e) {
        console.warn("Cancel request failed:", e);
      }
    }
    setTaskState("IDLE");
    setStatusNarrative("Task execution cancelled. Pending actions blocked.");
    addTimelineEntry("HANDOFF", "Cancelled by User", "Execution halted; all pending actions dropped.");
  };

  const testMetaConnectivity = async () => {
    setIsTestingConn(true);
    try {
      const res = await fetch(`${API_BASE}/models/test-connectivity`, {
        method: "POST",
        headers: API_HEADERS,
      });
      const data = await res.json();
      setTestConnResult(data);
    } catch (err: any) {
      setTestConnResult({ error: err.message });
    } finally {
      setIsTestingConn(false);
    }
  };

  // Liquid flow surface render colors & animations
  const getFlowSurfaceStyle = () => {
    switch (taskState) {
      case "OBSERVE":
        return {
          glowColor: "#38bdf8",
          stateLabel: "OBSERVING ACTIVE SURFACE",
          badgeColor: "badge-cyan",
          accentRing: "border-cyan-500/50 shadow-[0_0_30px_rgba(56,189,248,0.3)]",
        };
      case "RETRIEVE":
        return {
          glowColor: "#a855f7",
          stateLabel: "RETRIEVING & GROUNDING CONTEXT",
          badgeColor: "badge-purple",
          accentRing: "border-purple-500/50 shadow-[0_0_30px_rgba(168,85,247,0.3)]",
        };
      case "PROPOSE":
        return {
          glowColor: "#3b82f6",
          stateLabel: "MUSE SPARK PROPOSING PLAN",
          badgeColor: "badge-cyan",
          accentRing: "border-blue-500/50 shadow-[0_0_30px_rgba(59,130,246,0.3)]",
        };
      case "AUTHORIZE":
        return {
          glowColor: "#f59e0b",
          stateLabel: "ACTION GATE AUTHORIZING",
          badgeColor: "badge-warning",
          accentRing: "border-amber-500/50 shadow-[0_0_30px_rgba(245,158,11,0.3)]",
        };
      case "EXECUTE_B2D":
        return {
          glowColor: "#0284c7",
          stateLabel: "EXECUTING: BROWSER → DESKTOP",
          badgeColor: "badge-cyan",
          accentRing: "border-sky-500/60 shadow-[0_0_35px_rgba(2,132,199,0.4)]",
        };
      case "EXECUTE_D2B":
        return {
          glowColor: "#8b5cf6",
          stateLabel: "EXECUTING: DESKTOP → BROWSER",
          badgeColor: "badge-purple",
          accentRing: "border-violet-500/60 shadow-[0_0_35px_rgba(139,92,246,0.4)]",
        };
      case "VERIFY":
        return {
          glowColor: "#10b981",
          stateLabel: "INDEPENDENT VERIFICATION IN PROGRESS",
          badgeColor: "badge-success",
          accentRing: "border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.3)]",
        };
      case "VERIFIED":
        return {
          glowColor: "#10b981",
          stateLabel: "INDEPENDENTLY VERIFIED",
          badgeColor: "badge-success",
          accentRing: "border-emerald-500 shadow-[0_0_40px_rgba(16,185,129,0.45)]",
        };
      case "FAILED":
      case "HANDOFF":
        return {
          glowColor: "#ef4444",
          stateLabel: "SAFETY STOP / HUMAN HANDOFF",
          badgeColor: "badge-danger",
          accentRing: "border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.3)]",
        };
      case "IDLE":
      default:
        return {
          glowColor: "#475569",
          stateLabel: "SYSTEM IDLE & READY",
          badgeColor: "badge-neutral",
          accentRing: "border-white/10",
        };
    }
  };

  const surface = getFlowSurfaceStyle();

  return (
    <div className="flex h-screen w-screen flex-col bg-[#07090e] text-[#f8fafc] select-none font-sans overflow-hidden">
      {/* 1. Header / Navigation Glass Bar */}
      <header className="flex h-14 items-center justify-between border-b border-white/[0.08] bg-[#0a0e17]/80 px-6 backdrop-blur-xl z-20">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 shadow-[0_0_15px_rgba(56,189,248,0.4)]">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="font-heading text-base font-bold tracking-tight text-white">
              Sahaay <span className="text-xs font-normal text-sky-400 font-mono">v0.4-liquid</span>
            </span>
            <span className="ml-2 text-xs text-slate-400 font-hindi">सहाय • Windows Desktop AI Agent</span>
          </div>
        </div>

        {/* Global Status Pills & Actions */}
        <div className="flex items-center gap-3">
          {(() => {
            const isMetaConfigured = Boolean(modelsStatus?.metaHosted?.isConfigured);
            const isLlamaReady = Boolean(modelsStatus?.localLlama?.isReady);
            const isCompanionUp = modelsStatus?.systemIntegrations?.windowsCompanion === "CONNECTED";

            return (
              <>
                {/* 1. Overall System Integrity Pill */}
                <button
                  onClick={() => setIsSettingsOpen(true)}
                  className={`badge ${
                    !isBackendReachable
                      ? "badge-danger animate-pulse"
                      : isCompanionUp
                      ? "badge-success"
                      : "badge-cyan"
                  } flex items-center gap-1.5 cursor-pointer hover:opacity-90 transition-opacity`}
                  title="Click to open System Diagnostics"
                >
                  {!isBackendReachable ? (
                    <>
                      <XCircle className="h-3 w-3 text-rose-400" />
                      <span>Backend Offline</span>
                    </>
                  ) : isCompanionUp ? (
                    <>
                      <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                      <span>System Ready</span>
                    </>
                  ) : (
                    <>
                      <Activity className="h-3 w-3 text-sky-400" />
                      <span>Local Retrieval Ready</span>
                    </>
                  )}
                </button>

                {/* 2. Planner Status */}
                <span
                  className={`badge ${isMetaConfigured ? "badge-cyan" : "badge-neutral"} flex items-center gap-1.5`}
                  title={isMetaConfigured ? "Meta Muse Spark 1.3 configured" : "Deterministic local planner active (Zero external leaks)"}
                >
                  <Radio className={`h-3 w-3 ${isMetaConfigured ? "text-sky-400 animate-pulse" : "text-slate-500"}`} />
                  {isMetaConfigured ? "Meta Muse Spark" : "Local Planner"}
                </span>

                {/* 3. Local Llama */}
                <span
                  className={`badge ${isLlamaReady ? "badge-purple" : "badge-neutral"} flex items-center gap-1.5`}
                  title={isLlamaReady ? "Local Llama 3.2 3B active" : "Local Llama weights not detected"}
                >
                  <Cpu className={`h-3 w-3 ${isLlamaReady ? "text-purple-400" : "text-slate-500"}`} />
                  {isLlamaReady ? "Llama 3.2 Ready" : "Llama Offline"}
                </span>

                {/* 4. Local-Only Mode Toggle */}
                <button
                  onClick={toggleLocalOnlyMode}
                  className={`badge ${localOnlyMode ? "badge-neutral" : "badge-success"} flex items-center gap-1.5 cursor-pointer hover:opacity-90 transition-opacity`}
                  title="Click to toggle Local-Only Privacy Mode"
                >
                  <Shield className="h-3 w-3" />
                  {localOnlyMode ? "Local-Only Mode" : "Hosted Inference Permitted"}
                </button>
              </>
            );
          })()}

          {/* Diagnostics Drawer Toggle */}
          <button
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 transition-colors"
            title="System Diagnostics & Runtime Status"
          >
            <Activity className="h-4 w-4 text-sky-400" />
          </button>
        </div>
      </header>

      {/* Offline Alert Banner if backend is unreachable */}
      {!isBackendReachable && (
        <div className="bg-red-950/75 border-b border-red-500/40 px-6 py-2.5 flex items-center justify-between text-xs text-red-200 z-10 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />
            <span>
              <strong>Core Backend Offline:</strong> FastAPI is unreachable at <code>http://127.0.0.1:8000</code>. Start via <code>.\scripts\start-sahaay.ps1</code> or check supervisor logs.
            </span>
          </div>
          <button
            onClick={runDiagnosticsProbe}
            disabled={isProbing}
            className="btn btn-secondary text-xs py-1 px-3 flex items-center gap-1.5 border border-red-400/30 hover:bg-red-500/20"
          >
            <RefreshCw className={`h-3 w-3 ${isProbing ? "animate-spin" : ""}`} />
            {isProbing ? "Checking..." : "Retry Connection"}
          </button>
        </div>
      )}

      {/* 2. Main Execution Surface */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Column: Interactive Liquid Glass Canvas & Unified Workspace */}
        <main className="flex-1 flex flex-col p-5 gap-4 overflow-y-auto">
          {/* A. The Living Liquid-Flow Surface */}
          <section className={`liquid-canvas-container p-6 relative rounded-2xl transition-all duration-500 border ${surface.accentRing}`}>
            {/* Ambient Background Aura */}
            <div
              className="absolute -top-24 -left-24 w-96 h-96 rounded-full blur-3xl opacity-25 pointer-events-none transition-colors duration-700"
              style={{ backgroundColor: surface.glowColor }}
            />
            <div
              className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full blur-3xl opacity-20 pointer-events-none transition-colors duration-700"
              style={{ backgroundColor: surface.glowColor }}
            />

            <div className="relative z-10 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`badge ${surface.badgeColor}`}>{surface.stateLabel}</span>
                  {taskState !== "IDLE" && (
                    <span className="text-xs text-slate-400 font-mono">
                      Task ID: {activeTaskId ? activeTaskId.slice(0, 8) : "running"}
                    </span>
                  )}
                </div>

                {taskState !== "IDLE" && (
                  <button
                    onClick={handleStopExecution}
                    className="btn btn-danger text-xs py-1 px-3"
                  >
                    <Pause className="h-3 w-3" /> Stop & Cancel
                  </button>
                )}
              </div>

              {/* Dynamic SVG Liquid-Flow Visualization */}
              <div className="h-32 w-full flex items-center justify-center relative my-2">
                <svg className="w-full h-full" viewBox="0 0 800 120" fill="none">
                  <defs>
                    <linearGradient id="liquidGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
                      <stop offset="50%" stopColor="#a855f7" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#10b981" stopOpacity="0.8" />
                    </linearGradient>
                    <filter id="glow">
                      <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                      <feMerge>
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                      </feMerge>
                    </filter>
                  </defs>

                  {/* Surface nodes */}
                  <g transform="translate(100, 60)">
                    <circle r="36" fill="#0f172a" stroke="#38bdf8" strokeWidth="2" filter="url(#glow)" />
                    <Globe className="h-6 w-6 text-sky-400" x="-12" y="-12" />
                    <text y="50" textAnchor="middle" fill="#94a3b8" fontSize="11" fontFamily="sans-serif">Browser Surface</text>
                  </g>

                  {/* Central Flow Stream */}
                  <path
                    d="M 140 60 C 260 20, 340 100, 400 60 C 460 20, 540 100, 660 60"
                    stroke={taskState !== "IDLE" ? "url(#liquidGrad)" : "rgba(255,255,255,0.15)"}
                    strokeWidth={taskState.startsWith("EXECUTE") ? "5" : "3"}
                    fill="none"
                    className={taskState !== "IDLE" ? "anim-flow-stream" : ""}
                  />

                  {/* Central Reasoning Nucleus */}
                  <g transform="translate(400, 60)">
                    <circle
                      r="28"
                      fill="#0f1626"
                      stroke={surface.glowColor}
                      strokeWidth="2.5"
                      className={taskState !== "IDLE" ? "anim-liquid-pulse" : ""}
                    />
                    <Cpu className="h-5 w-5" style={{ color: surface.glowColor }} x="-10" y="-10" />
                    <text y="42" textAnchor="middle" fill="#cbd5e1" fontSize="10" fontFamily="sans-serif">Action Gate & Verifier</text>
                  </g>

                  {/* Desktop node */}
                  <g transform="translate(700, 60)">
                    <circle r="36" fill="#0f172a" stroke="#10b981" strokeWidth="2" filter="url(#glow)" />
                    <AppWindow className="h-6 w-6 text-emerald-400" x="-12" y="-12" />
                    <text y="50" textAnchor="middle" fill="#94a3b8" fontSize="11" fontFamily="sans-serif">Windows Desktop</text>
                  </g>
                </svg>
              </div>

              {/* Real-time Narrative Display */}
              <div className="rounded-xl border border-white/[0.08] bg-[#07090e]/60 p-3.5 backdrop-blur-md">
                <div className="flex items-start gap-3">
                  <Activity className="h-4 w-4 mt-0.5 text-sky-400 shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-200">{statusNarrative}</p>
                    {lastWorkflowResult?.sourceProvenance && (
                      <p className="text-xs text-slate-400 mt-1 font-mono">
                        Source Provenance SHA-256: {lastWorkflowResult.sourceProvenance.sha256.slice(0, 24)}...
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* B. Cross-Surface Quick Workflows */}
          <section className="grid grid-cols-2 gap-4">
            {/* Flow 1 Card */}
            <div className="glass-panel p-4 flex flex-col justify-between border border-white/10 hover:border-sky-500/40 transition-all">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="badge badge-cyan flex items-center gap-1">
                    <ArrowRight className="h-3 w-3" /> Browser &rarr; Desktop
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">DEMO 01</span>
                </div>
                <h3 className="text-sm font-semibold text-white">Extract BESCOM Bill to Notepad</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Extracts synthetic utility bill from browser tab, grounds facts in SQLite, and populates &amp; verifies in desktop window.
                </p>
              </div>
              <button
                onClick={() => triggerBrowserToDesktopWorkflow(true)}
                disabled={taskState !== "IDLE" && taskState !== "VERIFIED" && taskState !== "FAILED"}
                className="btn btn-primary mt-4 w-full text-xs py-2"
              >
                <Play className="h-3.5 w-3.5" /> Run Browser &rarr; Desktop Flow
              </button>
            </div>

            {/* Flow 2 Card */}
            <div className="glass-panel p-4 flex flex-col justify-between border border-white/10 hover:border-purple-500/40 transition-all">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="badge badge-purple flex items-center gap-1">
                    <ArrowLeftRight className="h-3 w-3" /> Desktop &rarr; Browser
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">DEMO 02</span>
                </div>
                <h3 className="text-sm font-semibold text-white">Local Invoice to Web Form</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Reads local invoice statement, maps fields, populates web form via extension, and independently verifies DOM values.
                </p>
              </div>
              <button
                onClick={() => triggerDesktopToBrowserWorkflow(true)}
                disabled={taskState !== "IDLE" && taskState !== "VERIFIED" && taskState !== "FAILED"}
                className="btn btn-primary mt-4 w-full text-xs py-2"
              >
                <Play className="h-3.5 w-3.5" /> Run Desktop &rarr; Browser Flow
              </button>
            </div>
          </section>

          {/* C. Unified Conversation & Task Composer */}
          <section className="glass-panel p-4 rounded-xl border border-white/10 mt-auto">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-sky-400" /> Indic Voice &amp; Semantic Composer
              </span>
              <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
                <span>Biasing:</span>
                {["kn", "hi", "en"].map((lang) => (
                  <button
                    key={lang}
                    onClick={() => setSelectedLanguage(lang)}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      selectedLanguage.includes(lang)
                        ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                        : "bg-white/5 text-slate-400"
                    }`}
                  >
                    {lang.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={toggleRecording}
                className={`btn h-10 w-10 p-0 rounded-xl transition-all ${
                  isRecording
                    ? "bg-rose-600 text-white animate-pulse shadow-[0_0_20px_rgba(244,63,94,0.6)]"
                    : "btn-secondary text-slate-300 hover:text-white"
                }`}
                title={isRecording ? "Stop Recording" : "Record Voice with Muse Voice Transcribe"}
              >
                <Mic className="h-4 w-4" />
              </button>

              <div className="flex-1 relative">
                <input
                  type="text"
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && triggerPromptExecution(userPrompt)}
                  placeholder="Ask Sahaay in Kannada, Hindi, or English (e.g. 'BESCOM bill check maadi Notepad ge copy maadi')..."
                  className="w-full rounded-xl border border-white/10 bg-[#0a0e17]/80 px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500/60 focus:outline-none focus:ring-1 focus:ring-sky-500/40"
                />
                {isRecording && (
                  <span className="absolute right-3 top-2.5 text-xs font-mono text-rose-400 animate-pulse flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-rose-500 inline-block" /> {recordingSeconds}s
                  </span>
                )}
              </div>

              <button
                onClick={() => triggerPromptExecution(userPrompt)}
                disabled={!userPrompt.trim()}
                className="btn btn-primary h-10 px-4 rounded-xl"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </section>
        </main>

        {/* Right Column: Task Passport / Story & Evidence Timeline */}
        <aside className="w-[440px] shrink-0 border-l border-white/[0.08] bg-[#0a0e17]/60 p-4 flex flex-col gap-3 backdrop-blur-xl">
          {/* Dual-tab switch */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div className="flex items-center gap-1.5 p-0.5 rounded-lg bg-black/40 border border-white/5">
              <button
                onClick={() => setActiveRightTab("passport")}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  activeRightTab === "passport"
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Compass className="h-3.5 w-3.5 text-sky-400" /> Task Passport
              </button>
              <button
                onClick={() => setActiveRightTab("timeline")}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  activeRightTab === "timeline"
                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Layers className="h-3.5 w-3.5 text-purple-400" /> Evidence Ledger
              </button>
            </div>
            {activeRightTab === "passport" && taskPassport && (
              <button
                onClick={handleClearArtifacts}
                className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                title="Clear visual artwork (Privacy)"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {activeRightTab === "passport" ? (
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {!taskPassport ? (
                <div className="p-6 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
                  <Compass className="h-8 w-8 text-slate-600 mb-1" />
                  <p className="font-semibold text-slate-400">Task Passport Idle</p>
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    Execute a workflow to generate a visual Step Story and Task Passport. Milestones will be illustrated with Meta Muse Image or obsidian vector graphics, tied directly to independent SQLite evidence.
                  </p>
                </div>
              ) : (
                <>
                  {/* Passport Overview Header */}
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="badge badge-cyan flex items-center gap-1">
                        {taskPassport.direction?.includes("desktop-to-browser") ? (
                          <>
                            <ArrowLeftRight className="h-3 w-3" /> Desktop &rarr; Browser
                          </>
                        ) : (
                          <>
                            <ArrowRight className="h-3 w-3" /> Browser &rarr; Desktop
                          </>
                        )}
                      </span>
                      <span
                        className={`badge ${
                          taskPassport.status === "VERIFIED"
                            ? "badge-success"
                            : taskPassport.status === "FAILED"
                            ? "badge-danger"
                            : "badge-warning"
                        }`}
                      >
                        {taskPassport.status}
                      </span>
                    </div>
                    <p className="text-slate-300 font-medium text-xs leading-relaxed">
                      {taskPassport.summary}
                    </p>
                    {taskPassport.provenanceSha256 && (
                      <div className="text-[10px] font-mono text-slate-400 truncate pt-1 border-t border-white/5">
                        Provenance SHA: {taskPassport.provenanceSha256}
                      </div>
                    )}
                  </div>

                  {/* Milestones Sequence */}
                  <div className="space-y-3">
                    {taskPassport.milestones.map((m) => {
                      const isExpanded = expandedStepIds.has(m.stepId);
                      return (
                        <div
                          key={m.stepId}
                          className="rounded-xl border border-white/10 bg-[#07090e]/80 p-3 text-xs space-y-2.5 transition-all hover:border-white/20"
                        >
                          {/* Milestone Title & Badges */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500/20 text-[10px] font-bold text-sky-300 border border-sky-500/30">
                                {m.stepIndex}
                              </span>
                              <span className="font-semibold text-slate-100">{m.title}</span>
                            </div>
                            <span
                              className={`badge text-[10px] ${
                                m.status === "VERIFIED"
                                  ? "badge-success"
                                  : m.status === "FAILED"
                                  ? "badge-danger"
                                  : "badge-cyan"
                              }`}
                            >
                              {m.status}
                            </span>
                          </div>

                          {/* Source -> Destination Route Badge */}
                          {(m.source || m.destination) && (
                            <div className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                              <span className="text-slate-300">{m.source || "Source"}</span>
                              <span>&rarr;</span>
                              <span className="text-slate-300">{m.destination || "Target"}</span>
                            </div>
                          )}

                          {/* Visual Illustration Canvas */}
                          <div className="relative rounded-lg overflow-hidden border border-white/10 bg-[#05070b]">
                            {m.imageUrl ? (
                              <img
                                src={`http://127.0.0.1:8000${m.imageUrl}`}
                                alt={m.title}
                                className="w-full h-36 object-cover"
                              />
                            ) : m.svgFallback ? (
                              <div
                                className="w-full h-36 flex items-center justify-center"
                                dangerouslySetInnerHTML={{ __html: m.svgFallback }}
                              />
                            ) : (
                              <div className="w-full h-36 flex items-center justify-center text-slate-600 text-[11px]">
                                Illustration pending
                              </div>
                            )}

                            {/* Overlay Badge */}
                            <div className="absolute top-2 right-2">
                              <span className="badge badge-neutral text-[9px] bg-black/70 backdrop-blur-md border-white/15">
                                {m.isIllustrationAiGenerated
                                  ? "AI-Generated Illustration (Muse Image)"
                                  : "Vector Illustration"}
                              </span>
                            </div>

                            {/* Explain this step / Regenerate Button */}
                            <div className="absolute bottom-2 right-2">
                              <button
                                onClick={() => handleIllustrateStep(m.stepId)}
                                disabled={illustratingStepId === m.stepId}
                                className="btn btn-secondary text-[10px] py-1 px-2.5 bg-black/70 backdrop-blur-md border border-white/20 hover:border-sky-400"
                                title="Generate or re-render visual explanation for this step"
                              >
                                {illustratingStepId === m.stepId ? (
                                  <RefreshCw className="h-3 w-3 animate-spin text-sky-400" />
                                ) : (
                                  <Wand2 className="h-3 w-3 text-sky-400" />
                                )}
                                <span>Explain Step</span>
                              </button>
                            </div>
                          </div>

                          {/* AI Disclaimer */}
                          <div className="text-[9px] text-slate-500 italic flex items-center gap-1">
                            <Info className="h-2.5 w-2.5 shrink-0" />
                            <span>AI visual metaphor. Deterministic facts &amp; verification rendered below.</span>
                          </div>

                          {/* Step Description */}
                          <p className="text-slate-300 text-xs leading-relaxed">
                            {m.description}
                          </p>

                          {/* Technical Proof Accordion Toggle */}
                          <div className="border-t border-white/5 pt-2">
                            <button
                              onClick={() => toggleStepExpanded(m.stepId)}
                              className="w-full flex items-center justify-between text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                            >
                              <span className="font-mono">Technical Details &amp; Evidence</span>
                              {isExpanded ? (
                                <ChevronDown className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5" />
                              )}
                            </button>

                            {isExpanded && (
                              <div className="mt-2 rounded-lg bg-black/50 p-2.5 text-[10px] font-mono text-slate-300 space-y-1.5 border border-white/5">
                                <div>
                                  <span className="text-slate-500">Operation: </span>
                                  <span className="text-sky-300">{m.operation}</span>
                                </div>
                                {m.evidenceId && (
                                  <div>
                                    <span className="text-slate-500">Evidence ID: </span>
                                    <span className="text-purple-300">{m.evidenceId}</span>
                                  </div>
                                )}
                                <div>
                                  <span className="text-slate-500">Independent Verification: </span>
                                  <span className={m.isVerified ? "text-emerald-400" : "text-amber-400"}>
                                    {m.isVerified ? "PASSED (Deterministic Proof)" : "UNVERIFIED / PENDING"}
                                  </span>
                                </div>
                                {m.parameters && Object.keys(m.parameters).length > 0 && (
                                  <div className="pt-1">
                                    <span className="text-slate-500">Parameters:</span>
                                    <pre className="mt-1 text-[9px] text-slate-400 overflow-x-auto p-1.5 rounded bg-black/70">
                                      {JSON.stringify(m.parameters, null, 2)}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {timeline.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  No active execution steps yet. Run a workflow to observe evidence recording.
                </div>
              ) : (
                timeline.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-xs space-y-1 hover:border-white/15 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{item.title}</span>
                      <span className="text-[10px] font-mono text-slate-500">{item.timestamp}</span>
                    </div>
                    <p className="text-slate-400 leading-relaxed">{item.details}</p>
                    {item.provenanceHash && (
                      <div className="pt-1 text-[10px] font-mono text-sky-400/90 truncate">
                        SHA: {item.provenanceHash}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </aside>
      </div>

      {/* 3. Editable Speech Transcript Confirmation Dialog */}
      {transcriptConfirmation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-panel-elevated w-full max-w-md p-6 rounded-2xl border border-white/20 flex flex-col gap-4">
            <div className="flex items-center gap-2 text-sky-400">
              <Volume2 className="h-5 w-5" />
              <h2 className="text-base font-bold text-white">Confirm Speech Transcript</h2>
            </div>
            <p className="text-xs text-slate-400">
              Muse Voice Transcribe completed. You may edit the recognized text before consequential execution:
            </p>
            <textarea
              value={transcriptConfirmation}
              onChange={(e) => setTranscriptConfirmation(e.target.value)}
              className="w-full rounded-xl border border-white/15 bg-black/40 p-3 text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
              rows={3}
            />
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setTranscriptConfirmation(null)}
                className="btn btn-secondary text-xs"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConfirmTranscript(transcriptConfirmation)}
                className="btn btn-primary text-xs"
              >
                <Check className="h-3.5 w-3.5" /> Execute Confirmed Task
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Real Runtime Diagnostics & System Integrity Drawer */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-[460px] h-full bg-[#0c1220] border-l border-white/10 p-5 overflow-y-auto flex flex-col gap-4 shadow-2xl">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <span className="font-heading font-bold text-sm text-white flex items-center gap-2">
                  <Activity className="h-4 w-4 text-sky-400" /> System Diagnostics &amp; Runtime Status
                </span>
                <span className="text-[10px] text-slate-400">
                  {lastProbedTime ? `Last probed: ${lastProbedTime}` : "Probing live system..."}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={runDiagnosticsProbe}
                  disabled={isProbing}
                  className="btn btn-secondary text-xs py-1 px-2.5 flex items-center gap-1 border border-white/10"
                  title="Re-probe all system channels and services"
                >
                  <RefreshCw className={`h-3 w-3 ${isProbing ? "animate-spin" : ""}`} />
                  {isProbing ? "Probing..." : "Refresh"}
                </button>
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="text-slate-400 hover:text-white text-lg px-1.5"
                  title="Close Drawer"
                >
                  &times;
                </button>
              </div>
            </div>

            {/* 1. Overall System Integrity Banner */}
            {(() => {
              const isCompanionUp = modelsStatus?.systemIntegrations?.windowsCompanion === "CONNECTED";
              const isBridgeUp = modelsStatus?.systemIntegrations?.nativeMessaging === "CONNECTED";
              const isExtAttached = modelsStatus?.systemIntegrations?.browserExtension === "ATTACHED";

              let overallState = "READY";
              let badgeClass = "badge-success";
              let titleText = "SYSTEM READY";
              const blockingReasons: string[] = [];

              if (!isBackendReachable) {
                overallState = "ERROR";
                badgeClass = "badge-danger";
                titleText = "BACKEND OFFLINE";
                blockingReasons.push("FastAPI Core Backend is not responding on 127.0.0.1:8000. Launch via .\\scripts\\start-sahaay.ps1.");
              } else if (!isCompanionUp) {
                overallState = "DEGRADED";
                badgeClass = "badge-cyan";
                titleText = "DEGRADED (LOCAL RETRIEVAL ONLY)";
                blockingReasons.push("Windows Companion (UIA) named pipe is stopped. Desktop automation degraded; file retrieval active.");
              }

              if (!isExtAttached && isBackendReachable) {
                blockingReasons.push("Browser extension not attached. Requires Sahaay extension loaded in Chrome/Edge on an active tab.");
              }
              if (!isBridgeUp && isBackendReachable) {
                blockingReasons.push("Browser native messaging pipe inactive. Waiting for extension connection.");
              }

              return (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">Overall System Readiness:</span>
                    <span className={`badge ${badgeClass}`}>{overallState}: {titleText}</span>
                  </div>
                  {blockingReasons.length > 0 ? (
                    <div className="space-y-1 pt-1 border-t border-white/5">
                      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Active Operational Blockers:</span>
                      {blockingReasons.map((reason, idx) => (
                        <div key={idx} className="text-[11px] text-amber-300/90 flex items-start gap-1.5">
                          <span className="text-amber-400 shrink-0">•</span>
                          <span>{reason}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-emerald-300/90 pt-1 border-t border-white/5">
                      All core components operational. Desktop and browser capabilities verified.
                    </p>
                  )}
                </div>
              );
            })()}

            {/* 2. Core Platform Services */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-sky-400" /> Core Services &amp; Persistence
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                {/* Desktop App */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Desktop Shell:</span>
                  <span className="badge badge-success">ONLINE {supervisorReport?.platform ? `(${supervisorReport.platform})` : ""}</span>
                </div>

                {/* Backend Reachability */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">FastAPI Core Backend:</span>
                  <span className={`badge ${isBackendReachable ? "badge-success" : "badge-danger"}`}>
                    {isBackendReachable ? `ONLINE (127.0.0.1:8000${supervisorReport?.backend?.pid ? ` PID ${supervisorReport.backend.pid}` : ""})` : "DISCONNECTED"}
                  </span>
                </div>

                {/* SQLite Evidence Ledger */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">SQLite Evidence Ledger:</span>
                  <span className={`badge ${isBackendReachable && backendHealth?.databaseReady ? "badge-success" : "badge-neutral"}`}>
                    {isBackendReachable && backendHealth?.databaseReady ? "READY (WAL MODE)" : "DISCONNECTED"}
                  </span>
                </div>

                {/* Action Gate Policy Engine */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Action Gate &amp; Privacy:</span>
                  <span className="badge badge-success">
                    {localOnlyMode ? "LOCAL-ONLY (FAIL-CLOSED)" : "HOSTED PERMITTED"}
                  </span>
                </div>

                {/* Task Orchestrator Status */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Task Orchestrator:</span>
                  <span className={`badge ${taskState === "IDLE" ? "badge-neutral" : "badge-purple"}`}>
                    {taskState}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. Automation Drivers & Surface Bridges */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <AppWindow className="h-3.5 w-3.5 text-emerald-400" /> Automation Drivers &amp; Bridges
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                {/* Windows Companion Controller */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Windows Controller (UIA):</span>
                    <span className="text-[10px] text-slate-500 font-mono">\\.\pipe\SahaayControllerPipe</span>
                  </div>
                  <span className={`badge ${
                    modelsStatus?.systemIntegrations?.windowsCompanion === "CONNECTED"
                      ? "badge-success"
                      : "badge-neutral"
                  }`}>
                    {modelsStatus?.systemIntegrations?.windowsCompanion || "DISCONNECTED"}
                  </span>
                </div>

                {/* Native Messaging Host */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Native Messaging Host:</span>
                    <span className="text-[10px] text-slate-500 font-mono">com.sahaay.nativehost (HKCU)</span>
                  </div>
                  <span className={`badge ${
                    modelsStatus?.systemIntegrations?.nativeMessaging === "CONNECTED"
                      ? "badge-success"
                      : "badge-neutral"
                  }`}>
                    {modelsStatus?.systemIntegrations?.nativeMessaging || "DISCONNECTED"}
                  </span>
                </div>

                {/* Browser Extension Bridge */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Browser Tab Observation:</span>
                    <span className="text-[10px] text-slate-500">Manifest V3 Extension</span>
                  </div>
                  <span className={`badge ${
                    modelsStatus?.systemIntegrations?.browserExtension === "ATTACHED"
                      ? "badge-success"
                      : modelsStatus?.systemIntegrations?.browserExtension === "HOST_WAITING"
                      ? "badge-warning"
                      : "badge-neutral"
                  }`}>
                    {modelsStatus?.systemIntegrations?.browserExtension || "DISCONNECTED"}
                  </span>
                </div>

                {/* Microphone Readiness */}
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Microphone Audio Capture:</span>
                  <span className={`badge ${
                    micStatus === "READY"
                      ? "badge-success"
                      : micStatus === "DENIED"
                      ? "badge-danger"
                      : "badge-warning"
                  }`}>
                    {micStatus === "READY" ? "READY" : micStatus}
                  </span>
                </div>
              </div>
            </div>

            {/* 4. Model Providers & Reasoning */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-purple-400" /> Model Providers &amp; Intelligence
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                {/* Deterministic Local Provider */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Deterministic Local Provider:</span>
                    <span className="text-[10px] text-slate-500">Zero-leak regex &amp; DAG formulation</span>
                  </div>
                  <span className="badge badge-success">READY</span>
                </div>

                {/* Meta Hosted Suite */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Meta Hosted Suite:</span>
                    <span className="text-[10px] text-slate-500 font-mono">api.meta.ai/v1</span>
                  </div>
                  <span className={`badge ${modelsStatus?.metaHosted?.isConfigured ? "badge-cyan" : "badge-neutral"}`}>
                    {modelsStatus?.metaHosted?.isConfigured ? "CONFIGURED" : "NOT_CONFIGURED"}
                  </span>
                </div>

                {/* Local Llama 3.2 3B */}
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-slate-300 block">Local Llama 3.2 3B:</span>
                    <span className="text-[10px] text-slate-500 font-mono">127.0.0.1:8080</span>
                  </div>
                  <span className={`badge ${modelsStatus?.localLlama?.isReady ? "badge-success" : "badge-neutral"}`}>
                    {modelsStatus?.localLlama?.status || "MODEL_FILE_MISSING"}
                  </span>
                </div>

                {/* Connectivity test button */}
                <button
                  onClick={testMetaConnectivity}
                  disabled={isTestingConn}
                  className="btn btn-secondary w-full text-xs py-1.5 mt-2"
                >
                  <RefreshCw className={`h-3 w-3 ${isTestingConn ? "animate-spin" : ""}`} />
                  {isTestingConn ? "Testing..." : "Test Model Connectivity"}
                </button>

                {testConnResult && (
                  <div className="p-2 rounded bg-black/40 text-[11px] font-mono text-slate-300 mt-2 space-y-1">
                    <div>Meta API: {testConnResult.metaApi?.status || "NOT_CONFIGURED"}</div>
                    <div>Local Llama: {modelsStatus?.localLlama?.status || "NOT_CONFIGURED"}</div>
                  </div>
                )}
              </div>
            </div>

            {/* 5. Quick Corrective Commands */}
            <div className="space-y-2 mt-auto">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Terminal className="h-3.5 w-3.5 text-sky-400" /> Corrective Commands
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 text-[11px] font-mono space-y-1.5 text-slate-400">
                <div># Launch Sahaay:</div>
                <div className="text-sky-300 bg-black/40 px-2 py-1 rounded select-all">.\scripts\start-sahaay.ps1</div>
                <div># Run System Diagnostics:</div>
                <div className="text-sky-300 bg-black/40 px-2 py-1 rounded select-all">.\scripts\start-sahaay.ps1 -DiagnosticsOnly</div>
                <div># Build Windows Controller:</div>
                <div className="text-sky-300 bg-black/40 px-2 py-1 rounded select-all">.\scripts\build-companion.ps1</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
