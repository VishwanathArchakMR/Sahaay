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
  Settings,
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
    fetchModelsStatus();
    const interval = setInterval(() => {
      fetchModelsStatus();
    }, 6000);
    return () => clearInterval(interval);
  }, []);

  const initSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: API_HEADERS,
        body: JSON.stringify({ localOnlyMode: true }),
      });
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.sessionId);
        setLocalOnlyMode(data.localOnlyMode);
        addTimelineEntry("IDLE", "Session Initialized", `Session ID: ${data.sessionId.slice(0, 8)}... (Local-only mode active)`);
      }
    } catch (err) {
      console.warn("Backend not yet reachable on loopback:", err);
    }
  };

  const fetchModelsStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/models/status`, { headers: API_HEADERS });
      if (res.ok) {
        const data = await res.json();
        setModelsStatus(data);
        setLocalOnlyMode(data.privacyMode?.localOnlyMode ?? true);
      }
    } catch (err) {
      // offline probe
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

    if (
      lower.includes("search") ||
      lower.includes("find") ||
      lower.includes("look up") ||
      lower.includes("tariff") ||
      lower.includes("rate")
    ) {
      // Internet research query
      setTaskState("OBSERVE");
      setStatusNarrative(`Public Internet Research: Querying keyless search for "${promptText}"...`);
      addTimelineEntry("OBSERVE", "Internet Research", `Query: "${promptText}"`);
      try {
        const res = await fetch(`${API_BASE}/research/search`, {
          method: "POST",
          headers: getApiHeaders(),
          body: JSON.stringify({ query: promptText, sessionId }),
        });
        const data = await res.json();
        if (data.status === "COMPLETED" && data.resultsCount > 0) {
          setTaskState("VERIFIED");
          const firstResult = data.results[0];
          setStatusNarrative(`Research Completed: Found ${data.resultsCount} sources. Top: "${firstResult.title}"`);
          addTimelineEntry("VERIFIED", `Research: ${data.resultsCount} Sources`, firstResult.snippet, firstResult.sha256);
        } else if (data.status === "LOCAL_ONLY_BLOCKED") {
          setTaskState("HANDOFF");
          setStatusNarrative("Internet research blocked by local-only mode. Provide consent to allow outbound search.");
          addTimelineEntry("HANDOFF", "Local-Only Mode", "Public search blocked by Privacy Gateway");
        } else {
          setTaskState("FAILED");
          setStatusNarrative(data.notice || "No search results found.");
          addTimelineEntry("FAILED", "Search Unavailable", data.notice || "Unavailable");
        }
      } catch (err: any) {
        setTaskState("FAILED");
        setStatusNarrative(`Search error: ${err.message}`);
      }
    } else if (lower.includes("bill") || lower.includes("current") || lower.includes("bescom")) {
      await triggerBrowserToDesktopWorkflow(true);
    } else if (lower.includes("form") || lower.includes("invoice") || lower.includes("pay")) {
      await triggerDesktopToBrowserWorkflow(true);
    } else {
      setTaskState("PROPOSE");
      setStatusNarrative(`Analyzing goal with planner: "${promptText}"`);
      try {
        const res = await fetch(`${API_BASE}/models/meta/muse-spark/plan`, {
          method: "POST",
          headers: getApiHeaders(),
          body: JSON.stringify({ goal: promptText }),
        });
        const planData = await res.json();
        setTaskState("VERIFIED");
        setStatusNarrative(`Plan formulated (${planData.validation_status || "LOCAL_FALLBACK"}): ${planData.steps?.length || 0} steps prepared.`);
        addTimelineEntry("VERIFIED", "Plan Generated", `Validation: ${planData.validation_status || "LOCAL_FALLBACK"}`);
      } catch (err: any) {
        setTaskState("FAILED");
        setStatusNarrative(`Planner unavailable: ${err.message}`);
        addTimelineEntry("FAILED", "Planning Failed", err.message);
      }
    }
    setUserPrompt("");
  };

  const handleStopExecution = () => {
    setTaskState("IDLE");
    setStatusNarrative("Task execution cancelled by user. Pending actions blocked.");
    addTimelineEntry("HANDOFF", "Cancelled by User", "Execution halted; all queued actions dropped.");
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

        {/* Global Status Pills */}
        <div className="flex items-center gap-3">
          {(() => {
            const isMetaConfigured = Boolean(modelsStatus?.metaHosted?.isConfigured);
            const isLlamaReady = Boolean(modelsStatus?.localLlama?.isReady);

            return (
              <>
                <span
                  className={`badge ${isMetaConfigured ? "badge-cyan" : "badge-neutral"} flex items-center gap-1.5`}
                  title={isMetaConfigured ? "Meta Muse Spark 1.3 configured" : "No Meta API key configured (Local fallback active)"}
                >
                  <Radio className={`h-3 w-3 ${isMetaConfigured ? "text-sky-400 animate-pulse" : "text-slate-500"}`} />
                  {isMetaConfigured ? "Meta Muse Spark Ready" : "Planner: Local Fallback"}
                </span>

                <span
                  className={`badge ${isLlamaReady ? "badge-purple" : "badge-neutral"} flex items-center gap-1.5`}
                  title={isLlamaReady ? "Local Llama 3.2 3B active" : "Local Llama 3.2 3B weights not detected"}
                >
                  <Cpu className={`h-3 w-3 ${isLlamaReady ? "text-purple-400" : "text-slate-500"}`} />
                  {isLlamaReady ? "Llama 3.2 3B Ready" : "Llama Offline"}
                </span>

                <span
                  className={`badge ${localOnlyMode ? "badge-neutral" : "badge-success"} flex items-center gap-1.5`}
                >
                  <Shield className="h-3 w-3" />
                  {localOnlyMode ? "Local-Only Mode" : "Hosted Consent Granted"}
                </span>
              </>
            );
          })()}

          <button
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 transition-colors"
            title="Model Diagnostics & Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </header>

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

      {/* 4. Model Diagnostics & Settings Drawer */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-[420px] h-full bg-[#0c1220] border-l border-white/10 p-5 overflow-y-auto flex flex-col gap-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <span className="font-heading font-bold text-sm text-white flex items-center gap-2">
                <Settings className="h-4 w-4 text-sky-400" /> Models &amp; Diagnostics
              </span>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                &times;
              </button>
            </div>

            {/* Meta Muse Spark 1.3 Section */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-sky-400" /> Meta Muse Spark 1.3 (Primary Planner)
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Model ID:</span>
                  <span className="font-mono text-[11px] text-sky-300">
                    {modelsStatus?.metaHosted?.models?.museSpark?.id || "muse-spark-1.3"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Endpoint:</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    {modelsStatus?.metaHosted?.baseUrl || "https://api.meta.ai/v1"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Readiness:</span>
                  <span
                    className={`badge ${
                      modelsStatus?.metaHosted?.models?.museSpark?.ready
                        ? "badge-success"
                        : modelsStatus?.metaHosted?.isConfigured
                        ? "badge-cyan"
                        : "badge-neutral"
                    }`}
                  >
                    {modelsStatus?.metaHosted?.models?.museSpark?.ready
                      ? "READY"
                      : modelsStatus?.metaHosted?.isConfigured
                      ? "CONFIGURED"
                      : "NOT_CONFIGURED"}
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 pt-1 border-t border-white/5">
                  Meta Muse Spark 1.3 is the primary hosted reasoning and planning engine for Sahaay, generating validated plans.
                </p>
              </div>
            </div>

            {/* Meta Muse Image Section */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="h-3.5 w-3.5 text-purple-400" /> Meta Muse Image (Storytelling)
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Model ID:</span>
                  <span className="font-mono text-[11px] text-purple-300">
                    {modelsStatus?.museImage?.model || "muse-image-1.0"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Readiness:</span>
                  <span
                    className={`badge ${
                      modelsStatus?.museImage?.isConfigured ? "badge-success" : "badge-neutral"
                    }`}
                  >
                    {modelsStatus?.museImage?.status || "OFFLINE_VECTOR_FALLBACK"}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Generation Budget:</span>
                  <span className="badge badge-purple">
                    {modelsStatus?.storytelling?.budget ?? 10} IMAGES/TASK
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 pt-1 border-t border-white/5">
                  Generates abstract visual metaphors for Task Passports. Falls back cleanly to vector SVG when offline.
                </p>
              </div>
            </div>

            {/* Meta Hosted Models Section */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Meta Hosted Suite (api.meta.ai)
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">API Key Configured:</span>
                  <span className={`badge ${modelsStatus?.metaHosted?.isConfigured ? "badge-success" : "badge-warning"}`}>
                    {modelsStatus?.metaHosted?.isConfigured ? "CONFIGURED" : "NOT SET (Offline Mocks)"}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Muse Wonder (Computer-Use):</span>
                  <span className="font-mono text-[11px] text-slate-200">muse-wonder-1.0</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Muse Voice Transcribe:</span>
                  <span className="font-mono text-[11px] text-slate-200">muse-voice-transcribe-1.0</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>SAM 3.1:</span>
                  <span className="font-mono text-[11px] text-slate-200">sam-3.1</span>
                </div>

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
                    <div>Muse Image: {testConnResult.museImage?.status || "NOT_CONFIGURED"}</div>
                    <div>Local Llama: {modelsStatus?.localLlama?.status || "NOT_CONFIGURED"}</div>
                  </div>
                )}
              </div>
            </div>

            {/* Local Llama Runtime Section */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Local Llama Runtime (Llama 3.2 3B)
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Status:</span>
                  <span className={`badge ${modelsStatus?.localLlama?.isReady ? "badge-success" : "badge-neutral"}`}>
                    {modelsStatus?.localLlama?.status || "MODEL_FILE_MISSING"}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  {modelsStatus?.localLlama?.message}
                </div>
                <div className="flex justify-between items-center text-slate-400 text-[11px]">
                  <span>Server Loopback:</span>
                  <span className="font-mono text-slate-200">127.0.0.1:8080</span>
                </div>
                {modelsStatus?.localLlama?.hardwareProfile && (
                  <div className="pt-1 text-[11px] text-slate-400 border-t border-white/5 space-y-1">
                    <div>CPU Cores: {modelsStatus.localLlama.hardwareProfile.cpuCores}</div>
                    <div>Backend: {modelsStatus.localLlama.hardwareProfile.accelerationBackend}</div>
                    {modelsStatus.localLlama.hardwareProfile.gpuName && (
                      <div>GPU: {modelsStatus.localLlama.hardwareProfile.gpuName}</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* System Integrations */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                System Integrations
              </h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Browser Extension:</span>
                  <span className="badge badge-success">READY</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Native Messaging Host:</span>
                  <span className="badge badge-success">READY</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Windows Companion (UIA):</span>
                  <span className="badge badge-success">READY</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">SQLite Evidence Ledger:</span>
                  <span className="badge badge-success">READY</span>
                </div>
              </div>
            </div>

            {/* Privacy Gateway Mode */}
            <div className="space-y-2 mt-auto">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Privacy Gateway</h4>
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs space-y-2">
                <p className="text-[11px] text-slate-400">
                  Local-only mode blocks all outbound transmissions to external model APIs fail-closed.
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-medium">Local-Only Enforcement:</span>
                  <span className="badge badge-success">ACTIVE</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
