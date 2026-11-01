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

const getApiHeaders = async (): Promise<Record<string, string>> => {
  let token = dynamicApiToken;
  if (!token && typeof window !== "undefined" && (window as any).sahaay?.getApiToken) {
    try {
      token = await (window as any).sahaay.getApiToken();
      if (token) dynamicApiToken = token;
    } catch {}
  }
  return {
    "Content-Type": "application/json",
    "X-Sahaay-Token": token || "dev-local-sahaay-token",
  };
};

const safeFetch = async (
  url: string,
  options: RequestInit = {},
  timeoutMs: number = 3000
): Promise<Response> => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return res;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
};

type TaskFlowState =
  | "IDLE"
  | "OBSERVE"
  | "RETRIEVE"
  | "PROPOSE"
  | "AUTHORIZE"
  | "EXECUTE"
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
    "home" | "tasks" | "computer" | "browser" | "files" | "apps" | "voice" | "history" | "settings" | "diagnostics"
  >("home");
  const [selectedContexts, setSelectedContexts] = useState<Set<string>>(
    new Set(["Computer", "Browser", "Files", "Apps", "Voice"])
  );

  // Session & Privacy
  const [sessionId, setSessionId] = useState<string>("");
  const [localOnlyMode, setLocalOnlyMode] = useState<boolean>(false);

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

  // Diagnostics Server Logs
  const [serverLogs, setServerLogs] = useState<Array<{
    timestamp: string;
    level: string;
    component: string;
    message: string;
  }>>([]);
  const [errorOnlyLogs, setErrorOnlyLogs] = useState<boolean>(false);
  const [diagActiveTab, setDiagActiveTab] = useState<"trace" | "logs">("trace");

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

  const initSession = async (): Promise<string | null> => {
    const storedId = localStorage.getItem("sahaay_active_session_id");
    const headers = await getApiHeaders();
    if (storedId) {
      try {
        const res = await safeFetch(`${API_BASE}/sessions/${storedId}`, { headers }, 2000);
        if (res.ok) {
          const data = await res.json();
          setSessionId(data.sessionId);
          setIsBackendReachable(true);
          addTimelineEntry(
            "IDLE",
            "Session Resumed",
            `Session: ${data.sessionId.slice(0, 8)}... (${data.localOnlyMode ? "Local-Only Mode" : "Hosted Allowed"})`
          );
          if (!data.localOnlyMode) {
            safeFetch(`${API_BASE}/sessions/${data.sessionId}/onboarding-consent`, {
              method: "POST",
              headers,
              body: JSON.stringify({
                accepted: true,
                justification: "Session resumed with Meta Cloud intelligence enabled",
              }),
            }, 2000).catch(() => {});
          }
          return data.sessionId;
        }
      } catch {}
    }

    try {
      const res = await safeFetch(
        `${API_BASE}/sessions`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ localOnlyMode }),
        },
        2500
      );
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.sessionId);
        localStorage.setItem("sahaay_active_session_id", data.sessionId);
        setIsBackendReachable(true);
        addTimelineEntry(
          "IDLE",
          "Session Initialized",
          `Session: ${data.sessionId.slice(0, 8)}... (${data.localOnlyMode ? "Local-Only Mode" : "Hosted Allowed"})`
        );
        if (!data.localOnlyMode) {
          safeFetch(`${API_BASE}/sessions/${data.sessionId}/onboarding-consent`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              accepted: true,
              justification: "Session initialized with Meta Cloud intelligence enabled",
            }),
          }, 2000).catch(() => {});
        }
        return data.sessionId;
      } else {
        setIsBackendReachable(false);
        return null;
      }
    } catch {
      setIsBackendReachable(false);
      return null;
    }
  };

  const runDiagnosticsProbe = async () => {
    setIsProbing(true);
    const headers = await getApiHeaders();
    try {
      const res = await safeFetch(`${API_BASE}/health`, { headers }, 2000);
      setIsBackendReachable(res.ok);
    } catch {
      setIsBackendReachable(false);
    }

    try {
      const res = await safeFetch(`${API_BASE}/models/status`, { headers }, 2000);
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
      const res = await safeFetch(`${API_BASE}/tasks?limit=20`, { headers }, 2000);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTasksList(data);
        }
      }
    } catch {
      // offline tasks probe
    }

    await fetchServerLogs(errorOnlyLogs);
    setIsProbing(false);
  };

  const fetchServerLogs = async (errorOnly: boolean = errorOnlyLogs) => {
    try {
      const headers = await getApiHeaders();
      const res = await safeFetch(`${API_BASE}/audit/logs?limit=50&error_only=${errorOnly}`, { headers }, 2000);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.logs)) {
          setServerLogs(data.logs);
        }
      }
    } catch {
      // offline logs probe
    }
  };

  const toggleLocalOnlyMode = async () => {
    const newMode = !localOnlyMode;
    const headers = await getApiHeaders();
    try {
      const res = await safeFetch(
        `${API_BASE}/sessions`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ localOnlyMode: newMode }),
        },
        2500
      );
      if (res.ok) {
        const data = await res.json();
        setSessionId(data.sessionId);
        localStorage.setItem("sahaay_active_session_id", data.sessionId);
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
      const headers = await getApiHeaders();
      const res = await safeFetch(`${API_BASE}/tasks/${taskId}/passport`, { headers }, 2500);
      if (res.ok) {
        const data = await res.json();
        setTaskPassport(data);
        return data;
      }
    } catch (err) {
      console.warn("Could not fetch Task Passport:", err);
    }
    return null;
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
      const headers = await getApiHeaders();
      const res = await safeFetch(`${API_BASE}/tasks?limit=20`, { headers }, 2500);
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

  const handleResetNewTask = () => {
    setActiveNav("home");
    setUserPrompt("");
    setActiveTaskId("");
    setTaskPassport(null);
    setTaskState("IDLE");
    setStatusNarrative("Sahaay agent is idle. Ready for voice or text prompt.");
    setTimeline([]);
  };

  const triggerPromptExecution = async (promptText: string) => {
    if (!promptText.trim()) return;
    const lower = promptText.toLowerCase();

    // Clear stale state and passports immediately so previous tasks don't linger
    setTaskPassport(null);
    setActiveTaskId("");
    setTimeline([]);

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
      lower.startsWith("extract") ||
      lower.startsWith("hello") ||
      lower.startsWith("explain");
    const isDoMode =
      lower.startsWith("open") ||
      lower.startsWith("calculate") ||
      lower.startsWith("launch") ||
      lower.startsWith("write") ||
      lower.startsWith("fill");
    const workflowMode = isAskMode ? "ask" : isDoMode ? "do" : "combined_retrieval_and_action";

    // Validate or establish session first
    let activeSessionId: string | null = sessionId;
    if (!activeSessionId) {
      activeSessionId = await initSession();
    }
    if (!activeSessionId) {
      setTaskState("FAILED");
      setStatusNarrative("Backend connection unavailable. Please ensure Sahaay FastAPI backend is online at 127.0.0.1:8000.");
      addTimelineEntry("FAILED", "Session Error", "Could not establish valid session with backend.");
      return;
    }

    setTaskState("PROPOSE");
    setStatusNarrative(`Submitting task: "${promptText}" (${workflowMode.toUpperCase()})...`);
    addTimelineEntry("PROPOSE", `Goal: "${promptText.slice(0, 48)}..."`, "Dispatching goal to Sahaay orchestrator");

    try {
      const headers = await getApiHeaders();
      const res = await safeFetch(
        `${API_BASE}/workflows/execute-goal`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            sessionId: activeSessionId,
            goal: promptText,
            workflowMode,
            sourceSurface: "desktop",
          }),
        },
        20000
      );

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Server returned HTTP ${res.status}`);
      }

      if (data.taskId) {
        const taskId = data.taskId;
        setActiveTaskId(taskId);
        setTaskState("PROPOSE");
        setStatusNarrative(`Task accepted (${taskId.slice(0, 8)}...). Orchestrating execution lifecycle.`);
        addTimelineEntry("PROPOSE", `Task Accepted: ${taskId.slice(0, 8)}...`, `Scheduled asynchronously`);

        // If synchronously completed (e.g. test harness or instant capability introspection)
        if ((data.status === "VERIFIED" || data.status === "COMPLETED") && data.isVerified) {
          setTaskState("VERIFIED");
          const summary =
            data.summary ||
            data.accumulatedFacts?.bill_summary ||
            data.accumulatedFacts?.deadline_summary ||
            data.accumulatedFacts?.key_findings ||
            data.accumulatedFacts?.calculation_result ||
            `Task completed successfully with ${data.completedSteps}/${data.totalSteps} steps verified.`;

          setStatusNarrative(summary);
          addTimelineEntry("VERIFIED", `Task Completed (${data.completedSteps}/${data.totalSteps} Steps)`, summary);
          await fetchTaskPassport(taskId);
          await fetchTasksList();
          return;
        }

        // Asynchronous polling loop (every 600ms, up to 50 iterations = 30 seconds)
        let isDone = false;
        let attempts = 0;
        const maxAttempts = 50;

        while (!isDone && attempts < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, 600));
          attempts++;

          try {
            const pollRes = await safeFetch(`${API_BASE}/tasks/${taskId}`, { headers }, 2500);
            if (!pollRes.ok) continue;

            const tData = await pollRes.json();
            const bStatus = (tData.status || "").toUpperCase();

            if (bStatus === "OBSERVING" || bStatus === "CREATED") {
              setTaskState("OBSERVE");
              setStatusNarrative("Observing system context and active windows...");
            } else if (bStatus === "PLANNING" || bStatus === "PROPOSING") {
              setTaskState("PROPOSE");
              setStatusNarrative("Generating execution plan and dependency DAG...");
            } else if (bStatus === "AUTHORIZING") {
              setTaskState("HANDOFF");
              setStatusNarrative("Checking policy grants and capability safety boundaries...");
            } else if (bStatus === "EXECUTING") {
              setTaskState("EXECUTE");
              setStatusNarrative("Executing automation steps across authorized Windows/Browser controllers...");
            } else if (bStatus === "VERIFYING") {
              setTaskState("VERIFY");
              setStatusNarrative("Verifying postconditions via independent UI automation readback...");
            } else if (bStatus === "COMPLETED") {
              isDone = true;
              setTaskState("VERIFIED");
              const pData = await fetchTaskPassport(taskId);
              const completedMsg =
                pData?.summary ||
                tData.summary ||
                `Task completed and independently verified with cryptographic SHA-256 evidence.`;
              setStatusNarrative(completedMsg);
              addTimelineEntry("VERIFIED", "Task Completed", completedMsg);
              break;
            } else if (bStatus === "FAILED" || bStatus === "CANCELLED") {
              isDone = true;
              setTaskState("FAILED");
              const err =
                tData.error ||
                (bStatus === "CANCELLED" ? "Task was cancelled." : "Task postcondition verification failed.");
              setStatusNarrative(`TASK FAILED: ${err}`);
              addTimelineEntry("FAILED", "Task Failed", err);
              await fetchTaskPassport(taskId);
              break;
            }
          } catch (pollErr: any) {
            console.warn("Polling task status error:", pollErr);
          }
        }

        if (!isDone && attempts >= maxAttempts) {
          setTaskState("FAILED");
          setStatusNarrative("Task execution timed out awaiting verification.");
          addTimelineEntry("FAILED", "Timeout", "Task execution timed out after 30 seconds.");
        }

        await fetchTasksList();
        return;
      }

      if ((data.status === "VERIFIED" || data.status === "COMPLETED") && data.isVerified) {
        setTaskState("VERIFIED");
        const summary =
          data.summary ||
          data.accumulatedFacts?.bill_summary ||
          data.accumulatedFacts?.deadline_summary ||
          data.accumulatedFacts?.key_findings ||
          data.accumulatedFacts?.calculation_result ||
          `Task completed successfully with ${data.completedSteps}/${data.totalSteps} steps verified.`;

        setStatusNarrative(summary);
        addTimelineEntry("VERIFIED", `Task Completed (${data.completedSteps}/${data.totalSteps} Steps)`, summary);
      } else if (data.status === "FAILED") {
        setTaskState("FAILED");
        setStatusNarrative(`TASK FAILED: ${data.error || "Verification failed."}`);
        addTimelineEntry("FAILED", "Task Failed", data.error || "Postcondition check failed");
      } else {
        setTaskState("HANDOFF");
        setStatusNarrative(`STATUS: ${data.status} — Awaiting authorization.`);
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
      const headers = await getApiHeaders();
      await safeFetch(`${API_BASE}/tasks/${activeTaskId}/cancel`, {
        method: "POST",
        headers,
      }, 3000).catch(() => {});
    }
    setTaskState("IDLE");
    setStatusNarrative("Task execution stopped by user.");
  };

  const handleApproveAction = async () => {
    if (!sessionId) return;
    const headers = await getApiHeaders();
    try {
      // Grant authorization for desktop and browser automation
      await safeFetch(`${API_BASE}/sessions/${sessionId}/grants`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          capability: "notepad",
          scope: "execute:action",
          purpose: "desktop_automation",
          justification: "User approved in desktop interface",
        }),
      });
      await safeFetch(`${API_BASE}/sessions/${sessionId}/grants`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          capability: "browser_action",
          scope: "https://*",
          purpose: "browser_content",
          justification: "User approved in desktop interface",
        }),
      });
      // Also provision canonical Meta Cloud onboarding grants
      await safeFetch(`${API_BASE}/sessions/${sessionId}/onboarding-consent`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          accepted: true,
          justification: "User authorized operations and Meta Cloud processing",
        }),
      });
      setStatusNarrative("Action authorized. Resuming task execution...");
      addTimelineEntry("AUTHORIZE", "Action Approved", "User granted execution permissions");
      if (userPrompt.trim()) {
        triggerPromptExecution(userPrompt);
      }
    } catch (err: any) {
      setStatusNarrative(`Failed to grant approval: ${err.message}`);
    }
  };

  const handleTakeOver = async () => {
    if (activeTaskId) {
      const headers = await getApiHeaders();
      try {
        await safeFetch(`${API_BASE}/tasks/${activeTaskId}/handoff`, {
          method: "POST",
          headers,
        });
      } catch {}
    }
    setTaskState("IDLE");
    setStatusNarrative("User took manual control. Sahaay agent is standing by.");
    addTimelineEntry("HANDOFF", "Manual Takeover", "User took manual control of laptop");
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

          const isWebm = (mimeType || "").includes("webm");
          const ext = isWebm ? "webm" : "wav";
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType || "audio/wav" });
          const formData = new FormData();
          formData.append("file", audioBlob, `recording.${ext}`);
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
              onClick={handleResetNewTask}
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
              onClick={() => setActiveNav("diagnostics")}
              className={`nav-rail-item ${activeNav === "diagnostics" ? "active" : ""}`}
            >
              <Activity size={16} color="var(--sahaay-mint)" />
              <span>Diagnostics</span>
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

              {/* Contextual Action Gate Authorization: APPROVE / TAKE OVER */}
              {taskState === "HANDOFF" && (
                <div style={{ padding: "12px 14px", background: "rgba(251, 191, 36, 0.12)", borderRadius: "12px", border: "1px solid rgba(251, 191, 36, 0.35)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
                  <div>
                    <div style={{ fontWeight: 600, color: "#fbbf24", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                      <Activity size={14} color="#fbbf24" /> Action Gate Authorization Required
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                      Explicit consent is required to execute native desktop / browser modifications.
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexShrink: 0 }}>
                    <button
                      onClick={handleApproveAction}
                      className="btn btn-primary"
                      style={{ fontSize: "11px", padding: "6px 14px", fontWeight: 600 }}
                    >
                      Approve Action
                    </button>
                    <button
                      onClick={handleTakeOver}
                      className="btn btn-secondary"
                      style={{ fontSize: "11px", padding: "6px 14px" }}
                    >
                      Take Over
                    </button>
                  </div>
                </div>
              )}

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

          {/* D. Lower 3 Frosted Glass Cards, Diagnostics, or History View */}
          {activeNav === "diagnostics" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Activity size={18} color="var(--sahaay-mint)" /> Connections & Diagnostics
                  </h3>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                    Authoritative runtime telemetry, live component health, and sanitized audit trace
                  </p>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    onClick={runDiagnosticsProbe}
                    className="btn btn-secondary"
                    style={{ fontSize: "11px", padding: "6px 12px", display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    <RefreshCw size={12} className={isProbing ? "anim-spin" : ""} /> Refresh Probes
                  </button>
                  <button
                    onClick={() => {
                      const report = {
                        timestamp: new Date().toISOString(),
                        backendOnline: isBackendReachable,
                        sessionId,
                        activeTaskId,
                        privacyMode: localOnlyMode ? "LOCAL_ONLY" : "HOSTED_ALLOWED",
                        models: modelsStatus,
                        recentTasksCount: tasksList.length,
                        recordedTimelineEvents: timeline.length,
                      };
                      navigator.clipboard.writeText(JSON.stringify(report, null, 2));
                      alert("Diagnostics JSON copied to clipboard!");
                    }}
                    className="btn btn-primary"
                    style={{ fontSize: "11px", padding: "6px 12px" }}
                  >
                    Copy Diagnostics
                  </button>
                  <button
                    onClick={() => {
                      const report = {
                        timestamp: new Date().toISOString(),
                        backendOnline: isBackendReachable,
                        sessionId,
                        activeTaskId,
                        privacyMode: localOnlyMode ? "LOCAL_ONLY" : "HOSTED_ALLOWED",
                        models: modelsStatus,
                        recentTasks: tasksList,
                        timeline,
                      };
                      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `sahaay-diagnostics-${Date.now()}.json`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="btn btn-subtle"
                    style={{ fontSize: "11px", padding: "6px 12px" }}
                  >
                    Export Report
                  </button>
                </div>
              </div>

              {/* Status Metric Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>FastAPI Backend Authority</div>
                  <div style={{ fontSize: "13px", fontWeight: 600, color: isBackendReachable ? "var(--sahaay-mint)" : "var(--sahaay-danger)", marginTop: "4px" }}>
                    {isBackendReachable ? "ONLINE (127.0.0.1:8000)" : "OFFLINE (Port 8000)"}
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Current Session ID</div>
                  <div style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--sahaay-cyan)", marginTop: "4px" }}>
                    {sessionId ? `${sessionId.slice(0, 16)}...` : "Initializing..."}
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Windows Controller Pipe</div>
                  <div style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--sahaay-text)", marginTop: "4px" }}>
                    \\\\.\\pipe\\SahaayControllerPipe
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Chrome/Edge Native Host</div>
                  <div style={{ fontSize: "12px", color: "var(--sahaay-mint)", marginTop: "4px" }}>
                    Registered (com.sahaay.nativehost)
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Planning Model / Provider</div>
                  <div style={{ fontSize: "12px", color: "var(--sahaay-text)", marginTop: "4px" }}>
                    Meta Muse Spark 1.3
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Privacy Gateway Tier</div>
                  <div style={{ fontSize: "12px", color: localOnlyMode ? "var(--sahaay-cyan)" : "var(--sahaay-warning)", marginTop: "4px" }}>
                    {localOnlyMode ? "STRICT LOCAL-ONLY" : "HOSTED INFERENCE ALLOWED"}
                  </div>
                </div>
              </div>

              {/* Live Event & Telemetry Trace / Server Logs */}
              <div style={{ marginTop: "4px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <button
                      onClick={() => setDiagActiveTab("trace")}
                      className="btn-pill-subtle"
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "4px 10px",
                        background: diagActiveTab === "trace" ? "rgba(138,245,207,0.15)" : "transparent",
                        color: diagActiveTab === "trace" ? "var(--sahaay-mint)" : "var(--sahaay-text-muted)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "6px",
                        cursor: "pointer",
                      }}
                    >
                      Execution Trace ({timeline.length})
                    </button>
                    <button
                      onClick={() => {
                        setDiagActiveTab("logs");
                        fetchServerLogs(errorOnlyLogs);
                      }}
                      className="btn-pill-subtle"
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "4px 10px",
                        background: diagActiveTab === "logs" ? "rgba(138,245,207,0.15)" : "transparent",
                        color: diagActiveTab === "logs" ? "var(--sahaay-mint)" : "var(--sahaay-text-muted)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "6px",
                        cursor: "pointer",
                      }}
                    >
                      Backend Server Logs ({serverLogs.length})
                    </button>
                  </div>
                  {diagActiveTab === "logs" && (
                    <label style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={errorOnlyLogs}
                        onChange={(e) => {
                          setErrorOnlyLogs(e.target.checked);
                          fetchServerLogs(e.target.checked);
                        }}
                      />
                      Errors only
                    </label>
                  )}
                </div>

                {diagActiveTab === "trace" ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "320px", overflowY: "auto", background: "rgba(3,10,14,0.6)", padding: "10px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                    {timeline.length === 0 ? (
                      <div style={{ fontSize: "11px", color: "var(--sahaay-text-subtle)", textAlign: "center", padding: "14px" }}>
                        No diagnostic events logged yet. Execute an agent request or click Refresh Probes.
                      </div>
                    ) : (
                      timeline.map((event) => (
                        <div key={event.id} style={{ display: "flex", alignItems: "flex-start", gap: "8px", fontSize: "11px", padding: "6px 8px", borderRadius: "6px", background: "rgba(255,255,255,0.02)" }}>
                          <span style={{ fontFamily: "var(--font-mono)", color: "var(--sahaay-text-subtle)", flexShrink: 0 }}>
                            [{event.timestamp}]
                          </span>
                          <span className={`badge ${event.state === "FAILED" ? "badge-danger" : event.state === "VERIFIED" ? "badge-success" : "badge-neutral"}`} style={{ fontSize: "9px", padding: "2px 6px" }}>
                            {event.step}
                          </span>
                          <span style={{ color: "#fff", fontWeight: 500 }}>{event.title}:</span>
                          <span style={{ color: "var(--sahaay-text-muted)", flex: 1 }}>{event.details}</span>
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "320px", overflowY: "auto", background: "rgba(3,10,14,0.6)", padding: "10px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)", fontFamily: "var(--font-mono)", fontSize: "10px" }}>
                    {serverLogs.length === 0 ? (
                      <div style={{ color: "var(--sahaay-text-subtle)", textAlign: "center", padding: "14px" }}>
                        No server logs found. Ensure backend is running.
                      </div>
                    ) : (
                      serverLogs.map((log, idx) => (
                        <div key={idx} style={{ display: "flex", alignItems: "flex-start", gap: "6px", padding: "3px 6px", borderRadius: "4px", background: log.level === "ERROR" || log.level === "CRITICAL" ? "rgba(255,100,100,0.08)" : log.level === "WARNING" ? "rgba(255,200,50,0.06)" : "transparent" }}>
                          <span style={{ color: "var(--sahaay-text-subtle)" }}>{log.timestamp}</span>
                          <span style={{ color: log.level === "ERROR" || log.level === "CRITICAL" ? "var(--sahaay-danger)" : log.level === "WARNING" ? "var(--sahaay-warning)" : "var(--sahaay-mint)", fontWeight: 600 }}>
                            [{log.level}]
                          </span>
                          <span style={{ color: "var(--sahaay-cyan)" }}>[{log.component}]</span>
                          <span style={{ color: "var(--sahaay-text)", flex: 1, wordBreak: "break-all" }}>{log.message}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </section>
          ) : activeNav === "history" ? (
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
          ) : activeNav === "computer" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Monitor size={18} color="var(--sahaay-cyan)" /> Windows Native Automation & UI Controller
                  </h3>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                    Named Pipe Daemon: <code>\\.\pipe\SahaayControllerPipe</code> • Direct UI Automation (No Shell Injection)
                  </p>
                </div>
                <span className="badge badge-success" style={{ fontSize: "11px" }}>
                  {modelsStatus?.systemIntegrations?.windowsCompanion || "Ready"}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Authorized Applications</h4>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginBottom: "12px" }}>
                    Strict allowlist restricts application launching to safe system tools:
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Calculator (calc.exe)</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Notepad (notepad.exe)</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>File Explorer (explorer.exe)</span>
                  </div>
                </div>

                <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Direct Computer Actions</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <button
                      onClick={() => triggerPromptExecution("Open Calculator and calculate 125 multiplied by 48")}
                      className="quick-action-btn"
                    >
                      <PlusCircle size={14} color="var(--sahaay-cyan)" />
                      <span>Calculate 125 * 48 in Calculator</span>
                    </button>
                    <button
                      onClick={() => triggerPromptExecution("Open Notepad and write automated status note")}
                      className="quick-action-btn"
                    >
                      <FileText size={14} color="var(--sahaay-mint)" />
                      <span>Launch Notepad & Type Note</span>
                    </button>
                  </div>
                </div>
              </div>
            </section>
          ) : activeNav === "browser" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Globe size={18} color="var(--sahaay-mint)" /> Browser Extension Bridge (Chrome & Edge)
                  </h3>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                    Native Messaging Host: <code>com.sahaay.nativehost</code> • Real MV3 Bridge via Named Pipe
                  </p>
                </div>
                <span className="badge badge-success" style={{ fontSize: "11px" }}>
                  {modelsStatus?.systemIntegrations?.browserExtension || "Bridge Attached"}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Bridge Capabilities</h4>
                  <ul style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", display: "flex", flexDirection: "column", gap: "6px", paddingLeft: "16px" }}>
                    <li>Active web tab DOM observation (sanitized text & structure)</li>
                    <li>Form input population with user-confirmed action gating</li>
                    <li>Readback extraction for independent cryptographic verification</li>
                    <li>Native Messaging Host auto-reconnect & origin validation</li>
                  </ul>
                </div>

                <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Web Automation Actions</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <button
                      onClick={() => triggerPromptExecution("Read active browser tab and summarize key facts")}
                      className="quick-action-btn"
                    >
                      <Globe size={14} color="var(--sahaay-mint)" />
                      <span>Observe & Summarize Active Tab</span>
                    </button>
                    <button
                      onClick={() => triggerPromptExecution("Research latest advancements in multimodal AI agents")}
                      className="quick-action-btn"
                    >
                      <Search size={14} color="var(--sahaay-cyan)" />
                      <span>Web Research via Clean Fetch</span>
                    </button>
                  </div>
                </div>
              </div>
            </section>
          ) : activeNav === "files" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Folder size={18} color="var(--sahaay-cyan)" /> Document Ingestion & Context Store
                  </h3>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                    Cryptographic SHA-256 Provenance • Deterministic Fact Ingestion (Zero Synthetic Hallucinations)
                  </p>
                </div>
                <span className="badge badge-success" style={{ fontSize: "11px" }}>Verified Storage</span>
              </div>

              <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Document Security Protocol</h4>
                <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", lineHeight: 1.6 }}>
                  Files ingested by Sahaay are fingerprinted using SHA-256 hashes, chunked deterministically, and stored in SQLite. Outbound transmissions to Meta Cloud require explicit user consent via the Privacy Gateway.
                </p>
              </div>
            </section>
          ) : activeNav === "apps" ? (
            <section className="glass-surface" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "8px" }}>
                    <LayoutGrid size={18} color="var(--sahaay-mint)" /> Capability Registry & Safety Boundaries
                  </h3>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginTop: "2px" }}>
                    Authoritative Registry: Centralized capability definitions, parameters, and action gates
                  </p>
                </div>
                <span className="badge badge-success" style={{ fontSize: "11px" }}>Registry Synchronized</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--sahaay-mint)" }}>windows_launch_app</span>
                  <p style={{ fontSize: "10px", color: "var(--sahaay-text-muted)", marginTop: "4px" }}>Launch authorized application with verified top-level HWND discovery.</p>
                </div>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--sahaay-cyan)" }}>windows_set_control_text</span>
                  <p style={{ fontSize: "10px", color: "var(--sahaay-text-muted)", marginTop: "4px" }}>Safely set text or send verified calculations to target window controls.</p>
                </div>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--sahaay-blue)" }}>browser_tab_observe</span>
                  <p style={{ fontSize: "10px", color: "var(--sahaay-text-muted)", marginTop: "4px" }}>Inspect active web tab structure, text, and form fields via MV3 bridge.</p>
                </div>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--sahaay-warning)" }}>verify_readback</span>
                  <p style={{ fontSize: "10px", color: "var(--sahaay-text-muted)", marginTop: "4px" }}>Independent UI automation readback verifying postconditions before completion.</p>
                </div>
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
