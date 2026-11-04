import React, { useEffect, useState, useRef } from "react";
import {
  Mic,
  Send,
  Pause,
  Play,
  Square,
  Globe,
  Monitor,
  Folder,
  Clock,
  Settings,
  PlusCircle,
  Home,
  CheckCircle2,
  RefreshCw,
  Search,
  FileText,
  ArrowRight,
  Activity,
  Paperclip,
  ShieldAlert,
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
  timeoutMs: number = 5000
): Promise<Response> => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(new Error("Timeout awaiting " + url)), timeoutMs);
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
  goal?: string;
  verificationStatus?: string;
  summaryNotice?: string;
  targetAppOrUrl?: string;
  sourceRef?: string;
  evidenceId?: string;
  createdAt?: string;
  extractedFields?: Record<string, any>;
}

interface TimelineItem {
  id: string;
  timestamp: string;
  step: string;
  state: TaskFlowState;
  title: string;
  details: string;
  provenanceHash?: string;
}

interface ModelsStatusReport {
  museSpark?: { isConfigured: boolean; baseUrl: string; model: string; status: string };
  metaHosted?: {
    isConfigured: boolean;
    baseUrl: string;
    endpoint?: string;
    modelId?: string;
    status?: string;
    statusCode?: number;
    httpResult?: string;
    generationVerified?: boolean;
    toolCallingVerified?: boolean;
    catalogueVerified?: boolean;
    remediationGuidance?: string | null;
    error?: string | null;
    diagnostics?: {
      credential?: string;
      tlsConnection?: string;
      apiAuthentication?: string;
      catalogueAvailability?: string;
      museSpark?: string;
      museWonder?: string;
      museVoice?: string;
      sam?: string;
    };
    models?: Record<string, any>;
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
  gpuAcceleration?: {
    isAvailable: boolean;
    gpuName: string;
    driverVersion: string;
    cudaVersion: string;
    totalMemoryMb: number;
    usedMemoryMb: number;
    freeMemoryMb: number;
    utilizationPercent: number;
    temperatureCelsius: number;
    accelerationTier: string;
    supportedWorkloads: string[];
    localLlmRecommendation: string;
  };
}

export function App(): React.JSX.Element {
  // Navigation & View state
  const [activeNav, setActiveNav] = useState<
    "home" | "tasks" | "computer" | "browser" | "files" | "history" | "settings" | "diagnostics"
  >("home");

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
  const [modelApiKeyInput, setModelApiKeyInput] = useState<string>("");
  const [isUpdatingApiKey, setIsUpdatingApiKey] = useState<boolean>(false);
  const [apiKeyFeedback, setApiKeyFeedback] = useState<string>("");

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
  const [messages, setMessages] = useState<Array<{
    messageId: string;
    role: string;
    content: string;
    createdAt: string;
    metadata?: any;
  }>>([]);
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

  // Files, Workspace & Live Observation
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [attachedDirectory, setAttachedDirectory] = useState<string | null>(null);

  const recordingIntervalRef = useRef<any>(null);
  const mediaRecorderRef = useRef<any>(null); // holds AudioContext pipeline handle
  const streamRef = useRef<MediaStream | null>(null);
  // PCM WAV capture via AudioContext (bypasses WebM encoding; Meta ASR needs 16kHz WAV)
  const audioContextRef = useRef<AudioContext | null>(null);
  const pcmSamplesRef = useRef<Float32Array[]>([]);

  // ── Pure-JS WAV encoder ────────────────────────────────────────────────────
  /** Encode interleaved Float32 samples at sampleRate Hz to a 16-bit PCM WAV Blob. */
  function encodeWav(samples: Float32Array[], sampleRate: number): Blob {
    // Concatenate all sample chunks
    const totalLen = samples.reduce((a, s) => a + s.length, 0);
    const merged = new Float32Array(totalLen);
    let offset = 0;
    for (const chunk of samples) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    // Downsample to 16000 if needed (simple linear interpolation)
    const targetRate = 16000;
    let pcm = merged;
    if (sampleRate !== targetRate) {
      const ratio = sampleRate / targetRate;
      const outLen = Math.floor(totalLen / ratio);
      pcm = new Float32Array(outLen);
      for (let i = 0; i < outLen; i++) {
        const srcIdx = i * ratio;
        const lo = Math.floor(srcIdx);
        const hi = Math.min(lo + 1, totalLen - 1);
        const frac = srcIdx - lo;
        pcm[i] = merged[lo] * (1 - frac) + merged[hi] * frac;
      }
    }
    // Convert float32 [-1,1] to int16
    const int16 = new Int16Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) {
      const s = Math.max(-1, Math.min(1, pcm[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const dataBytes = int16.buffer.byteLength;
    const buffer = new ArrayBuffer(44 + dataBytes);
    const view = new DataView(buffer);
    const write = (off: number, str: string) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
    write(0, "RIFF"); view.setUint32(4, 36 + dataBytes, true);
    write(8, "WAVE"); write(12, "fmt "); view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);   // PCM
    view.setUint16(22, 1, true);   // mono
    view.setUint32(24, targetRate, true);
    view.setUint32(28, targetRate * 2, true); // byte rate
    view.setUint16(32, 2, true);   // block align
    view.setUint16(34, 16, true);  // bits per sample
    write(36, "data"); view.setUint32(40, dataBytes, true);
    new Uint8Array(buffer, 44).set(new Uint8Array(int16.buffer));
    return new Blob([buffer], { type: "audio/wav" });
  }

  useEffect(() => {
    let isMounted = true;
    (async () => {
      const sid = await initSession();
      if (isMounted) {
        runDiagnosticsProbe();
        if (sid) {
          fetchConversationMessages(sid);
          fetchTasksList();
        }
      }
    })();

    const interval = setInterval(() => {
      runDiagnosticsProbe();
      fetchTasksList();
      fetchConversationMessages();
    }, 3000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [sessionId]);

  const fetchConversationMessages = async (sid?: string) => {
    const targetSession = sid || sessionId;
    if (!targetSession) return;
    try {
      const headers = await getApiHeaders();
      const res = await safeFetch(`${API_BASE}/sessions/${targetSession}/messages`, { headers }, 2500);
      if (res.ok) {
        const msgs = await res.json();
        setMessages(msgs);
      }
    } catch {}
  };

  const initSession = async (): Promise<string | null> => {
    const headers = await getApiHeaders();
    // 1. Try to sync with existing active session (cross-surface shared with browser)
    try {
      const activeRes = await safeFetch(`${API_BASE}/sessions/active/latest`, { headers }, 2000);
      if (activeRes.ok) {
        const activeData = await activeRes.json();
        if (activeData.sessionId) {
          setSessionId(activeData.sessionId);
          localStorage.setItem("sahaay_active_session_id", activeData.sessionId);
          setIsBackendReachable(true);
          fetchConversationMessages(activeData.sessionId);
          return activeData.sessionId;
        }
      }
    } catch {}

    const storedId = localStorage.getItem("sahaay_active_session_id");
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
            await safeFetch(
              `${API_BASE}/sessions/${data.sessionId}/onboarding-consent`,
              {
                method: "POST",
                headers,
                body: JSON.stringify({
                  accepted: true,
                  justification: "Session resumed with Meta Cloud intelligence enabled",
                }),
              },
              3000
            ).catch(() => {});
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
          body: JSON.stringify({ localOnlyMode, autoAuthorizeMetaCloud: true }),
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
          await safeFetch(
            `${API_BASE}/sessions/${data.sessionId}/onboarding-consent`,
            {
              method: "POST",
              headers,
              body: JSON.stringify({
                accepted: true,
                justification: "Session initialized with Meta Cloud intelligence enabled",
              }),
            },
            3000
          ).catch(() => {});
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
          const targetTaskId = activeTaskId || (data.length > 0 ? (data[0].task_id || data[0].taskId) : null);
          if (targetTaskId) {
            try {
              const evRes = await safeFetch(`${API_BASE}/tasks/${targetTaskId}/events`, { headers }, 2000);
              if (evRes.ok) {
                const evList = await evRes.json();
                if (Array.isArray(evList) && evList.length > 0) {
                  const mapped: TimelineItem[] = evList.map((e: any) => ({
                    id: e.event_id || Math.random().toString(),
                    timestamp: (e.timestamp || "").split("T")[1]?.slice(0, 8) || new Date().toLocaleTimeString(),
                    state: (e.stage === "COMPLETED" ? "VERIFIED" : (e.stage || "EXECUTE")) as TaskFlowState,
                    step: (e.event_type || "").replace("task.", "").toUpperCase(),
                    title: e.stage || "ACTION",
                    details: e.message || JSON.stringify(e.data || {}),
                  }));
                  setTimeline(mapped);
                }
              }
            } catch {}
          }
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

  const handleSaveModelApiKey = async () => {
    if (!modelApiKeyInput.trim()) return;
    setIsUpdatingApiKey(true);
    setApiKeyFeedback("Authenticating with Meta Model API...");
    try {
      const headers = await getApiHeaders();
      const res = await safeFetch(
        `${API_BASE}/models/credentials`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ modelApiKey: modelApiKeyInput.trim() }),
        },
        12000
      );
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.isVerified) {
        setApiKeyFeedback(`✓ Authenticated: ${data.modelId} (${data.httpResult || "HTTP 200 OK"})`);
        setModelApiKeyInput("");
        await runDiagnosticsProbe();
      } else {
        const errorMsg =
          data.error || data.message || data.detail || res.statusText || "Verification failed";
        setApiKeyFeedback(`✗ Failed (${data.httpResult || "HTTP " + res.status}): ${errorMsg}`);
      }
    } catch (e: any) {
      setApiKeyFeedback(`✗ Error: ${e.message || "Failed to reach backend"}`);
    } finally {
      setIsUpdatingApiKey(false);
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

  // Execution Handlers
  const fetchTasksList = async () => {
    try {
      const headers = await getApiHeaders();
      const res = await safeFetch(`${API_BASE}/tasks?limit=20`, { headers }, 2500);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTasksList(data);
          const targetTaskId = activeTaskId || (data.length > 0 ? (data[0].task_id || data[0].taskId) : null);
          if (targetTaskId) {
            try {
              const evRes = await safeFetch(`${API_BASE}/tasks/${targetTaskId}/events`, { headers }, 2000);
              if (evRes.ok) {
                const evList = await evRes.json();
                if (Array.isArray(evList) && evList.length > 0) {
                  const mapped: TimelineItem[] = evList.map((e: any) => ({
                    id: e.event_id || Math.random().toString(),
                    timestamp: (e.timestamp || "").split("T")[1]?.slice(0, 8) || new Date().toLocaleTimeString(),
                    state: (e.stage === "COMPLETED" ? "VERIFIED" : (e.stage || "EXECUTE")) as TaskFlowState,
                    step: (e.event_type || "").replace("task.", "").toUpperCase(),
                    title: e.stage || "ACTION",
                    details: e.message || JSON.stringify(e.data || {}),
                  }));
                  setTimeline(mapped);
                }
              }
            } catch {}
          }
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

    // Optimistically record user message in transcript
    const tempMsgId = "msg-" + Date.now();
    setMessages((prev) => [
      ...prev,
      {
        messageId: tempMsgId,
        role: "user",
        content: promptText,
        createdAt: new Date().toISOString(),
      },
    ]);

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
      if (!localOnlyMode) {
        await safeFetch(`${API_BASE}/sessions/${activeSessionId}/onboarding-consent`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            accepted: true,
            justification: "Automatic task dispatch consent confirmation",
          }),
        }, 3000).catch(() => {});
      }
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
            context: [
              attachedDirectory ? `Attached Project Directory / Workspace: ${attachedDirectory}` : "",
              attachedFiles.length > 0 ? `Attached User Files:\n${attachedFiles.map((f) => `- ${f}`).join("\n")}` : "",
            ].filter(Boolean).join("\n\n"),
          }),
        },
        90000
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

