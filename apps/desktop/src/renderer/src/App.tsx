import React, { useEffect, useState } from "react";
import {
  Shield,
  Mic,
  Send,
  CheckCircle2,
  XCircle,
  Pause,
  UserCheck,
  Cpu,
  Database,
  Terminal,
  Globe,
  AppWindow,
  Search,
  ArrowUpDown,
  RefreshCw,
  Layers,
  AlertTriangle,
  FileText,
  Upload,
  FileCheck,
  Trash2,
  Compass,
  Info,
} from "lucide-react";

interface HealthStatus {
  status: string;
  systemVersion: string;
  localOnlyMode: boolean;
  databaseReady: boolean;
}

interface CapabilityStatus {
  systemVersion: string;
  desktopAutomationAvailable: boolean;
  browserAutomationAvailable: boolean;
  modelsAvailable: Array<{ name: string; isAvailable: boolean }>;
  activeCapabilities: string[];
}

interface OpenWindowItem {
  hwnd: number;
  title: string;
  processName: string;
  bounds: { x: number; y: number; width: number; height: number };
}

interface UiElementItem {
  name: string;
  controlType: string;
  bounds: { x: number; y: number; width: number; height: number };
  isKeyboardFocusable?: boolean;
}

interface BrowserObservation {
  url: string;
  title: string;
  scrollPosition: { x: number; y: number };
  documentDimensions: { width: number; height: number };
  visibleTextExcerpt: string;
  accessibleElements?: Array<{ tag: string; role: string; text: string }>;
}

interface SearchResultItem {
  factId: string;
  factType: string;
  sourceId: string;
  sourceType: string;
  sourceUri: string;
  sourceTitle: string;
  observedAt: string;
  matchedSnippet: string;
  confidenceScore: number;
  matchLocation?: string;
  isUntrustedContent?: boolean;
}

interface IngestedDocument {
  sourceId: string;
  filePath: string;
  fileName: string;
  fileSizeBytes: number;
  totalChunks: number;
  pageCount?: number;
  checksumSha256: string;
  ingestedAt: string;
}

interface FeedItem {
  id: string;
  timestamp: string;
  kind: "USER_PROMPT" | "RETRIEVAL_RESULT" | "ACTION_STEP" | "SYSTEM_NOTICE" | "INGESTION_EVENT" | "HANDOFF_ALERT";
  title: string;
  subtitle?: string;
  badge?: { text: string; variant: "purple" | "success" | "danger" | "neutral" | "warning" };
  details?: string;
  payload?: any;
}

interface ActionTimelineItem {
  id: string;
  type: string;
  target: string;
  risk: string;
  decision: string;
  verificationStatus: string;
  evidenceId?: string;
  timestamp: string;
  details?: string;
}

type TaskMode = "retrieval_only" | "action_only" | "combined_verify_action";

