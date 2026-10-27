import React, { useEffect, useState } from "react";
import {
  Shield,
  Mic,
  Send,
  CheckCircle2,
  Pause,
  XCircle,
  UserCheck,
  Cpu,
  Database,
  Terminal,
} from "lucide-react";

interface HealthStatus {
  status: string;
  systemVersion: string;
  localOnlyMode: boolean;
  databaseReady: boolean;
}

interface CapabilityStatus {
  desktopAutomationAvailable: boolean;
  browserAutomationAvailable: boolean;
  modelsAvailable: Array<{ name: string; isAvailable: boolean }>;
  activeCapabilities: string[];
}

export function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityStatus | null>(null);
  const [inputGoal, setInputGoal] = useState("");
  const [currentStage, setCurrentStage] = useState<string>("IDLE");
  const [taskStatus, setTaskStatus] = useState<string>("READY");

  const [facts] = useState([
    {
      id: "f-1",
      type: "source-extracted",
      content: "Found permitted file: C:\\Sahaay\\docs\\architecture.md",
      confidence: 1.0,
      source: "local_file",
    },
    {
      id: "f-2",
      type: "observed",
      content: "Active window is 'Sahaay Desktop Agent'",
      confidence: 1.0,
      source: "windows_desktop",
    },
    {
      id: "f-3",
      type: "inferred",
      content: "Execution pipeline requires Action Gate authorization before dispatch",
      confidence: 0.95,
      source: "policy_engine",
    },
  ]);

  const [actions] = useState([
    {
      id: "a-1",
      type: "read_file",
      target: "C:\\Sahaay\\docs\\architecture.md",
      risk: "READ_ONLY",
      decision: "ALLOW",
      verificationStatus: "VERIFIED",
    },
  ]);

  useEffect(() => {
    // Probe local backend health endpoint
    fetch("http://127.0.0.1:8000/api/v1/health")
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => setHealth(null));

    fetch("http://127.0.0.1:8000/api/v1/capabilities")
      .then((res) => res.json())
      .then((data) => setCapabilities(data))
      .catch(() => setCapabilities(null));
  }, []);

  const stages = ["OBSERVE", "PROPOSE", "AUTHORIZE", "EXECUTE", "VERIFY", "RECORD"];

  const handleStartTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputGoal.trim()) return;
    setTaskStatus("PLANNING");
    setCurrentStage("OBSERVE");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* Top Navigation Bar */}
      <header
        style={{
          height: "56px",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          background: "var(--bg-secondary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #38bdf8, #2563eb)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: "bold",
              color: "white",
            }}
          >
            S
          </div>
          <div>
            <h1 style={{ fontSize: "16px", margin: 0 }}>Sahaay</h1>
          </div>
          <span className="badge badge-purple" style={{ marginLeft: "8px" }}>
            v0.1.0-foundation
          </span>
        </div>

        {/* System & Privacy Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            className="badge badge-success"
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <Shield size={12} />
            <span>Local-Only (Fail-Closed)</span>
          </div>

          <div
            className={`badge ${health ? "badge-success" : "badge-warning"}`}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <Database size={12} />
            <span>Backend: {health ? "Online" : "Disconnected"}</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left Column: Conversation & Task Management */}
        <section
          style={{
            flex: "1 1 55%",
            borderRight: "1px solid var(--border-color)",
            display: "flex",
            flexDirection: "column",
            background: "var(--bg-primary)",
          }}
        >
          {/* Execution Sequence Tracker */}
          <div
            style={{
              padding: "16px 20px",
              borderBottom: "1px solid var(--border-color)",
              background: "rgba(15, 23, 42, 0.6)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "10px",
              }}
            >
              <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                ORCHESTRATION PIPELINE
              </span>
              <span className="badge badge-neutral">Status: {taskStatus}</span>
            </div>

            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {stages.map((stage, idx) => {
                const isActive = stage === currentStage;
                return (
                  <React.Fragment key={stage}>
                    <div
                      style={{
                        padding: "6px 12px",
                        borderRadius: "6px",
                        fontSize: "11px",
                        fontWeight: 700,
                        letterSpacing: "0.05em",
                        background: isActive
                          ? "linear-gradient(135deg, #0284c7, #2563eb)"
                          : "var(--bg-tertiary)",
                        color: isActive ? "#ffffff" : "var(--text-muted)",
                        border: `1px solid ${isActive ? "var(--accent-primary)" : "var(--border-color)"}`,
                      }}
                    >
                      {stage}
                    </div>
                    {idx < stages.length - 1 && (
                      <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>→</span>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Action Gate & Task Controls */}
          <div
            style={{
              padding: "12px 20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid var(--border-color)",
            }}
          >
            <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Task Safety Controls:
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn btn-secondary"
                onClick={() => setTaskStatus("PAUSED")}
                style={{ fontSize: "12px", padding: "6px 12px" }}
              >
                <Pause size={14} /> Pause
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setTaskStatus("HANDOFF_REQUESTED")}
                style={{ fontSize: "12px", padding: "6px 12px" }}
              >
                <UserCheck size={14} /> Handoff
              </button>
              <button
                className="btn btn-danger"
                onClick={() => {
                  setTaskStatus("CANCELLED");
                  setCurrentStage("IDLE");
                }}
                style={{ fontSize: "12px", padding: "6px 12px" }}
              >
                <XCircle size={14} /> Cancel Task
              </button>
            </div>
          </div>

          {/* Conversation & Action Timeline Stream */}
          <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>
            <h3 style={{ fontSize: "14px", color: "var(--text-muted)", marginBottom: "12px" }}>
              ACTION TIMELINE & VERIFIED EVIDENCE
            </h3>

            {actions.map((act) => (
              <div
                key={act.id}
                className="glass-panel"
                style={{ padding: "14px", marginBottom: "12px" }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Terminal size={16} color="var(--accent-primary)" />
                    <span style={{ fontSize: "13px", fontWeight: 600 }}>{act.type}</span>
                    <span className="badge badge-neutral">{act.risk}</span>
                  </div>
                  <div style={{ display: "flex", gap: "6px" }}>
                    <span className="badge badge-success">Policy: {act.decision}</span>
                    <span className="badge badge-success">
                      <CheckCircle2 size={12} /> {act.verificationStatus}
                    </span>
                  </div>
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                  Target: {act.target}
                </div>
              </div>
            ))}
          </div>

          {/* Prompt / Input Bar */}
          <form
            onSubmit={handleStartTask}
            style={{
              padding: "16px 20px",
              borderTop: "1px solid var(--border-color)",
              background: "var(--bg-secondary)",
              display: "flex",
              gap: "10px",
              alignItems: "center",
            }}
          >
            <button
              type="button"
              className="btn btn-secondary"
              title="Voice input is scaffolded for Muse Transcribe"
              style={{ padding: "10px" }}
            >
              <Mic size={18} color="var(--text-secondary)" />
            </button>
            <input
              type="text"
              value={inputGoal}
              onChange={(e) => setInputGoal(e.target.value)}
              placeholder="Ask a question or describe a task across your real computer..."
              style={{
                flex: 1,
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "10px 14px",
                color: "var(--text-primary)",
                fontSize: "14px",
                outline: "none",
              }}
            />
            <button type="submit" className="btn btn-primary">
              <Send size={16} /> Execute
            </button>
          </form>
        </section>

        {/* Right Column: Context, Provenance & Fact Classification */}
        <aside
          style={{
            flex: "1 1 45%",
            background: "var(--bg-secondary)",
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            padding: "20px",
          }}
        >
          <div style={{ marginBottom: "20px" }}>
            <h3 style={{ fontSize: "14px", color: "var(--text-muted)", marginBottom: "12px" }}>
              EXTRACTED CONTEXT & PROVENANCE LEDGER
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Every claim is tagged by fact type and traced to its verified origin. Inferences and uncertain claims are explicitly distinguished from observed facts.
            </p>

            {facts.map((fact) => {
              let badgeColor = "badge-neutral";
              if (fact.type === "observed") badgeColor = "badge-success";
              if (fact.type === "source-extracted") badgeColor = "badge-purple";
              if (fact.type === "inferred") badgeColor = "badge-warning";

              return (
                <div
                  key={fact.id}
                  className="glass-panel"
                  style={{ padding: "14px", marginBottom: "10px" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "6px",
                    }}
                  >
                    <span className={`badge ${badgeColor}`}>{fact.type}</span>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Source: {fact.source}
                    </span>
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                    {fact.content}
                  </div>
                </div>
              );
            })}
          </div>

          {/* System Capability Truthfulness Report */}
          <div className="glass-panel" style={{ padding: "16px", marginTop: "auto" }}>
            <h4
              style={{
                fontSize: "13px",
                fontWeight: 600,
                marginBottom: "8px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Cpu size={16} color="var(--accent-primary)" /> Stage 01 Capability Baseline
            </h4>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: 1.6 }}>
              <div>• Desktop UI Automation: <strong>{capabilities?.desktopAutomationAvailable ? "Connected" : "Not Yet Connected"}</strong></div>
              <div>• Browser Extension Bridge: <strong>{capabilities?.browserAutomationAvailable ? "Active" : "Scaffolded (Manifest V3)"}</strong></div>
              <div>• External Models: <strong>{capabilities?.modelsAvailable.length ? "Configured" : "Disabled (Fail-Closed)"}</strong></div>
              <div>• Action Gate & State Machine: <strong>Enforced ({capabilities?.activeCapabilities.length ?? 0} active policies)</strong></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