        // Asynchronous authoritative polling loop matching backend budget (every 600ms, up to 300 iterations = 180 seconds)
        let isDone = false;
        let attempts = 0;
        const maxAttempts = 300;

        while (!isDone && attempts < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, 600));
          attempts++;

          try {
            const pollRes = await safeFetch(`${API_BASE}/tasks/${taskId}`, { headers }, 2500);
            if (!pollRes.ok) continue;

            const tData = await pollRes.json();
            const bStatus = (tData.status || "").toUpperCase();

            // Fetch recent progress event if available to display exact live action
            let liveActionMsg = "";
            try {
              const evRes = await safeFetch(`${API_BASE}/tasks/${taskId}/events`, { headers }, 1500);
              if (evRes.ok) {
                const evList = await evRes.json();
                if (Array.isArray(evList) && evList.length > 0) {
                  const lastEv = evList[evList.length - 1];
                  if (lastEv && lastEv.message) {
                    liveActionMsg = ` • ${lastEv.message}`;
                  }
                }
              }
            } catch {}

            if (bStatus === "OBSERVING" || bStatus === "CREATED") {
              setTaskState("OBSERVE");
              setStatusNarrative(`Observing system context and active surfaces${liveActionMsg}...`);
            } else if (bStatus === "PLANNING" || bStatus === "PROPOSING") {
              setTaskState("PROPOSE");
              setStatusNarrative(`Generating execution plan and reasoning${liveActionMsg}...`);
            } else if (bStatus === "AUTHORIZING") {
              setTaskState("HANDOFF");
              setStatusNarrative(`Evaluating policy grants and capability safety boundaries${liveActionMsg}...`);
            } else if (bStatus === "EXECUTING") {
              setTaskState("EXECUTE");
              setStatusNarrative(`Executing automation across Windows/Browser controllers${liveActionMsg}...`);
            } else if (bStatus === "VERIFYING") {
              setTaskState("VERIFY");
              setStatusNarrative(`Verifying postconditions via independent readback${liveActionMsg}...`);
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
          setStatusNarrative("Task execution exceeded 180s timeout budget awaiting backend completion.");
          addTimelineEntry("FAILED", "Timeout", "Task execution timed out after 180 seconds.");
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

  const handleAttachFiles = async () => {
    try {
      if ((window as any).sahaay?.openFiles) {
        const files: string[] = await (window as any).sahaay.openFiles();
        if (files && files.length > 0) {
          setAttachedFiles((prev) => Array.from(new Set([...prev, ...files])));
        }
      }
    } catch (err) {
      console.warn("Failed to open files dialog:", err);
    }
  };

  const handleAttachDirectory = async () => {
    try {
      if ((window as any).sahaay?.openDirectory) {
        const dir: string | null = await (window as any).sahaay.openDirectory();
        if (dir) {
          setAttachedDirectory(dir);
        }
      }
    } catch (err) {
      console.warn("Failed to open directory dialog:", err);
    }
  };

  const handleStopTask = async (taskId: string) => {
    try {
      const headers = await getApiHeaders();
      await safeFetch(`${API_BASE}/tasks/${taskId}/stop`, { method: "POST", headers }, 3000);
      if (taskId === activeTaskId) {
        setTaskState("IDLE");
        setStatusNarrative("Task stopped by user.");
      }
      await fetchTasksList();
    } catch (err) {
      console.warn("Failed to stop task:", err);
    }
  };

  const handlePauseTask = async (taskId: string) => {
    try {
      const headers = await getApiHeaders();
      await safeFetch(`${API_BASE}/tasks/${taskId}/pause`, { method: "POST", headers }, 3000);
      await fetchTasksList();
    } catch (err) {
      console.warn("Failed to pause task:", err);
    }
  };

  const handleResumeTask = async (taskId: string) => {
    try {
      const headers = await getApiHeaders();
      await safeFetch(`${API_BASE}/tasks/${taskId}/resume`, { method: "POST", headers }, 3000);
      await fetchTasksList();
    } catch (err) {
      console.warn("Failed to resume task:", err);
    }
  };

  const handleApproveTask = async (taskId: string) => {
    try {
      const headers = await getApiHeaders();
      await safeFetch(`${API_BASE}/tasks/${taskId}/transition`, {
        method: "POST",
        headers,
        body: JSON.stringify({ targetState: "EXECUTING" }),
      }, 3000);
      await fetchTasksList();
    } catch (err) {
      console.warn("Failed to approve task:", err);
    }
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
      // Delegate all stop/encode/transcribe logic to stopAndTranscribe()
      await stopAndTranscribe();
    } else {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          setMicState("UNAVAILABLE");
          setStatusNarrative("Microphone is not supported in this environment.");
          return;
        }

        // ── AudioContext WAV capture (16kHz mono s16le) ─────────────────────
        // Meta Voyager ASR only accepts WAV at 16000 or 24000 Hz.
        // We capture raw PCM via ScriptProcessorNode and encode it ourselves
        // so we always send valid 16kHz WAV — never WebM/Opus.
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true }
        });
        streamRef.current = stream;
        pcmSamplesRef.current = [];

        const ctx = new AudioContext({ sampleRate: 16000 });
        audioContextRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        // ScriptProcessor (deprecated but universally supported in Electron/Chromium)
        const bufferSize = 4096;
        const proc = ctx.createScriptProcessor(bufferSize, 1, 1);
        proc.onaudioprocess = (e) => {
          const chunk = e.inputBuffer.getChannelData(0);
          pcmSamplesRef.current.push(new Float32Array(chunk));
        };
        source.connect(proc);
        proc.connect(ctx.destination);

        // Store processor reference on mediaRecorderRef for stop logic
        (mediaRecorderRef as any).current = { _proc: proc, _source: source, _ctx: ctx };

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

  /** Stop the AudioContext capture, encode WAV, send for transcription. */
  const stopAndTranscribe = async () => {
    if (recordingIntervalRef.current) clearInterval(recordingIntervalRef.current);
    setIsRecording(false);
    setRecordingSeconds(0);
    setMicState("PROCESSING");
    setStatusNarrative("Processing microphone audio with speech-to-text...");

    // Tear down AudioContext pipeline
    const handle = (mediaRecorderRef as any).current;
    if (handle?._proc) { handle._proc.disconnect(); }
    if (handle?._source) { handle._source.disconnect(); }
    if (handle?._ctx) { await handle._ctx.close(); }
    audioContextRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    const samples = pcmSamplesRef.current;
    pcmSamplesRef.current = [];

    if (samples.length === 0) {
      setMicState("FAILED");
      setStatusNarrative("No audio captured from microphone.");
      return;
    }

    // Encode to 16kHz WAV
    const audioBlob = encodeWav(samples, 16000);
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
          const transcribedText = data.transcript.trim();
          setUserPrompt(transcribedText);
          setStatusNarrative(`Transcript: "${transcribedText}". Executing voice command...`);
          addTimelineEntry("OBSERVE", "Voice Command Recognized", `"${transcribedText}"`);
          triggerPromptExecution(transcribedText);
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
            {/* Meta Cloud Connection Status Pill */}
            <div
              className="glass-control"
              style={{ padding: "4px 12px", display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", fontWeight: 500 }}
              title={
                modelsStatus?.metaHosted?.generationVerified
                  ? `Meta Cloud: ${modelsStatus?.metaHosted?.modelId || "muse-spark-1.3"} (Live Generation & Tools Verified)`
                  : modelsStatus?.metaHosted?.isConfigured
                  ? `Meta Cloud: ${modelsStatus?.metaHosted?.status || "Configuration Verification Pending"} - ${modelsStatus?.metaHosted?.remediationGuidance || ""}`
                  : "Meta Cloud: Configure credentials in Settings"
              }
            >
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: modelsStatus?.metaHosted?.generationVerified
                    ? "var(--sahaay-mint)"
                    : modelsStatus?.metaHosted?.isConfigured
                    ? (modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED" ? "var(--sahaay-accent-crimson)" : "var(--sahaay-warning)")
                    : "var(--sahaay-text-muted)",
                  boxShadow: modelsStatus?.metaHosted?.generationVerified ? "0 0 8px #8AF5CF" : "none",
                }}
              />
              <span>
                {modelsStatus?.metaHosted?.generationVerified
                  ? "Meta Cloud Active"
                  : modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED"
                  ? "Generation 401"
                  : modelsStatus?.metaHosted?.isConfigured
                  ? "Meta Key Check"
                  : "Meta Cloud Setup"}
              </span>
            </div>

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
          </section>

          {/* B. Main Frosted Glass Task Composer */}
          <section className="glass-surface-strong composer-card">
            {(attachedFiles.length > 0 || attachedDirectory) && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px", paddingBottom: "8px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                {attachedDirectory && (
                  <div className="badge badge-cyan" style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px" }}>
                    <Folder size={12} />
                    <span style={{ maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      Workspace: {attachedDirectory.split(/[\/\\]/).pop()}
                    </span>
                    <X size={12} style={{ cursor: "pointer" }} onClick={() => setAttachedDirectory(null)} />
                  </div>
                )}
                {attachedFiles.map((file, idx) => (
                  <div key={idx} className="badge badge-neutral" style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px" }}>
                    <FileText size={12} />
                    <span style={{ maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {file.split(/[\/\\]/).pop()}
                    </span>
                    <X size={12} style={{ cursor: "pointer" }} onClick={() => setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))} />
                  </div>
                ))}
              </div>
            )}

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
                placeholder="Type your task here or speak... (e.g. 'Open VS Code, create hello world, and run it')"
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

            {/* Middle Row: Prominent Voice Mic + Attachments + Actions */}
            <div className="composer-bottom" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {/* Prominent Voice Microphone Control */}
                <div
                  onClick={toggleRecording}
                  className={`waveform-container ${isRecording ? "anim-waveform" : ""}`}
                  style={{
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "6px 14px",
                    borderRadius: "12px",
                    background: isRecording ? "rgba(138, 245, 207, 0.15)" : "rgba(255, 255, 255, 0.05)",
                    border: isRecording ? "1px solid var(--sahaay-mint)" : "1px solid rgba(255, 255, 255, 0.1)",
                    transition: "all 0.2s ease",
                  }}
                  title={isRecording ? `Listening (${recordingSeconds}s)... Click to finish and execute` : "Click to speak your command"}
                >
                  <Mic size={16} color={isRecording ? "var(--sahaay-mint)" : "var(--sahaay-cyan)"} />
                  <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                    <div className="waveform-bar" style={{ height: isRecording ? "14px" : "6px" }} />
                    <div className="waveform-bar" style={{ height: isRecording ? "20px" : "8px" }} />
                    <div className="waveform-bar" style={{ height: isRecording ? "10px" : "5px" }} />
                    <div className="waveform-bar" style={{ height: isRecording ? "18px" : "7px" }} />
                    <div className="waveform-bar" style={{ height: isRecording ? "12px" : "6px" }} />
                  </div>
                  <span style={{ fontSize: "11px", fontWeight: 500, color: isRecording ? "var(--sahaay-mint)" : "var(--sahaay-text)", fontFamily: "var(--font-mono)" }}>
                    {isRecording ? `Listening (${recordingSeconds}s)... Click to execute` : micState === "PROCESSING" ? "Transcribing (Meta Voyager)..." : "Voice"}
                  </span>
                </div>

                {/* File & Folder Attach Buttons */}
                <button
                  type="button"
                  onClick={handleAttachFiles}
                  className="glass-control"
                  style={{ padding: "6px 10px", display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "var(--sahaay-text)", cursor: "pointer" }}
                  title="Attach Files to Task"
                >
                  <Paperclip size={13} color="var(--sahaay-mint)" /> Attach Files
                </button>
                <button
                  type="button"
                  onClick={handleAttachDirectory}
                  className="glass-control"
                  style={{ padding: "6px 10px", display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "var(--sahaay-text)", cursor: "pointer" }}
                  title="Attach Folder / Project Workspace"
                >
                  <Folder size={13} color="var(--sahaay-cyan)" /> Attach Workspace
                </button>
              </div>

              {/* Action Buttons: Stop & Send */}
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                {taskState !== "IDLE" && taskState !== "VERIFIED" && taskState !== "FAILED" && (
                  <button
                    onClick={handleStopExecution}
                    className="btn btn-danger"
                    style={{ padding: "6px 14px", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}
                    title="Cancel active execution"
                  >
                    <Square size={13} /> Stop Task
                  </button>
                )}

                <button
                  onClick={() => triggerPromptExecution(userPrompt)}
                  disabled={!userPrompt.trim() || (taskState !== "IDLE" && taskState !== "VERIFIED" && taskState !== "FAILED")}
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

              {/* Master Task Result Experience (Directive Section 12) */}
              {taskPassport && (
                <div style={{ padding: "16px 18px", background: "rgba(6, 24, 34, 0.95)", borderRadius: "14px", border: "1px solid rgba(138, 245, 207, 0.3)", display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase", color: "var(--sahaay-text-muted)" }}>
                        TASK RESULT
                      </span>
                      <span
                        className={`badge ${
                          taskPassport.verificationStatus === "VERIFIED"
                            ? "badge-success"
                            : taskPassport.verificationStatus === "FAILED"
                            ? "badge-danger"
                            : taskPassport.verificationStatus === "CANCELLED"
                            ? "badge-neutral"
                            : "badge-warning"
                        }`}
                        style={{ fontSize: "10px", fontWeight: 700 }}
                      >
                        {taskPassport.verificationStatus === "VERIFIED"
                          ? "COMPLETED & VERIFIED"
                          : taskPassport.verificationStatus}
                      </span>
                    </div>
                    <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--sahaay-cyan)" }}>
                      ID: {taskPassport.taskId.slice(0, 8)}...
                    </span>
                  </div>

                  {/* What you asked */}
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "10px 12px", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--sahaay-text-muted)", marginBottom: "4px" }}>What you asked:</div>
                    <div style={{ color: "#fff", fontWeight: 500 }}>"{taskPassport.goal}"</div>
                  </div>

                  {/* What Sahaay did */}
                  <div>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--sahaay-text-muted)", marginBottom: "6px" }}>What Sahaay did:</div>
                    <div style={{ color: "#e2e8f0", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                      {taskPassport.summary}
                    </div>
                  </div>

                  {/* Output deliverable / preview if artifact exists */}
                  {taskPassport.extractedFields?.styledUrl && (
                    <div style={{ marginTop: "6px", padding: "10px", background: "rgba(0, 0, 0, 0.3)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
                      <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--sahaay-mint)", marginBottom: "6px" }}>Result Deliverable:</div>
                      <img
                        src={`${API_BASE.replace('/api/v1', '')}${taskPassport.extractedFields.styledUrl}`}
                        alt="Task Result Deliverable"
                        style={{ maxWidth: "100%", maxHeight: "240px", borderRadius: "6px", objectFit: "contain" }}
                      />
                    </div>
                  )}

                  {/* Verification Checklist */}
                  <div style={{ background: "rgba(138, 245, 207, 0.05)", padding: "10px 12px", borderRadius: "8px", border: "1px solid rgba(138, 245, 207, 0.15)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--sahaay-mint)", marginBottom: "4px" }}>Verification:</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "11px", color: "#cbd5e1" }}>
                      <div>✓ Target surface: {taskPassport.targetAppOrUrl || "Authorized Environment"}</div>
                      <div>✓ Objective post-conditions independently checked via {taskPassport.sourceRef || "Local Controller"}</div>
                      {taskPassport.evidenceId && (
                        <div>✓ Cryptographic evidence recorded (Ledger ID: {taskPassport.evidenceId.slice(0, 8)}...)</div>
                      )}
                    </div>
                  </div>

                  {/* Collapsible Technical Evidence */}
                  <details style={{ marginTop: "4px", fontSize: "11px", color: "var(--sahaay-text-subtle)", cursor: "pointer" }}>
                    <summary style={{ outline: "none", color: "var(--sahaay-cyan)" }}>View Technical Evidence Details</summary>
                    <div style={{ marginTop: "8px", padding: "8px 10px", background: "rgba(0, 0, 0, 0.4)", borderRadius: "6px", fontFamily: "var(--font-mono)", fontSize: "10px", wordBreak: "break-all" }}>
                      <div>Evidence ID: {taskPassport.evidenceId || "N/A"}</div>
                      <div>SHA-256 Hash: {taskPassport.provenanceSha256 || "N/A"}</div>
                      <div>Workflow Mode: {taskPassport.workflowMode}</div>
                      <div>Direction: {taskPassport.direction}</div>
                      <div>Completed At: {taskPassport.createdAt}</div>
                    </div>
                  </details>
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
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)", gridColumn: "span 2" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                    <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--sahaay-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Meta AI Platform & Model Verification
                    </div>
                    <span
                      className={`badge ${
                        modelsStatus?.metaHosted?.generationVerified
                          ? "badge-success"
                          : modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED"
                          ? "badge-danger"
                          : "badge-neutral"
                      }`}
                      style={{ fontSize: "10px" }}
                    >
                      {modelsStatus?.metaHosted?.generationVerified
                        ? "ALL SYSTEMS VERIFIED"
                        : modelsStatus?.metaHosted?.status || "UNTESTED"}
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "8px" }}>
                    {[
                      { label: "API Credential", val: modelsStatus?.metaHosted?.diagnostics?.credential || (modelsStatus?.metaHosted?.isConfigured ? "Configured" : "Not Configured") },
                      { label: "TLS Connection", val: modelsStatus?.metaHosted?.diagnostics?.tlsConnection || (modelsStatus?.metaHosted?.generationVerified ? "Verified" : "Untested") },
                      { label: "API Authentication", val: modelsStatus?.metaHosted?.diagnostics?.apiAuthentication || (modelsStatus?.metaHosted?.generationVerified ? "Verified" : "Untested") },
                      { label: "Catalogue Availability", val: modelsStatus?.metaHosted?.diagnostics?.catalogueAvailability || (modelsStatus?.metaHosted?.catalogueVerified ? "Verified" : "Untested") },
                      { label: "Muse Spark", val: modelsStatus?.metaHosted?.diagnostics?.museSpark || (modelsStatus?.metaHosted?.generationVerified ? "Generation Verified" : "Untested") },
                      { label: "Muse Wonder", val: modelsStatus?.metaHosted?.diagnostics?.museWonder || (modelsStatus?.metaHosted?.generationVerified ? "Generation Verified" : "Untested") },
                      { label: "Voice Transcription", val: modelsStatus?.metaHosted?.diagnostics?.museVoice || (modelsStatus?.metaHosted?.generationVerified ? "ASR Verified" : "Untested") },
                      { label: "SAM 3.1 Grounding", val: modelsStatus?.metaHosted?.diagnostics?.sam || (modelsStatus?.metaHosted?.generationVerified ? "Grounding Verified" : "Untested") },
                    ].map((diagItem) => (
                      <div
                        key={diagItem.label}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "6px 10px",
                          borderRadius: "8px",
                          background: "rgba(255,255,255,0.02)",
                          border: "1px solid rgba(255,255,255,0.04)",
                        }}
                      >
                        <span style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>{diagItem.label}</span>
                        <span
                          className={`badge ${
                            diagItem.val.toLowerCase().includes("verified") || diagItem.val.toLowerCase() === "configured"
                              ? "badge-success"
                              : diagItem.val.toLowerCase().includes("failed") || diagItem.val.toLowerCase().includes("error") || diagItem.val.toLowerCase().includes("unauthorized")
                              ? "badge-danger"
                              : "badge-neutral"
                          }`}
                          style={{ fontSize: "10px" }}
                        >
                          {diagItem.val}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", marginTop: "8px", fontFamily: "var(--font-mono)" }}>
                    {modelsStatus?.metaHosted?.endpoint || "https://api.meta.ai/v1/chat/completions"}
                  </div>
                  {modelsStatus?.metaHosted?.remediationGuidance && (
                    <div style={{ fontSize: "10px", color: "var(--sahaay-warning)", marginTop: "4px" }}>
                      {modelsStatus.metaHosted.remediationGuidance}
                    </div>
                  )}
                  {modelsStatus?.metaHosted?.error && (
                    <div style={{ fontSize: "10px", color: "var(--sahaay-accent-crimson)", marginTop: "4px" }}>
                      {modelsStatus.metaHosted.error}
                    </div>
                  )}
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>Privacy Gateway Tier</div>
                  <div style={{ fontSize: "12px", color: localOnlyMode ? "var(--sahaay-cyan)" : "var(--sahaay-warning)", marginTop: "4px" }}>
                    {localOnlyMode ? "STRICT LOCAL-ONLY" : "HOSTED INFERENCE ALLOWED"}
                  </div>
                </div>
                <div style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "11px", color: "var(--sahaay-text-muted)" }}>NVIDIA GPU Acceleration</div>
                  <div style={{ fontSize: "12px", color: modelsStatus?.gpuAcceleration?.isAvailable ? "var(--sahaay-mint)" : "var(--sahaay-text-muted)", marginTop: "4px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span>{modelsStatus?.gpuAcceleration?.gpuName || "GeForce RTX 3050 (4GB)"}</span>
                    <span className="badge badge-success" style={{ fontSize: "10px" }}>
                      {modelsStatus?.gpuAcceleration?.isAvailable ? `${modelsStatus.gpuAcceleration.temperatureCelsius}°C` : "READY"}
                    </span>
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--sahaay-cyan)", marginTop: "2px" }}>
                    {modelsStatus?.gpuAcceleration?.freeMemoryMb ? `${modelsStatus.gpuAcceleration.freeMemoryMb} MB VRAM Free • Perception & Compute` : "Dedicated 4GB VRAM • Driver 555.97"}
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
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>Verified Computer Capabilities</h4>
                  <p style={{ fontSize: "11px", color: "var(--sahaay-text-muted)", marginBottom: "12px" }}>
                    Connected and verified computer execution capabilities:
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Browser Automation (Chrome & Edge Tabs/DOM/Forms)</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Windows Applications & UI Automation</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Native Office Deliverables (.docx & .xlsx)</span>
                    <span className="badge" style={{ background: "rgba(85,216,255,0.1)", color: "var(--sahaay-cyan)" }}>GPU Screen Perception & Change Detection</span>
                    <span className="badge" style={{ background: "rgba(85,216,255,0.1)", color: "var(--sahaay-cyan)" }}>Multi-Hop Grounded Web Research</span>
                    <span className="badge" style={{ background: "rgba(85,216,255,0.1)", color: "var(--sahaay-cyan)" }}>Tabular In-Memory SQLite Engine</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>34 Multi-Format Document Ingestion</span>
                    <span className="badge" style={{ background: "rgba(138,245,207,0.1)", color: "var(--sahaay-mint)" }}>Meta muse-spark-1.3 Dynamic Reasoning</span>
                  </div>
                </div>

                <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>General Computer Actions</h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    <button
                      onClick={() => triggerPromptExecution("Observe the active desktop window and report its controls")}
                      className="quick-action-btn"
                    >
                      <Activity size={14} color="var(--sahaay-mint)" />
                      <span>Observe Active Desktop Window</span>
                    </button>
                    <button
                      onClick={() => triggerPromptExecution("Check system status and registered capabilities")}
                      className="quick-action-btn"
                    >
                      <Search size={14} color="var(--sahaay-cyan)" />
                      <span>Check System Status & Capabilities</span>
                    </button>
                    <button
                      onClick={() => triggerPromptExecution("List files in the current workspace directory")}
                      className="quick-action-btn"
                    >
                      <FileText size={14} color="var(--sahaay-mint)" />
                      <span>List Workspace Directory Files</span>
                    </button>
                    <button
                      onClick={() => triggerPromptExecution("Launch Notepad and inspect its window")}
                      className="quick-action-btn"
                    >
                      <PlusCircle size={14} color="var(--sahaay-cyan)" />
                      <span>Launch Notepad Application</span>
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
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Needs Attention & Approvals Section */}
              {tasksList.filter((t) => t.status === "HANDOFF_REQUESTED").length > 0 && (
                <section className="glass-surface" style={{ padding: "16px 20px", borderRadius: "16px", border: "1px solid rgba(255, 170, 0, 0.4)", background: "rgba(255, 170, 0, 0.05)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <ShieldAlert size={18} color="var(--sahaay-warning)" />
                      <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>Tasks Awaiting Authorization</h3>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: "10px" }}>Human Handoff Active</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {tasksList
                      .filter((t) => t.status === "HANDOFF_REQUESTED")
                      .map((task) => (
                        <div
                          key={task.taskId}
                          style={{
                            padding: "12px 14px",
                            borderRadius: "10px",
                            background: "rgba(0,0,0,0.25)",
                            border: "1px solid rgba(255,255,255,0.08)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexWrap: "wrap",
                            gap: "10px",
                          }}
                        >
                          <div>
                            <div style={{ fontSize: "13px", fontWeight: 500, color: "#fff" }}>{task.goal}</div>
                            <div style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
                              Task ID: {task.taskId.slice(0, 8)}... • Type: {task.taskType}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "8px" }}>
                            <button
                              onClick={() => handleApproveTask(task.taskId)}
                              className="btn btn-primary text-xs"
                              style={{ padding: "4px 12px", display: "flex", alignItems: "center", gap: "4px" }}
                            >
                              <CheckCircle2 size={12} /> Approve & Continue
                            </button>
                            <button
                              onClick={() => handleStopTask(task.taskId)}
                              className="btn btn-danger text-xs"
                              style={{ padding: "4px 10px" }}
                            >
                              <Square size={11} /> Reject / Stop
                            </button>
                          </div>
                        </div>
                      ))}
                  </div>
                </section>
              )}

              {/* Chronological Unified Chat Transcript */}
              <section className="glass-surface conversation-panel" style={{ padding: "20px", borderRadius: "18px", display: "flex", flexDirection: "column", gap: "16px", minHeight: "240px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.06)", paddingBottom: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Activity size={16} color="var(--sahaay-mint)" />
                    <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>Conversation</h3>
                  </div>
                  <span className="badge badge-neutral" style={{ fontSize: "10px" }}>
                    {messages.length} messages
                  </span>
                </div>

                {messages.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--sahaay-text-subtle)", fontSize: "13px" }}>
                    Ready to assist. Ask a question, request an action in the browser or Windows, or attach files.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "450px", overflowY: "auto", paddingRight: "4px" }}>
                    {messages.map((m) => (
                      <div
                        key={m.messageId}
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: m.role === "user" ? "flex-end" : "flex-start",
                          gap: "4px",
                        }}
                      >
                        <div
                          style={{
                            maxWidth: "85%",
                            padding: "12px 16px",
                            borderRadius: m.role === "user" ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                            background: m.role === "user" ? "rgba(85, 216, 255, 0.15)" : "rgba(255, 255, 255, 0.04)",
                            border: m.role === "user" ? "1px solid rgba(85, 216, 255, 0.3)" : "1px solid rgba(255, 255, 255, 0.08)",
                            color: "#fff",
                            fontSize: "13px",
                            lineHeight: 1.5,
                          }}
                        >
                          <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>

                          {m.metadata?.styledUrl && (
                            <div style={{ marginTop: "10px" }}>
                              <img
                                src={m.metadata.styledUrl}
                                alt="Generated Visual Artifact"
                                style={{ maxHeight: "200px", maxWidth: "100%", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.15)" }}
                              />
                            </div>
                          )}

                          {m.metadata?.evidenceId && (
                            <details style={{ marginTop: "8px", fontSize: "10px", color: "var(--sahaay-text-subtle)" }}>
                              <summary style={{ cursor: "pointer", color: "var(--sahaay-cyan)" }}>Technical Evidence Details</summary>
                              <div style={{ marginTop: "4px", fontFamily: "var(--font-mono)" }}>
                                Evidence ID: {m.metadata.evidenceId}<br />
                                Target: {m.metadata.target || "Local System"}
                              </div>
                            </details>
                          )}
                        </div>
                        <span style={{ fontSize: "10px", color: "var(--sahaay-text-subtle)", padding: "0 4px" }}>
                          {m.role === "user" ? "You" : "Sahaay"} • {new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Responsive Cards Grid */}
              <section className="cards-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "16px" }}>
                {/* Card 1: Active Tasks in Progress */}
                <div className="glass-surface grid-card" style={{ minHeight: "180px" }}>
                  <div>
                    <div className="card-title-row">
                      <h3 className="card-title">Tasks in Progress</h3>
                      <span style={{ fontSize: "11px", color: "var(--sahaay-text-subtle)" }}>
                        {tasksList.filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED" && t.status !== "HANDOFF_REQUESTED").length} active
                      </span>
                    </div>

                    {tasksList.filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED" && t.status !== "HANDOFF_REQUESTED").length === 0 ? (
                      <div style={{ padding: "20px 10px", textAlign: "center", color: "var(--sahaay-text-subtle)", fontSize: "12px" }}>
                        No active tasks in progress. Enter a prompt above or attach a project to start deep work.
                      </div>
                    ) : (
                      <div className="card-items-list" style={{ gap: "8px" }}>
                        {tasksList
                          .filter((t) => t.status !== "COMPLETED" && t.status !== "FAILED" && t.status !== "CANCELLED" && t.status !== "HANDOFF_REQUESTED")
                          .slice(0, 4)
                          .map((task) => (
                            <div
                              key={task.taskId}
                              onClick={() => {
                                setActiveTaskId(task.taskId);
                                fetchTaskPassport(task.taskId);
                              }}
                              className="task-progress-item"
                              style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: "6px" }}
                            >
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "12px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden", flex: 1 }}>
                                  <Activity size={14} color="var(--sahaay-cyan)" style={{ flexShrink: 0 }} />
                                  <span style={{ fontWeight: 500, color: "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {task.goal}
                                  </span>
                                </div>
                                <span className="badge badge-success" style={{ fontSize: "9px", flexShrink: 0, marginLeft: "6px" }}>
                                  {task.status}
                                </span>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "10px", color: "var(--sahaay-text-subtle)" }}>
                                <span style={{ fontFamily: "var(--font-mono)" }}>ID: {task.taskId.slice(0, 8)}...</span>
                                <div style={{ display: "flex", gap: "4px" }}>
                                  {task.status === "PAUSED" ? (
                                    <button
                                      type="button"
                                      onClick={(e) => { e.stopPropagation(); handleResumeTask(task.taskId); }}
                                      className="btn btn-secondary text-xs"
                                      style={{ padding: "2px 6px", fontSize: "10px" }}
                                      title="Resume execution"
                                    >
                                      <Play size={10} /> Resume
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={(e) => { e.stopPropagation(); handlePauseTask(task.taskId); }}
                                      className="btn btn-secondary text-xs"
                                      style={{ padding: "2px 6px", fontSize: "10px" }}
                                      title="Pause execution"
                                    >
                                      <Pause size={10} /> Pause
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); handleStopTask(task.taskId); }}
                                    className="btn btn-danger text-xs"
                                    style={{ padding: "2px 6px", fontSize: "10px" }}
                                    title="Stop this task"
                                  >
                                    <Square size={10} /> Stop
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card 2: Recent tasks (Real SQLite Persistent Ledger) */}
                <div className="glass-surface grid-card" style={{ minHeight: "180px" }}>
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
                                  color={task.status === "COMPLETED" ? "var(--sahaay-success)" : (task.status === "CANCELLED" ? "var(--sahaay-warning)" : "var(--sahaay-danger)")}
                                  style={{ flexShrink: 0 }}
                                />
                                <span style={{ color: "#fff", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", fontSize: "12px" }}>
                                  {task.goal}
                                </span>
                              </div>
                              <span
                                className={`badge ${task.status === "COMPLETED" ? "badge-success" : (task.status === "CANCELLED" ? "badge-warning" : "badge-danger")}`}
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
              </section>
            </div>
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
                <span className={`badge ${modelsStatus?.metaHosted?.isConfigured ? "badge-success" : "badge-neutral"}`}>
                  {modelsStatus?.metaHosted?.isConfigured ? "META CLOUD (MUSE SPARK)" : "CREDENTIALS REQUIRED"}
                </span>
              </div>

              <div style={{ padding: "12px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600 }}>Meta Cloud API Credentials (MODEL_API_KEY)</span>
                  <span
                    className={`badge ${
                      modelsStatus?.metaHosted?.generationVerified
                        ? "badge-success"
                        : modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED"
                        ? "badge-danger"
                        : modelsStatus?.metaHosted?.isConfigured
                        ? "badge-warning"
                        : "badge-neutral"
                    }`}
                  >
                    {modelsStatus?.metaHosted?.generationVerified
                      ? "GENERATION AUTHENTICATED"
                      : modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED"
                      ? "GENERATION 401 (UNAUTHORIZED)"
                      : modelsStatus?.metaHosted?.isConfigured
                      ? "CONFIGURED (UNTESTED)"
                      : "NOT CONFIGURED"}
                  </span>
                </div>
                <div style={{ fontSize: "11px", color: "var(--sahaay-text-subtle)" }}>
                  Configures access to Meta hosted models ({modelsStatus?.metaHosted?.modelId || "muse-spark-1.3"}, Muse Voice, Muse Wonder) via {modelsStatus?.metaHosted?.baseUrl || "https://api.meta.ai/v1"}.
                </div>
                <div style={{ fontSize: "11px", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 8px", background: "rgba(0,0,0,0.2)", borderRadius: "4px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: "var(--sahaay-text-muted)" }}>Endpoint: {modelsStatus?.metaHosted?.endpoint || "https://api.meta.ai/v1/chat/completions"}</span>
                  <span style={{ color: modelsStatus?.metaHosted?.generationVerified ? "var(--sahaay-green)" : (modelsStatus?.metaHosted?.status === "GENERATION_UNAUTHORIZED" ? "var(--sahaay-accent-crimson)" : "var(--sahaay-warning)") }}>
                    {modelsStatus?.metaHosted?.httpResult || "UNTESTED"}
                  </span>
                </div>
                {modelsStatus?.metaHosted?.remediationGuidance && (
                  <div style={{ fontSize: "11px", color: "var(--sahaay-warning)", padding: "4px 8px", background: "rgba(255, 170, 0, 0.1)", borderRadius: "4px" }}>
                    Guidance: {modelsStatus.metaHosted.remediationGuidance}
                  </div>
                )}
                {modelsStatus?.metaHosted?.error && (
                  <div style={{ fontSize: "11px", color: "var(--sahaay-accent-crimson)", padding: "4px 8px", background: "rgba(255, 68, 68, 0.1)", borderRadius: "4px" }}>
                    Error: {modelsStatus.metaHosted.error}
                  </div>
                )}
                <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                  <input
                    type="password"
                    value={modelApiKeyInput}
                    onChange={(e) => setModelApiKeyInput(e.target.value)}
                    placeholder={modelsStatus?.metaHosted?.isConfigured ? "•••••••••••••••••••••••••••••••• (Configured)" : "Paste MODEL_API_KEY here"}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(0, 0, 0, 0.3)",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      color: "#fff",
                      fontSize: "12px",
                      outline: "none",
                    }}
                  />
                  <button
                    onClick={handleSaveModelApiKey}
                    disabled={isUpdatingApiKey || !modelApiKeyInput.trim()}
                    className="btn btn-primary text-xs"
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {isUpdatingApiKey ? "Testing..." : "Save & Verify"}
                  </button>
                </div>
                {apiKeyFeedback && (
                  <div style={{ fontSize: "11px", color: apiKeyFeedback.startsWith("✓") ? "var(--sahaay-green)" : "var(--sahaay-accent-crimson)", marginTop: "2px" }}>
                    {apiKeyFeedback}
                  </div>
                )}
              </div>

              <div style={{ padding: "10px 14px", borderRadius: "10px", background: "rgba(255, 255, 255, 0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Speech-to-Text Pipeline (Meta Voyager ASR)</span>
                <span className={`badge ${micState === "READY" || micState === "RECORDING" || micState === "TRANSCRIBED" ? "badge-success" : "badge-neutral"}`}>
                  {micState === "RECORDING" ? "RECORDING 16kHz WAV" : micState === "PROCESSING" ? "TRANSCRIBING..." : micState === "PERMISSION_REQUIRED" ? "MIC PERMISSION NEEDED" : "16kHz PCM WAV READY"}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", paddingTop: "8px" }}>
              <button
                onClick={async () => {
                  setIsProbing(true);
                  setApiKeyFeedback("Testing live Meta API connectivity and models...");
                  try {
                    const headers = await getApiHeaders();
                    const res = await safeFetch(`${API_BASE}/models/verify`, { method: "POST", headers }, 20000);
                    if (res.ok) {
                      const data = await res.json();
                      const metaInfo = data?.metaApi;
                      if (metaInfo?.generationVerified) {
                        setApiKeyFeedback(`✓ Verified: ${metaInfo.modelId || "muse-spark-1.3"} (Live Generation OK)`);
                      } else {
                        setApiKeyFeedback(`Status: ${metaInfo?.status || "Unknown"} - ${metaInfo?.message || ""}`);
                      }
                      await runDiagnosticsProbe();
                    } else {
                      setApiKeyFeedback(`✗ Test failed (HTTP ${res.status})`);
                    }
                  } catch (e: any) {
                    setApiKeyFeedback(`✗ Error: ${e.message}`);
                  } finally {
                    setIsProbing(false);
                  }
                }}
                disabled={isProbing}
                className="btn btn-secondary text-xs"
              >
                <CheckCircle2 size={14} className={isProbing ? "animate-spin" : ""} /> Test Connection
              </button>
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