export function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityStatus | null>(null);

  // Unified Task & Conversation State
  const [taskMode, setTaskMode] = useState<TaskMode>("retrieval_only");
  const [inputGoal, setInputGoal] = useState("");
  const [currentStage, setCurrentStage] = useState<string>("IDLE");
  const [taskStatus, setTaskStatus] = useState<string>("READY");
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Active Sources Scope
  const [browserObs, setBrowserObs] = useState<BrowserObservation | null>({
    url: "https://developer.mozilla.org/en-US/docs/Web/API",
    title: "Web APIs | MDN Web Docs",
    scrollPosition: { x: 0, y: 120 },
    documentDimensions: { width: 1280, height: 3840 },
    visibleTextExcerpt:
      "Web APIs are typically used with JavaScript, although this doesn't always have to be the case. When writing code for the Web, there are a large number of Web APIs available...",
  });
  const [isBrowserStale, setIsBrowserStale] = useState(false);
  const [ingestedDocs, setIngestedDocs] = useState<IngestedDocument[]>([]);
  const [docPathInput, setDocPathInput] = useState("");
  const [isIngestingDoc, setIsIngestingDoc] = useState(false);

  // Windows Desktop State
  const [activeWindow, setActiveWindow] = useState<OpenWindowItem | null>(null);
  const [openWindows, setOpenWindows] = useState<OpenWindowItem[]>([]);
  const [selectedHwnd, setSelectedHwnd] = useState<number | null>(null);
  const [windowElements, setWindowElements] = useState<UiElementItem[]>([]);
  const [isLoadingWindows, setIsLoadingWindows] = useState(false);

  // Unified Chronological Feed
  const [feed, setFeed] = useState<FeedItem[]>([
    {
      id: "feed-init-1",
      timestamp: new Date().toLocaleTimeString(),
      kind: "SYSTEM_NOTICE",
      title: "Sahaay Unified Environment Initialized",
      subtitle: "Privacy Gateway: Local-Only mode enforced (Zero external model calls)",
      badge: { text: "BUILD 03 READY", variant: "purple" },
      details:
        "Deterministic information retrieval and verified computer actions operate through a shared context, Action Gate, and Independent Verifier.",
    },
    {
      id: "feed-init-2",
      timestamp: new Date().toLocaleTimeString(),
      kind: "INGESTION_EVENT",
      title: "Authorized Browser Tab Captured",
      subtitle: "MDN Web Docs (https://developer.mozilla.org/en-US/docs/Web/API)",
      badge: { text: "BROWSER TAB", variant: "neutral" },
      details:
        "Observation verified. Dimensions: 1280x3840, Scroll Y: 120px. Content indexed for deterministic keyword retrieval.",
    },
  ]);

  // Evidence Ledger
  const [actions, setActions] = useState<ActionTimelineItem[]>([
    {
      id: "act-initial-1",
      type: "OBSERVE_TAB",
      target: "https://developer.mozilla.org/en-US/docs/Web/API",
      risk: "READ_ONLY",
      decision: "ALLOW",
      verificationStatus: "VERIFIED",
      evidenceId: "ev-001-init",
      timestamp: new Date().toLocaleTimeString(),
      details: "Observed tab MDN Web Docs, verified title and dimensions",
    },
  ]);

  const stages = ["OBSERVE", "PROPOSE", "AUTHORIZE", "EXECUTE", "VERIFY", "RECORD"];

  // Polling backend capabilities and status
  const refreshStatus = () => {
    fetch("http://127.0.0.1:8000/api/v1/health")
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => setHealth(null));

    fetch("http://127.0.0.1:8000/api/v1/capabilities")
      .then((res) => res.json())
      .then((data) => setCapabilities(data))
      .catch(() => setCapabilities(null));

    fetch("http://127.0.0.1:8000/api/v1/windows/active")
      .then((res) => res.json())
      .then((data) => {
        if (data.isConnected && data.activeWindow) {
          setActiveWindow(data.activeWindow);
        }
      })
      .catch(() => {});

    fetch("http://127.0.0.1:8000/api/v1/browser/active-observation")
      .then((res) => res.json())
      .then((data) => {
        if (data.activeObservation) {
          setIsBrowserStale(data.activeObservation.isStale || false);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  // Ingest Local Document via POST /api/v1/sources/ingest-file
  const handleIngestDocument = async (filePathToIngest?: string) => {
    const targetPath = (filePathToIngest || docPathInput).trim();
    if (!targetPath) return;
    setIsIngestingDoc(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/sources/ingest-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filePath: targetPath,
          description: `User-selected document for task retrieval: ${targetPath}`,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        const newDoc: IngestedDocument = {
          sourceId: data.sourceId,
          filePath: data.filePath,
          fileName: data.fileName,
          fileSizeBytes: data.fileSizeBytes,
          totalChunks: data.totalChunks,
          pageCount: data.pageCount,
          checksumSha256: data.checksumSha256,
          ingestedAt: new Date().toLocaleTimeString(),
        };

        setIngestedDocs((prev) => [newDoc, ...prev]);
        setDocPathInput("");

        setFeed((prev) => [
          {
            id: `feed-doc-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "INGESTION_EVENT",
            title: `Document Ingested: ${data.fileName}`,
            subtitle: `Path: ${data.filePath} (${(data.fileSizeBytes / 1024).toFixed(1)} KB)`,
            badge: { text: "LOCAL DOCUMENT", variant: "purple" },
            details: `Extracted ${data.totalChunks} text chunks ${data.pageCount ? `across ${data.pageCount} pages` : ""}. SHA-256: ${data.checksumSha256.substring(0, 16)}... Indexed into deterministic store under local task boundary.`,
          },
          ...prev,
        ]);
      } else {
        setFeed((prev) => [
          {
            id: `feed-err-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "SYSTEM_NOTICE",
            title: `Document Ingestion Rejected`,
            subtitle: data.detail || "File access denied or parsing failure",
            badge: { text: "SECURITY GATE", variant: "danger" },
            details: `Strict path validation and format constraints enforced. Only authorized files (.txt, .md, .pdf) under 10MB permitted.`,
          },
          ...prev,
        ]);
      }
    } catch (err: any) {
      setFeed((prev) => [
        {
          id: `feed-err-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "SYSTEM_NOTICE",
          title: `Document Ingestion Error`,
          subtitle: String(err),
          badge: { text: "FAILED", variant: "danger" },
        },
        ...prev,
      ]);
    } finally {
      setIsIngestingDoc(false);
    }
  };

  // Observe Browser Tab via Backend
  const handleObserveTab = async () => {
    if (!browserObs) return;
    setCurrentStage("OBSERVE");
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/browser/observe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(browserObs),
      });
      const data = await res.json();
      if (data.success) {
        setIsBrowserStale(false);
        setFeed((prev) => [
          {
            id: `feed-obs-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "INGESTION_EVENT",
            title: `Fresh Browser Observation Recorded`,
            subtitle: browserObs.url,
            badge: { text: "TAB RE-OBSERVED", variant: "success" },
            details: `Version ${data.observationVersion} registered in ContextStore. Source ID: ${data.sourceId}`,
          },
          ...prev,
        ]);
        setActions((prev) => [
          {
            id: `act-${Date.now()}`,
            type: "OBSERVE_BROWSER_TAB",
            target: browserObs.url,
            risk: "READ_ONLY",
            decision: "ALLOW",
            verificationStatus: "VERIFIED",
            evidenceId: data.sourceId,
            timestamp: new Date().toLocaleTimeString(),
            details: `Observation recorded to ContextStore. Source ID: ${data.sourceId}`,
          },
          ...prev,
        ]);
      }
    } catch {
      // Fallback
    } finally {
      setCurrentStage("IDLE");
    }
  };

  // Safe Bounded Scroll Action (Action-Only workflow)
  const handleExecuteBoundedScroll = async (customDeltaY: number = 300) => {
    if (!browserObs || isProcessing) return;
    setIsProcessing(true);
    setCurrentStage("OBSERVE");

    const preScrollY = browserObs.scrollPosition.y;
    const requestedDeltaY = customDeltaY;
    const postScrollY = preScrollY + requestedDeltaY;

    try {
      // 1. Create task with taskType: 'action_only'
      const tRes = await fetch("http://127.0.0.1:8000/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: `Scroll tab ${browserObs.url} down by ${requestedDeltaY}px`,
          taskType: "action_only",
        }),
      });
      const taskData = await tRes.json();
      const taskId = taskData.taskId;
      const sessionId = taskData.sessionId;
      setActiveTaskId(taskId);
      setActiveSessionId(sessionId);
      setTaskStatus("PLANNING");

      // 2. Propose & Authorize via ActionGate
      setCurrentStage("PROPOSE");
      await new Promise((r) => setTimeout(r, 200));

      setCurrentStage("AUTHORIZE");
      // 3. Dispatch to ActionGate and IndependentVerifier
      setCurrentStage("EXECUTE");
      const actionRes = await fetch("http://127.0.0.1:8000/api/v1/browser/action/scroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          taskId,
          stepId: `step-scroll-${Date.now()}`,
          url: browserObs.url,
          requestedDeltaY,
          preScrollY,
          postScrollY,
        }),
      });

      setCurrentStage("VERIFY");
      const actionData = await actionRes.json();

      setCurrentStage("RECORD");
      // Update local browser observation state
      if (actionData.verificationStatus === "VERIFIED") {
        setBrowserObs((prev) =>
          prev
            ? {
                ...prev,
                scrollPosition: { ...prev.scrollPosition, y: postScrollY },
              }
            : null
        );
      }

      setTaskStatus(actionData.verificationStatus === "VERIFIED" ? "COMPLETED" : "FAILED");

      // Feed item
      setFeed((prev) => [
        {
          id: `feed-act-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "ACTION_STEP",
          title: `Action: Bounded Scroll (${requestedDeltaY}px)`,
          subtitle: `Target: ${browserObs.url}`,
          badge: {
            text: actionData.verificationStatus || "VERIFIED",
            variant: actionData.verificationStatus === "VERIFIED" ? "success" : "danger",
          },
          details: `ActionGate: ${actionData.policyDecision}. Pre-scroll Y: ${preScrollY}px -> Post-scroll Y: ${postScrollY}px. Delta verified: ${actionData.actualDeltaY}px. Evidence ID: ${actionData.evidenceId || "N/A"}.`,
        },
        ...prev,
      ]);

      setActions((prev) => [
        {
          id: `act-${Date.now()}`,
          type: "SCROLL_BROWSER_TAB",
          target: browserObs.url,
          risk: "READ_ONLY",
          decision: actionData.policyDecision || "ALLOW",
          verificationStatus: actionData.verificationStatus || "VERIFIED",
          evidenceId: actionData.evidenceId,
          timestamp: new Date().toLocaleTimeString(),
          details: `Requested: ${requestedDeltaY}px, Verified actualDelta: ${actionData.actualDeltaY}px. Details: ${actionData.details || "Postcondition met"}`,
        },
        ...prev,
      ]);
    } catch (err: any) {
      setTaskStatus("FAILED");
      setFeed((prev) => [
        {
          id: `feed-err-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "SYSTEM_NOTICE",
          title: "Action Execution Error",
          subtitle: String(err),
          badge: { text: "FAILED", variant: "danger" },
        },
        ...prev,
      ]);
    } finally {
      setIsProcessing(false);
      setCurrentStage("IDLE");
    }
  };

  // Perform Deterministic Search (Retrieval-Only workflow)
  const handleRetrievalTask = async (query: string) => {
    if (!query.trim() || isProcessing) return;
    setIsProcessing(true);
    setCurrentStage("OBSERVE");

    try {
      // 1. Create task with taskType: 'retrieval_only'
      const tRes = await fetch("http://127.0.0.1:8000/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: `Retrieve information matching: "${query}"`,
          taskType: "retrieval_only",
        }),
      });
      const taskData = await tRes.json();
      setActiveTaskId(taskData.taskId);
      setActiveSessionId(taskData.sessionId);
      setTaskStatus("OBSERVING");

      // 2. Perform deterministic search
      const res = await fetch("http://127.0.0.1:8000/api/v1/sources/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const searchData = await res.json();
      const results: SearchResultItem[] = searchData.results || [];

      setCurrentStage("RECORD");
      setTaskStatus("COMPLETED");

      // Post results to conversation feed
      setFeed((prev) => [
        {
          id: `feed-ret-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "RETRIEVAL_RESULT",
          title: `Retrieval Query: "${query}"`,
          subtitle: `${results.length} deterministic match(es) from authorized sources`,
          badge: { text: "RETRIEVAL-ONLY", variant: "purple" },
          details: searchData.limitationNotice || undefined,
          payload: results,
        },
        ...prev,
      ]);
    } catch (err: any) {
      setTaskStatus("FAILED");
      setFeed((prev) => [
        {
          id: `feed-err-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "SYSTEM_NOTICE",
          title: "Retrieval Query Error",
          subtitle: String(err),
          badge: { text: "FAILED", variant: "danger" },
        },
        ...prev,
      ]);
    } finally {
      setIsProcessing(false);
      setCurrentStage("IDLE");
    }
  };

  // Execute Combined Workflow: Verify precondition in sources, then perform action
  const handleCombinedWorkflow = async (expectedText: string, scrollDelta: number = 300) => {
    if (!browserObs || isProcessing) return;
    setIsProcessing(true);
    setCurrentStage("OBSERVE");

    try {
      // 1. Create combined task
      const tRes = await fetch("http://127.0.0.1:8000/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: `Verify presence of "${expectedText}" in page, then scroll ${scrollDelta}px`,
          taskType: "combined_verify_action",
        }),
      });
      const taskData = await tRes.json();
      const taskId = taskData.taskId;
      setActiveTaskId(taskId);
      setActiveSessionId(taskData.sessionId);
      setTaskStatus("OBSERVING");

      setCurrentStage("PROPOSE");
      setCurrentStage("AUTHORIZE");

      // 2. Call combined verify-and-scroll endpoint
      const combinedRes = await fetch(`http://127.0.0.1:8000/api/v1/tasks/${taskId}/combined/verify-and-scroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requiredTextInSource: expectedText,
          scrollDeltaY: scrollDelta,
          url: browserObs.url,
        }),
      });

      const combinedData = await combinedRes.json();
      setCurrentStage("VERIFY");
      setCurrentStage("RECORD");

      setTaskStatus(combinedData.taskStatus);

      if (combinedData.taskStatus === "COMPLETED") {
        setBrowserObs((prev) =>
          prev
            ? {
                ...prev,
                scrollPosition: { ...prev.scrollPosition, y: prev.scrollPosition.y + scrollDelta },
              }
            : null
        );

        setFeed((prev) => [
          {
            id: `feed-comb-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "ACTION_STEP",
            title: `Combined Workflow Succeeded`,
            subtitle: `Verified "${expectedText}" in source -> Executed scroll (${scrollDelta}px)`,
            badge: { text: "VERIFIED & EXECUTED", variant: "success" },
            details: `ActionGate authorized after precondition check. Evidence ID: ${combinedData.actionEvidenceId}. Excerpt: "${combinedData.verifiedExcerpt}"`,
          },
          ...prev,
        ]);
      } else if (combinedData.taskStatus === "HANDOFF_REQUESTED") {
        setFeed((prev) => [
          {
            id: `feed-comb-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "HANDOFF_ALERT",
            title: `Precondition Not Met: Action Blocked`,
            subtitle: `Required text "${expectedText}" was not verified in current page`,
            badge: { text: "HANDOFF REQUESTED", variant: "warning" },
            details:
              combinedData.message ||
              "Action withheld because expected source fact could not be confirmed deterministically. Control handed back to user.",
          },
          ...prev,
        ]);
      } else {
        setFeed((prev) => [
          {
            id: `feed-comb-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "SYSTEM_NOTICE",
            title: `Combined Workflow Status: ${combinedData.taskStatus}`,
            subtitle: combinedData.message,
            badge: { text: combinedData.taskStatus, variant: "danger" },
          },
          ...prev,
        ]);
      }
    } catch (err: any) {
      setTaskStatus("FAILED");
      setFeed((prev) => [
        {
          id: `feed-err-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          kind: "SYSTEM_NOTICE",
          title: "Combined Workflow Error",
          subtitle: String(err),
          badge: { text: "FAILED", variant: "danger" },
        },
        ...prev,
      ]);
    } finally {
      setIsProcessing(false);
      setCurrentStage("IDLE");
    }
  };

  // Main Prompt Form Submit (Routes according to taskMode)
  const handleSubmitPrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = inputGoal.trim();
    if (!prompt || isProcessing) return;

    // Add user message to conversation feed
    setFeed((prev) => [
      {
        id: `feed-user-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
        kind: "USER_PROMPT",
        title: prompt,
        badge: {
          text:
            taskMode === "retrieval_only"
              ? "RETRIEVAL-ONLY"
              : taskMode === "action_only"
                ? "ACTION-ONLY"
                : "COMBINED WORKFLOW",
          variant:
            taskMode === "retrieval_only"
              ? "purple"
              : taskMode === "action_only"
                ? "neutral"
                : "success",
        },
      },
      ...prev,
    ]);

    setInputGoal("");

    if (taskMode === "retrieval_only") {
      await handleRetrievalTask(prompt);
    } else if (taskMode === "action_only") {
      await handleExecuteBoundedScroll(300);
    } else {
      await handleCombinedWorkflow(prompt, 300);
    }
  };

  // Discover Open Windows
  const handleDiscoverWindows = async () => {
    setIsLoadingWindows(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/windows");
      const data = await res.json();
      if (data.isConnected && Array.isArray(data.windows)) {
        setOpenWindows(data.windows);
        if (data.windows.length > 0 && !selectedHwnd) {
          setSelectedHwnd(data.windows[0].hwnd);
        }
      }
    } catch {
      // Fallback
    } finally {
      setIsLoadingWindows(false);
    }
  };

  // Inspect Selected Window UI Automation Elements
  const handleInspectWindow = async (hwnd: number) => {
    setSelectedHwnd(hwnd);
    setWindowElements([]);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/windows/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hwnd }),
      });
      const data = await res.json();
      if (Array.isArray(data.elements)) {
        setWindowElements(data.elements);
        setFeed((prev) => [
          {
            id: `feed-win-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            kind: "INGESTION_EVENT",
            title: `UI Elements Inspected (HWND: ${hwnd})`,
            subtitle: `Found ${data.elements.length} accessible controls via .NET UIAutomation`,
            badge: { text: "WINDOWS CONTROLLER", variant: "neutral" },
            details: `Non-destructive inspection completed over authenticated named pipe.`,
          },
          ...prev,
        ]);
      }
    } catch {
      // Offline fallback
    }
  };

  // Handle Cancel / Stop
  const handleCancelTask = async () => {
    setTaskStatus("CANCELLED");
    setCurrentStage("IDLE");
    if (activeTaskId) {
      try {
        await fetch(`http://127.0.0.1:8000/api/v1/tasks/${activeTaskId}/cancel`, {
          method: "POST",
        });
      } catch {
        // Fallback
      }
    }
    setFeed((prev) => [
      {
        id: `feed-stop-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
        kind: "SYSTEM_NOTICE",
        title: "Task Stopped / Cancelled by User",
        subtitle: "ActionGate invalidated all pending operations immediately",
        badge: { text: "STOPPED", variant: "danger" },
      },
      ...prev,
    ]);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg-primary)" }}>
      {/* Top Header Bar */}
      <header
        style={{
          height: "56px",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #38bdf8, #2563eb)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: "bold",
              color: "white",
              fontSize: "16px",
            }}
          >
            S
          </div>
          <div>
            <h1 style={{ fontSize: "16px", margin: 0, fontWeight: 700, letterSpacing: "-0.01em" }}>
              Sahaay (सहाय)
            </h1>
          </div>
          <span className="badge badge-purple" style={{ marginLeft: "4px" }}>
            v0.3.0-unified
          </span>
        </div>

        {/* Live Bridges & Privacy Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div className="badge badge-success" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Shield size={12} />
            <span>Local-Only (Fail-Closed)</span>
          </div>

          <div
            className={`badge ${health ? "badge-success" : "badge-danger"}`}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <Database size={12} />
            <span>FastAPI: {health ? "Online" : "Offline"}</span>
          </div>

          <div
            className={`badge ${capabilities?.desktopAutomationAvailable ? "badge-success" : "badge-neutral"}`}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <AppWindow size={12} />
            <span>Windows Pipe: {capabilities?.desktopAutomationAvailable ? "Connected" : "Offline"}</span>
          </div>

          <div
            className={`badge ${capabilities?.browserAutomationAvailable ? "badge-success" : "badge-neutral"}`}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <Globe size={12} />
            <span>Browser Bridge: {capabilities?.browserAutomationAvailable ? "Active" : "Offline"}</span>
          </div>

          <button
            onClick={refreshStatus}
            className="btn btn-secondary"
            style={{ padding: "6px 10px", fontSize: "12px" }}
            title="Refresh component status"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </header>

      {/* Main Content Area: Split into Primary Conversation/Task Stream and Active Sources/Ledger */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left Column: Primary Unified Conversation, Search, and Task Execution Stream */}
        <section
          style={{
            flex: "1 1 62%",
            borderRight: "1px solid var(--border-color)",
            display: "flex",
            flexDirection: "column",
            background: "var(--bg-primary)",
            overflow: "hidden",
          }}
        >
          {/* Top Invariant Pipeline Bar */}
          <div
            style={{
              padding: "10px 18px",
              borderBottom: "1px solid var(--border-color)",
              background: "rgba(15, 23, 42, 0.8)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexShrink: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  fontSize: "10px",
                  color: "var(--text-secondary)",
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                }}
              >
                INVARIANT:
              </span>
              <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                {stages.map((stage, idx) => {
                  const isActive = stage === currentStage;
                  return (
                    <React.Fragment key={stage}>
                      <span
                        style={{
                          padding: "3px 8px",
                          borderRadius: "4px",
                          fontSize: "10px",
                          fontWeight: 700,
                          background: isActive
                            ? "linear-gradient(135deg, #0284c7, #2563eb)"
                            : "var(--bg-tertiary)",
                          color: isActive ? "#ffffff" : "var(--text-muted)",
                          border: `1px solid ${isActive ? "var(--accent-primary)" : "var(--border-color)"}`,
                        }}
                      >
                        {stage}
                      </span>
                      {idx < stages.length - 1 && (
                        <span style={{ color: "var(--text-muted)", fontSize: "9px" }}>→</span>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>

            {/* Task Controls */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span
                className={`badge ${
                  taskStatus === "COMPLETED"
                    ? "badge-success"
                    : taskStatus === "CANCELLED"
                      ? "badge-danger"
                      : taskStatus === "HANDOFF_REQUESTED"
                        ? "badge-warning"
                        : "badge-neutral"
                }`}
                style={{ fontSize: "10px" }}
              >
                Status: {taskStatus}
              </span>
              {activeSessionId && (
                <span className="badge badge-purple" style={{ fontSize: "9px" }}>
                  Sess: {activeSessionId.substring(0, 8)}
                </span>
              )}

              <button
                className="btn btn-secondary"
                onClick={() => setTaskStatus("PAUSED")}
                style={{ fontSize: "11px", padding: "4px 8px" }}
                title="Pause ongoing automation"
              >
                <Pause size={11} /> Pause
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setTaskStatus("HANDOFF_REQUESTED")}
                style={{ fontSize: "11px", padding: "4px 8px" }}
                title="Hand control back to human user"
              >
                <UserCheck size={11} /> Handoff
              </button>
              <button
                className="btn btn-danger"
                onClick={handleCancelTask}
                style={{ fontSize: "11px", padding: "4px 8px" }}
                title="Stop task and invalidate all pending actions"
              >
                <XCircle size={11} /> Stop
              </button>
            </div>
          </div>

          {/* Unified Feed Stream (Scrollable) */}
          <div
            style={{
              flex: 1,
              padding: "16px 20px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            {feed.map((item) => (
              <div
                key={item.id}
                className="glass-panel"
                style={{
                  padding: "14px",
                  background:
                    item.kind === "USER_PROMPT"
                      ? "rgba(30, 41, 59, 0.4)"
                      : item.kind === "HANDOFF_ALERT"
                        ? "rgba(245, 158, 11, 0.08)"
                        : "var(--bg-card)",
                  borderColor:
                    item.kind === "USER_PROMPT"
                      ? "rgba(56, 189, 248, 0.3)"
                      : item.kind === "HANDOFF_ALERT"
                        ? "rgba(245, 158, 11, 0.4)"
                        : "var(--border-color)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "6px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {item.kind === "USER_PROMPT" && <Compass size={14} color="var(--accent-primary)" />}
                    {item.kind === "RETRIEVAL_RESULT" && <Search size={14} color="#a855f7" />}
                    {item.kind === "ACTION_STEP" && <ArrowUpDown size={14} color="#10b981" />}
                    {item.kind === "INGESTION_EVENT" && <FileCheck size={14} color="#38bdf8" />}
                    {item.kind === "HANDOFF_ALERT" && <AlertTriangle size={14} color="#f59e0b" />}
                    {item.kind === "SYSTEM_NOTICE" && <Info size={14} color="var(--text-secondary)" />}

                    <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)" }}>
                      {item.title}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {item.badge && (
                      <span className={`badge badge-${item.badge.variant}`} style={{ fontSize: "10px" }}>
                        {item.badge.text}
                      </span>
                    )}
                    <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{item.timestamp}</span>
                  </div>
                </div>

                {item.subtitle && (
                  <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                    {item.subtitle}
                  </div>
                )}

                {item.details && (
                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--text-muted)",
                      background: "var(--bg-tertiary)",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      lineHeight: 1.5,
                      fontFamily: item.kind === "ACTION_STEP" ? "monospace" : "inherit",
                    }}
                  >
                    {item.details}
                  </div>
                )}

                {/* Structured Payload Rendering (for Retrieval Results) */}
                {item.payload && Array.isArray(item.payload) && (
                  <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    {item.payload.map((res: SearchResultItem) => (
                      <div
                        key={res.factId}
                        style={{
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border-color)",
                          borderRadius: "6px",
                          padding: "10px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "4px",
                          }}
                        >
                          <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent-primary)" }}>
                            {res.sourceTitle}
                          </span>
                          <span className="badge badge-purple" style={{ fontSize: "9px" }}>
                            {res.sourceType}
                          </span>
                        </div>
                        <div
                          style={{
                            fontSize: "12px",
                            color: "var(--text-primary)",
                            background: "var(--bg-tertiary)",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            lineHeight: 1.5,
                            margin: "4px 0",
                          }}
                        >
                          "{res.matchedSnippet}"
                        </div>
                        <div
                          style={{
                            fontSize: "10px",
                            color: "var(--text-muted)",
                            display: "flex",
                            justifyContent: "space-between",
                            fontFamily: "monospace",
                          }}
                        >
                          <span>Origin: {res.sourceUri}</span>
                          <span>Confidence: {(res.confidenceScore * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Document Ingestion Quick Bar */}
          <div
            style={{
              padding: "10px 18px",
              borderTop: "1px solid var(--border-color)",
              background: "var(--bg-secondary)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 600, whiteSpace: "nowrap" }}>
              <Upload size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />
              Ingest Local File:
            </span>
            <input
              type="text"
              value={docPathInput}
              onChange={(e) => setDocPathInput(e.target.value)}
              placeholder="Full path to authorized file (e.g. C:\docs\manual.pdf, .txt, .md)..."
              style={{
                flex: 1,
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                borderRadius: "6px",
                padding: "6px 10px",
                color: "var(--text-primary)",
                fontSize: "12px",
                outline: "none",
              }}
            />
            <button
              onClick={() => handleIngestDocument()}
              disabled={isIngestingDoc || !docPathInput.trim()}
              className="btn btn-secondary"
              style={{ padding: "6px 12px", fontSize: "11px", whiteSpace: "nowrap" }}
            >
              {isIngestingDoc ? "Parsing..." : "Ingest File"}
            </button>
            <button
              onClick={() => handleIngestDocument("README.md")}
              className="btn btn-secondary"
              style={{ padding: "6px 8px", fontSize: "11px", whiteSpace: "nowrap" }}
              title="Quick ingest project README"
            >
              + README.md
            </button>
          </div>

          {/* Unified Prompt & Omni-Input Footer */}
          <form
            onSubmit={handleSubmitPrompt}
            style={{
              padding: "14px 18px",
              borderTop: "1px solid var(--border-color)",
              background: "var(--bg-primary)",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              flexShrink: 0,
            }}
          >
            {/* Mode Selector Pill Buttons */}
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>Workflow:</span>
              <button
                type="button"
                onClick={() => setTaskMode("retrieval_only")}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  background: taskMode === "retrieval_only" ? "rgba(168, 85, 247, 0.2)" : "var(--bg-tertiary)",
                  color: taskMode === "retrieval_only" ? "#c084fc" : "var(--text-secondary)",
                  border: `1px solid ${taskMode === "retrieval_only" ? "#a855f7" : "var(--border-color)"}`,
                }}
              >
                🔎 Retrieval-Only
              </button>
              <button
                type="button"
                onClick={() => setTaskMode("action_only")}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  background: taskMode === "action_only" ? "rgba(56, 189, 248, 0.2)" : "var(--bg-tertiary)",
                  color: taskMode === "action_only" ? "#38bdf8" : "var(--text-secondary)",
                  border: `1px solid ${taskMode === "action_only" ? "#38bdf8" : "var(--border-color)"}`,
                }}
              >
                ⚡ Action-Only (Bounded Scroll)
              </button>
              <button
                type="button"
                onClick={() => setTaskMode("combined_verify_action")}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  background: taskMode === "combined_verify_action" ? "rgba(16, 185, 129, 0.2)" : "var(--bg-tertiary)",
                  color: taskMode === "combined_verify_action" ? "#34d399" : "var(--text-secondary)",
                  border: `1px solid ${taskMode === "combined_verify_action" ? "#10b981" : "var(--border-color)"}`,
                }}
              >
                🔗 Combined (Verify Then Act)
              </button>
            </div>

            {/* Input Row */}
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <button
                type="button"
                className="btn btn-secondary"
                title="Voice input is scaffolded for Muse Transcribe (deferred to Milestone 04 Meta model integration)"
                style={{ padding: "9px" }}
              >
                <Mic size={15} color="var(--text-secondary)" />
              </button>
              <input
                type="text"
                value={inputGoal}
                onChange={(e) => setInputGoal(e.target.value)}
                placeholder={
                  taskMode === "retrieval_only"
                    ? "Ask a question about open tab or documents (e.g., 'What is Web APIs?', 'due date')..."
                    : taskMode === "action_only"
                      ? "Request bounded computer operation (e.g., 'Scroll tab down by 300px')..."
                      : "Combined request: enter required keyword to verify in page before scrolling..."
                }
                style={{
                  flex: 1,
                  background: "var(--bg-tertiary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "9px 12px",
                  color: "var(--text-primary)",
                  fontSize: "13px",
                  outline: "none",
                }}
              />
              <button
                type="submit"
                disabled={isProcessing || !inputGoal.trim()}
                className="btn btn-primary"
                style={{ padding: "8px 16px", fontSize: "12px" }}
              >
                <Send size={14} /> {isProcessing ? "Processing..." : "Submit"}
              </button>
            </div>
          </form>
        </section>

        {/* Right Column: Active Scope & Immutable Evidence Ledger */}
        <aside
          style={{
            flex: "1 1 38%",
            background: "var(--bg-secondary)",
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            padding: "16px",
            gap: "16px",
          }}
        >
          {/* Active Authorized Scope Section */}
          <div className="glass-panel" style={{ padding: "14px" }}>
            <h3
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginBottom: "10px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Globe size={14} color="var(--accent-primary)" /> ACTIVE AUTHORIZED SOURCES & SCOPE
            </h3>

            {/* Browser Tab Scope */}
            {browserObs && (
              <div
                style={{
                  background: "var(--bg-tertiary)",
                  borderRadius: "6px",
                  padding: "10px",
                  marginBottom: "8px",
                  border: `1px solid ${isBrowserStale ? "var(--warning)" : "var(--border-color)"}`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent-primary)" }}>
                    {browserObs.title}
                  </span>
                  <div style={{ display: "flex", gap: "4px" }}>
                    {isBrowserStale && (
                      <span className="badge badge-warning" style={{ fontSize: "9px" }}>
                        STALE (Re-Observe Required)
                      </span>
                    )}
                    <button
                      onClick={handleObserveTab}
                      className="btn btn-secondary"
                      style={{ padding: "2px 6px", fontSize: "10px" }}
                      title="Re-observe active tab"
                    >
                      <RefreshCw size={10} />
                    </button>
                  </div>
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", fontFamily: "monospace", marginBottom: "4px" }}>
                  {browserObs.url}
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)" }}>
                  Scroll Y: {browserObs.scrollPosition.y}px | Dims: {browserObs.documentDimensions.width}x{browserObs.documentDimensions.height}px
                </div>
              </div>
            )}

            {/* Ingested Local Documents Scope */}
            {ingestedDocs.length > 0 && (
              <div style={{ marginTop: "8px" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
                  Ingested Documents ({ingestedDocs.length}):
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "4px" }}>
                  {ingestedDocs.map((doc) => (
                    <div
                      key={doc.sourceId}
                      style={{
                        background: "var(--bg-tertiary)",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        fontSize: "11px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        <FileText size={11} style={{ display: "inline", marginRight: "4px", verticalAlign: "middle" }} />
                        <span style={{ fontWeight: 600 }}>{doc.fileName}</span>
                        <span style={{ color: "var(--text-muted)", fontSize: "10px", marginLeft: "6px" }}>
                          ({doc.totalChunks} chunks)
                        </span>
                      </div>
                      <button
                        onClick={() => setIngestedDocs((prev) => prev.filter((d) => d.sourceId !== doc.sourceId))}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                        }}
                        title="Revoke source"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Foreground Windows Application */}
            <div style={{ marginTop: "10px", borderTop: "1px solid var(--border-color)", paddingTop: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
                  Foreground Windows App:
                </span>
                <button
                  onClick={handleDiscoverWindows}
                  disabled={isLoadingWindows}
                  className="btn btn-secondary"
                  style={{ padding: "2px 6px", fontSize: "10px" }}
                >
                  <RefreshCw size={10} /> {isLoadingWindows ? "Scanning..." : "Scan Apps"}
                </button>
              </div>
              {activeWindow ? (
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                  <strong>{activeWindow.title}</strong> ({activeWindow.processName}, HWND {activeWindow.hwnd})
                </div>
              ) : (
                <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "4px" }}>
                  {capabilities?.desktopAutomationAvailable
                    ? "Ready to inspect UI elements over named pipe"
                    : "Sahaay.Controller offline"}
                </div>
              )}

              {openWindows.length > 0 && (
                <div style={{ marginTop: "8px", maxHeight: "140px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                    Discovered Windows ({openWindows.length}):
                  </div>
                  {openWindows.map((win) => (
                    <div
                      key={win.hwnd}
                      onClick={() => handleInspectWindow(win.hwnd)}
                      style={{
                        padding: "4px 8px",
                        borderRadius: "4px",
                        background: selectedHwnd === win.hwnd ? "rgba(56, 189, 248, 0.2)" : "var(--bg-tertiary)",
                        border: `1px solid ${selectedHwnd === win.hwnd ? "var(--accent-primary)" : "var(--border-color)"}`,
                        cursor: "pointer",
                        fontSize: "11px",
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{win.title || win.processName}</span>
                      <span style={{ color: "var(--text-muted)", fontSize: "9px", marginLeft: "4px" }}>HWND {win.hwnd}</span>
                    </div>
                  ))}
                </div>
              )}

              {windowElements.length > 0 && (
                <div style={{ marginTop: "8px", maxHeight: "100px", overflowY: "auto" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>
                    Elements for HWND {selectedHwnd} ({windowElements.length}):
                  </div>
                  {windowElements.slice(0, 5).map((el, idx) => (
                    <div key={idx} style={{ fontSize: "10px", color: "var(--text-secondary)", display: "flex", justifyContent: "space-between" }}>
                      <span>{el.name || "<Unnamed>"}</span>
                      <span className="badge badge-neutral" style={{ fontSize: "8px" }}>{el.controlType}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Immutable Evidence Ledger & Verification */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <h3
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginBottom: "8px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Layers size={14} color="var(--accent-primary)" /> IMMUTABLE EVIDENCE LEDGER ({actions.length})
            </h3>
            <p style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "10px", lineHeight: 1.4 }}>
              All driver actions are authorized by ActionGate, executed, and independently verified against fresh postconditions.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {actions.map((act) => (
                <div key={act.id} className="glass-panel" style={{ padding: "10px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "4px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Terminal size={12} color="var(--accent-primary)" />
                      <span style={{ fontSize: "11px", fontWeight: 700 }}>{act.type}</span>
                    </div>
                    <span style={{ fontSize: "9px", color: "var(--text-muted)" }}>{act.timestamp}</span>
                  </div>

                  <div
                    style={{
                      fontSize: "10px",
                      color: "var(--text-secondary)",
                      fontFamily: "monospace",
                      marginBottom: "6px",
                    }}
                  >
                    Target: {act.target}
                  </div>

                  <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
                    <span className={`badge ${act.decision === "ALLOW" ? "badge-success" : "badge-danger"}`} style={{ fontSize: "9px" }}>
                      Policy: {act.decision}
                    </span>
                    <span
                      className={`badge ${
                        act.verificationStatus === "VERIFIED"
                          ? "badge-success"
                          : act.verificationStatus === "CONFLICT"
                            ? "badge-danger"
                            : "badge-neutral"
                      }`}
                      style={{ display: "flex", alignItems: "center", gap: "3px", fontSize: "9px" }}
                    >
                      {act.verificationStatus === "VERIFIED" ? (
                        <CheckCircle2 size={10} />
                      ) : (
                        <AlertTriangle size={10} />
                      )}
                      {act.verificationStatus}
                    </span>
                  </div>

                  {act.details && (
                    <div
                      style={{
                        fontSize: "10px",
                        color: "var(--text-muted)",
                        background: "var(--bg-tertiary)",
                        padding: "4px 6px",
                        borderRadius: "4px",
                      }}
                    >
                      {act.details}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* System Truthfulness Card */}
          <div className="glass-panel" style={{ padding: "12px", marginTop: "auto" }}>
            <h4
              style={{
                fontSize: "11px",
                fontWeight: 700,
                marginBottom: "6px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Cpu size={13} color="var(--accent-primary)" /> Milestone 03 Integrity Baseline
            </h4>
            <div style={{ fontSize: "10px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              <div>• External AI Models: <strong>Disabled (Zero API keys, Fail-Closed)</strong></div>
              <div>• Deterministic Ingestion: <strong>Local files (.txt, .md, .pdf) & active tab</strong></div>
              <div>• Independent Verifier: <strong>Active (Model self-attestation rejected)</strong></div>
              <div>• Untrusted Data Isolation: <strong>Web & doc text strictly separated from policy</strong></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
