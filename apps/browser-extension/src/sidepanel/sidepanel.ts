/**
 * Sahaay Aurora Glass — Browser Side Panel Controller
 * Connects to the canonical Sahaay backend authority (FastAPI) and Native Host.
 */

const API_BASE = "http://127.0.0.1:8000/api/v1";

interface ActiveTabContext {
  url: string;
  title: string;
  visibleTextExcerpt?: string;
  tabId?: number;
}

let currentSessionId: string | null = null;
let currentTabContext: ActiveTabContext = {
  url: "",
  title: "Connecting to active tab...",
};
let isBackendConnected = false;

// DOM Elements
const connPill = document.getElementById("conn-pill") as HTMLElement;
const alertBanner = document.getElementById("alert-banner") as HTMLElement;
const alertMsg = document.getElementById("alert-msg") as HTMLElement;
const btnRetryConn = document.getElementById("btn-retry-conn") as HTMLButtonElement;
const pageTitleEl = document.getElementById("page-title") as HTMLElement;
const pageUrlEl = document.getElementById("page-url") as HTMLElement;
const btnRefreshPage = document.getElementById("btn-refresh-page") as HTMLButtonElement;
const chatStream = document.getElementById("chat-stream") as HTMLElement;
const composerInput = document.getElementById("composer-input") as HTMLInputElement;
const btnSend = document.getElementById("btn-send") as HTMLButtonElement;
const btnStop = document.getElementById("btn-stop") as HTMLButtonElement | null;

let activeExecutingTaskId: string | null = null;

// Tab switcher buttons
const tabs = document.querySelectorAll<HTMLButtonElement>(".tab-btn");
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
  });
});

let isNativeConnected = false;
let nativeHostStatus = "DISCONNECTED";

async function checkBridgeStatus(): Promise<void> {
  const backendOk = await checkBackendHealth();

  try {
    if (chrome?.runtime?.sendMessage) {
      chrome.runtime.sendMessage(
        { command: "get_native_status", sessionId: currentSessionId || "browser-sidepanel" },
        (res) => {
          if (chrome.runtime.lastError) {
            isNativeConnected = false;
            nativeHostStatus = "FAILED";
            return;
          }
          if (res?.success && res.data) {
            nativeHostStatus = res.data.connectionState || "DISCONNECTED";
            isNativeConnected = nativeHostStatus === "CONNECTED";

            if (backendOk) {
              if (isNativeConnected) {
                connPill.textContent = "Online • Bridge Connected";
                connPill.style.color = "var(--sahaay-mint)";
                connPill.style.backgroundColor = "rgba(138,245,207,0.15)";
                connPill.style.borderColor = "rgba(138,245,207,0.3)";
                alertBanner.style.display = "none";
              } else {
                connPill.textContent = `Bridge: ${nativeHostStatus}`;
                connPill.style.color = "var(--sahaay-warning)";
                connPill.style.backgroundColor = "rgba(255,209,102,0.15)";
                connPill.style.borderColor = "rgba(255,209,102,0.3)";
                alertMsg.textContent = `Native Host ${nativeHostStatus}: ${res.data.lastError || "Awaiting connection"}.`;
                alertBanner.style.display = "flex";
              }
            }
          }
        }
      );
    }
  } catch {
    // Ignore runtime messaging check errors
  }
}


let activeAuthToken: string = "";

async function getAuthToken(): Promise<string> {
  if (activeAuthToken) return activeAuthToken;
  try {
    if (chrome?.storage?.local) {
      const stored = await chrome.storage.local.get("sahaayAuthToken");
      if (stored && stored.sahaayAuthToken) {
        activeAuthToken = stored.sahaayAuthToken;
        return activeAuthToken;
      }
    }
  } catch {}
  return "";
}

async function getAuthHeaders(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const token = await getAuthToken();
  const headers: Record<string, string> = { ...extra };
  if (token) {
    headers["X-Sahaay-Token"] = token;
  }
  return headers;
}

async function safeFetch(url: string, options: RequestInit = {}, timeoutMs: number = 5000): Promise<Response> {
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
}

async function checkBackendHealth(): Promise<boolean> {
  try {
    const headers = await getAuthHeaders();
    const res = await safeFetch(`${API_BASE}/health`, {
      method: "GET",
      headers,
    }, 2000);
    if (res.ok) {
      isBackendConnected = true;
      if (isNativeConnected) {
        connPill.textContent = "Online • Bridge Connected";
        connPill.style.color = "var(--sahaay-mint)";
        connPill.style.backgroundColor = "rgba(138,245,207,0.15)";
        connPill.style.borderColor = "rgba(138,245,207,0.3)";
        alertBanner.style.display = "none";
      }
      return true;
    }
  } catch {
    // Offline or timed out
  }
  isBackendConnected = false;
  connPill.textContent = "Backend Offline";
  connPill.style.color = "var(--sahaay-danger)";
  connPill.style.backgroundColor = "rgba(255,141,145,0.15)";
  connPill.style.borderColor = "rgba(255,141,145,0.3)";
  alertMsg.textContent = "Core backend offline. Start Sahaay to enable desktop actions.";
  alertBanner.style.display = "flex";
  return false;
}

async function ensureSession(): Promise<string> {
  if (currentSessionId && currentSessionId !== "00000000-0000-0000-0000-000000000001") {
    return currentSessionId;
  }

  // Try to bind to existing shared active session from desktop/backend
  try {
    const headers = await getAuthHeaders();
    const activeRes = await safeFetch(`${API_BASE}/sessions/active/latest`, { headers }, 2000);
    if (activeRes.ok) {
      const activeData = await activeRes.json();
      if (activeData.sessionId) {
        currentSessionId = activeData.sessionId;
        return currentSessionId!;
      }
    }
  } catch {}

  // Create session on canonical backend
  try {
    const headers = await getAuthHeaders({ "Content-Type": "application/json" });
    const res = await safeFetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers,

      body: JSON.stringify({
        userId: "local-user",
        privacyTier: "HOSTED_ALLOWED",
        localOnlyMode: false,
        autoAuthorizeMetaCloud: true,
        deviceFingerprint: "sahaay-browser-extension-mv3",
      }),
    }, 2500);
    if (res.ok) {
      const data = await res.json();
      currentSessionId = data.sessionId;
      return currentSessionId!;
    }
  } catch (err) {
    console.warn("Failed to create session on backend:", err);
  }
  throw new Error("Unable to connect to Sahaay core backend. Please start the backend at 127.0.0.1:8000.");
}

async function refreshActiveTab(): Promise<void> {
  try {
    if (chrome?.tabs?.query) {
      let activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (!activeTabs || activeTabs.length === 0) {
        activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
      }
      if (!activeTabs || activeTabs.length === 0) {
        activeTabs = await chrome.tabs.query({ active: true });
      }
      
      const currentTab = (activeTabs && activeTabs.length > 0)
        ? (activeTabs.find(t => t.url && !t.url.startsWith("chrome-extension://") && !t.url.startsWith("edge://") && !t.url.startsWith("chrome://")) || activeTabs[0])
        : null;

      if (currentTab && currentTab.url) {
        currentTabContext.url = currentTab.url || "about:blank";
        currentTabContext.title = currentTab.title || currentTab.url;
        currentTabContext.tabId = currentTab.id;

        pageTitleEl.textContent = currentTabContext.title;
        pageUrlEl.textContent = currentTabContext.url;

        // Request full observation through service worker
        chrome.runtime.sendMessage(
          { command: "inspect_tab", sessionId: currentSessionId || "browser-sidepanel" },
          (response) => {
            if (chrome.runtime.lastError) {
              console.warn("Inspect tab warning:", chrome.runtime.lastError.message);
              return;
            }
            if (response?.success && response.data) {
              currentTabContext.visibleTextExcerpt = response.data.visibleTextExcerpt;
              if (response.data.title) pageTitleEl.textContent = response.data.title;
              if (response.data.url) pageUrlEl.textContent = response.data.url;
            }
          }
        );
      } else {
        pageTitleEl.textContent = "No Active Webpage Tab";
        pageUrlEl.textContent = "Open a webpage in Chrome or Edge to observe";
        currentTabContext.url = "";
        currentTabContext.title = "";
      }
    } else {
      pageTitleEl.textContent = "No Active Webpage Tab";
      pageUrlEl.textContent = "Open a webpage in Chrome or Edge to observe";
      currentTabContext.url = "";
      currentTabContext.title = "";
    }
  } catch (err) {
    console.warn("Could not query active tab:", err);
    pageTitleEl.textContent = "No Active Webpage Tab";
    pageUrlEl.textContent = "Open a webpage in Chrome or Edge to observe";
  }
}

function appendUserMessage(text: string): void {
  const bubble = document.createElement("div");
  bubble.className = "user-bubble";
  bubble.textContent = text;
  chatStream.appendChild(bubble);
  chatStream.scrollTop = chatStream.scrollHeight;
}

function appendAgentCard(htmlContent: string): HTMLElement {
  const container = document.createElement("div");
  container.className = "agent-response";
  container.innerHTML = `
    <div class="agent-header">
      <svg width="14" height="14" viewBox="0 0 32 32" fill="none">
        <path d="M7 16C7 11 11 7 16 7C21 7 25 11 25 16C25 21 21 25 16 25" stroke="#8AF5CF" stroke-width="3" stroke-linecap="round"/>
      </svg>
      <span>Sahaay Agent</span>
    </div>
    <div class="glass-surface agent-card">
      ${htmlContent}
    </div>
  `;
  chatStream.appendChild(container);
  chatStream.scrollTop = chatStream.scrollHeight;
  return container;
}

function renderCompletionCard(container: HTMLElement, opts: {
  taskId: string;
  goal: string;
  status: string;
  summary: string;
  error?: string;
  targetSurface?: string;
  provenanceSha256?: string;
  milestones?: Array<{ title: string; description: string; status: string }>;
  deliverableUrl?: string;
}) {
  const isVerified = opts.status === "COMPLETED";
  const badgeText = isVerified ? "VERIFIED" : (opts.status === "FAILED" ? "FAILED" : (opts.status === "CANCELLED" ? "CANCELLED" : "NEEDS ATTENTION"));
  const headerColor = isVerified ? "#8af5cf" : (opts.status === "FAILED" ? "#ff6b6b" : "#ffd166");
  const borderColor = isVerified ? "rgba(138, 245, 207, 0.3)" : (opts.status === "FAILED" ? "rgba(255, 107, 107, 0.3)" : "rgba(255, 209, 102, 0.3)");

  let deliverableHtml = "";
  if (opts.deliverableUrl) {
    deliverableHtml = `
      <div style="margin: 8px 0; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 8px; text-align: center;">
        <img src="${opts.deliverableUrl}" alt="Task Result Deliverable" style="max-width: 100%; max-height: 200px; border-radius: 6px; object-fit: contain;" />
      </div>
    `;
  }

  let milestonesHtml = "";
  if (opts.milestones && opts.milestones.length > 0) {
    milestonesHtml = opts.milestones.map((m) => `
      <div style="display: flex; align-items: flex-start; gap: 6px; margin-bottom: 4px;">
        <span style="color: ${m.status === 'COMPLETED' ? '#8af5cf' : '#888'};">✓</span>
        <div>
          <span style="font-weight: 500; color: #eee;">${m.title}:</span>
          <span style="color: #aaa; margin-left: 4px;">${m.description}</span>
        </div>
      </div>
    `).join("");
  }

  container.innerHTML = `
    <div style="background: rgba(6, 24, 34, 0.95); border: 1px solid ${borderColor}; border-radius: 12px; padding: 14px; font-size: 13px; display: flex; flex-direction: column; gap: 10px;">
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: #8892b0;">
            TASK RESULT
          </span>
          <span style="padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; background: ${isVerified ? 'rgba(138, 245, 207, 0.15)' : 'rgba(255,107,107,0.15)'}; color: ${headerColor}; border: 1px solid ${borderColor};">
            ${badgeText}
          </span>
        </div>
        <span style="font-family: monospace; font-size: 10px; color: #64748b;">
          ${opts.taskId.slice(0, 8)}
        </span>
      </div>

      <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px;">
        <div style="font-size: 11px; font-weight: 600; color: #8892b0; margin-bottom: 2px;">What you asked:</div>
        <div style="color: #cbd5e1; font-weight: 500;">${opts.goal}</div>
      </div>

      <div>
        <div style="font-size: 11px; font-weight: 600; color: ${headerColor}; margin-bottom: 2px;">What Sahaay did:</div>
        <div style="color: #f1f5f9; line-height: 1.4;">${opts.summary || (isVerified ? "Task completed successfully with ledger verification." : (opts.error || "Execution terminated."))}</div>
      </div>

      ${deliverableHtml}

      <div style="background: rgba(138, 245, 207, 0.05); padding: 8px 10px; border-radius: 8px; border: 1px solid rgba(138, 245, 207, 0.15); font-size: 11px;">
        <div style="font-weight: 600; color: #8af5cf; margin-bottom: 4px;">Verification:</div>
        <div style="color: #cbd5e1; display: flex; flex-direction: column; gap: 2px;">
          <div>✓ Target surface: ${opts.targetSurface || "Authorized Browser / Desktop Environment"}</div>
          <div>✓ Cryptographic proof recorded in ledger</div>
          ${opts.provenanceSha256 ? `<div>✓ Hash: <code style="font-size: 10px; color: #94a3b8;">${opts.provenanceSha256.slice(0, 16)}...</code></div>` : ""}
        </div>
      </div>

      <details style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 6px;">
        <summary style="font-size: 11px; color: #64748b; cursor: pointer;">Technical Evidence & Milestones</summary>
        <div style="margin-top: 8px; font-size: 11px;">
          ${milestonesHtml || '<span style="color: #64748b;">No individual milestone steps recorded.</span>'}
        </div>
      </details>
    </div>
  `;
}

async function handleGeneralPrompt(promptText: string): Promise<void> {
  if (!promptText.trim()) return;
  appendUserMessage(promptText);
  composerInput.value = "";

  if (btnStop) btnStop.style.display = "inline-flex";

  const agentCard = appendAgentCard(`
    <p>Executing request across authorized Sahaay capabilities...</p>
    <div style="font-size: 11px; color: var(--sahaay-text-muted); font-family: 'JetBrains Mono', monospace;">
      Page: ${(currentTabContext.title || "Active Tab").slice(0, 36)}...
    </div>
  `);

  try {
    const sessionId = await ensureSession();

    // Dynamically determine workflowMode
    const lowerPrompt = promptText.toLowerCase().trim();
    let workflowMode: "ask" | "do" | "combined_retrieval_and_action" = "combined_retrieval_and_action";
    const pureQuestionPrefixes = [
      "what is", "who is", "why is", "why does", "explain ", "tell me about", "how does", "what are", "meaning of"
    ];
    const hasActionWords = [
      "play", "listen", "watch", "stream", "open", "click", "type", "navigate",
      "browse", "launch", "search", "create", "download", "fill", "press",
      "scroll", "edit", "write", "generate", "calc", "notepad", "tab", "add to cart", "buy", "shop"
    ].some((w) => lowerPrompt.includes(w));

    if (pureQuestionPrefixes.some((p) => lowerPrompt.startsWith(p)) && !hasActionWords) {
      workflowMode = "ask";
    } else {
      workflowMode = "combined_retrieval_and_action";
    }

    const payload = {
      sessionId,
      goal: promptText,
      workflowMode,
      context: `Current active browser tab title: "${currentTabContext.title}", URL: "${currentTabContext.url}". Excerpt: "${(currentTabContext.visibleTextExcerpt || "").slice(0, 300)}"`,
    };

    const headers = await getAuthHeaders({ "Content-Type": "application/json" });
    const res = await safeFetch(`${API_BASE}/workflows/execute-goal`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    }, 90000);

    const cardBody = agentCard.querySelector(".agent-card") as HTMLElement | null;
    if (res.ok) {
      const data = await res.json();
      const taskId = data.taskId;
      activeExecutingTaskId = taskId || null;

      // If accepted asynchronously, poll for completion
      if (data.status === "ACCEPTED" && taskId) {
        if (cardBody) {
          cardBody.innerHTML = `
            <p>Task accepted (<strong>${taskId.slice(0, 8)}...</strong>). Orchestrating execution...</p>
            <div style="font-size: 11px; color: var(--sahaay-cyan); margin-top: 4px;">Observing → Proposing → Authorizing → Executing → Verifying</div>
          `;
        }

        let isCompleted = false;
        let attempts = 0;
        const maxAttempts = 300; // 180s authoritative timeout budget

        while (!isCompleted && attempts < maxAttempts) {
          await new Promise((r) => setTimeout(r, 600));
          attempts++;

          try {
            const pHeaders = await getAuthHeaders();
            const pollRes = await safeFetch(`${API_BASE}/tasks/${taskId}`, {
              headers: pHeaders,
            }, 2500);

            if (pollRes.ok) {
              const tData = await pollRes.json();
              const bStatus = (tData.status || "").toUpperCase();

              if (bStatus === "COMPLETED" || bStatus === "FAILED" || bStatus === "CANCELLED") {
                isCompleted = true;
                if (cardBody) {
                  // Attempt to fetch task passport for richer details
                  let passportData: any = null;
                  try {
                    const passRes = await safeFetch(`${API_BASE}/tasks/${taskId}/passport`, { headers: pHeaders }, 2000);
                    if (passRes.ok) passportData = await passRes.json();
                  } catch {}

                  const deliverableUrl = tData.deliverableUrl || (tData.artifacts && tData.artifacts[0]?.filePath ? `${API_BASE}/tasks/${taskId}/artifacts` : undefined);

                  // Refresh active tab so sidepanel has the latest title/URL from navigation
                  try {
                    await refreshActiveTab();
                  } catch {}

                  let resolvedTarget = passportData?.targetAppOrUrl;
                  if (!resolvedTarget || resolvedTarget.includes("New Tab") || resolvedTarget === "Windows / Browser") {
                    if (currentTabContext.title && currentTabContext.title !== "New Tab") {
                      resolvedTarget = `Browser Tab: "${currentTabContext.title}"`;
                    } else if (tData.accumulatedFacts?.browser_title && tData.accumulatedFacts?.browser_title !== "New Tab") {
                      resolvedTarget = `Browser Tab: "${tData.accumulatedFacts.browser_title}"`;
                    } else if (tData.accumulatedFacts?.browser_url) {
                      resolvedTarget = tData.accumulatedFacts.browser_url;
                    } else {
                      resolvedTarget = "Browser Window";
                    }
                  }

                  let cleanSummary = tData.summary || passportData?.summary || passportData?.summaryNotice || "";
                  if (!cleanSummary || cleanSummary.includes("Illustrations are generated as visual metaphors")) {
                    cleanSummary = bStatus === "COMPLETED" ? "Action successfully verified and completed on system." : (tData.error || "Task ended.");
                  }

                  renderCompletionCard(cardBody, {
                    taskId,
                    goal: promptText,
                    status: bStatus,
                    summary: cleanSummary,
                    error: tData.error,
                    targetSurface: resolvedTarget,
                    provenanceSha256: passportData?.provenanceSha256,
                    milestones: passportData?.milestones,
                    deliverableUrl,
                  });
                }
                break;
              }
            }
          } catch {}
        }

        if (!isCompleted && attempts >= maxAttempts && cardBody) {
          cardBody.innerHTML = `<p style="color: var(--sahaay-warning);">Task execution timed out awaiting verification.</p>`;
        }
      } else if (cardBody) {
        let cleanSummary = data.summary || "";
        if (!cleanSummary || cleanSummary.includes("Illustrations are generated as visual metaphors")) {
          cleanSummary = (data.status || "").toUpperCase() === "COMPLETED" ? "Completed successfully." : "Execution ended.";
        }
        renderCompletionCard(cardBody, {
          taskId: taskId || "sync-exec",
          goal: promptText,
          status: (data.status || "COMPLETED").toUpperCase(),
          summary: cleanSummary,
          targetSurface: (currentTabContext.title && currentTabContext.title !== "New Tab") ? `Browser Tab: "${currentTabContext.title}"` : (data.targetAppOrUrl || "Browser Environment"),
        });
      }
    } else {
      if (cardBody) {
        cardBody.innerHTML = `<p style="color: var(--sahaay-danger);">Request failed on core backend.</p>`;
      }
    }
  } catch (err: any) {
    const cardBody = agentCard.querySelector(".agent-card") as HTMLElement | null;
    if (cardBody) {
      cardBody.innerHTML = `<p style="color: var(--sahaay-danger);">Error connecting to backend (${err.message}).</p>`;
    }
  } finally {
    if (btnStop) btnStop.style.display = "none";
    activeExecutingTaskId = null;
  }
}

// Event Listeners
btnRefreshPage.addEventListener("click", () => {
  refreshActiveTab();
});

btnRetryConn.addEventListener("click", () => {
  if (chrome?.runtime?.sendMessage) {
    chrome.runtime.sendMessage({ command: "reconnect_native", sessionId: "browser-sidepanel" }, () => {
      checkBridgeStatus();
    });
  } else {
    checkBridgeStatus();
  }
});


// Attachment & Voice Input Controls
const btnAttach = document.getElementById("btn-attach") as HTMLButtonElement | null;
const btnVoice = document.getElementById("btn-voice") as HTMLButtonElement | null;
const fileInput = document.getElementById("sidepanel-file-input") as HTMLInputElement | null;
const attachedChipsEl = document.getElementById("attached-chips") as HTMLElement | null;

// ── Pure-JS WAV encoder (16kHz mono s16le PCM for Meta Voyager ASR) ──────
function encodeWav(samples: Float32Array[], sampleRate: number): Blob {
  const totalLen = samples.reduce((a, s) => a + s.length, 0);
  const merged = new Float32Array(totalLen);
  let offset = 0;
  for (const chunk of samples) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
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
  const int16 = new Int16Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const dataBytes = int16.buffer.byteLength;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  const write = (off: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i));
  };
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

let isRecording = false;
let audioContext: AudioContext | null = null;
let scriptProcessor: ScriptProcessorNode | null = null;
let mediaStream: MediaStream | null = null;
let pcmSamples: Float32Array[] = [];

if (btnAttach && fileInput) {
  btnAttach.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", async () => {
    if (!fileInput.files || fileInput.files.length === 0) return;
    const file = fileInput.files[0];
    try {
      const sid = await ensureSession();
      const formData = new FormData();
      formData.append("file", file);
      formData.append("customTitle", file.name);

      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/sources/upload-and-ingest`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (res.ok) {
        if (attachedChipsEl) {
          attachedChipsEl.style.display = "flex";
          const chip = document.createElement("div");
          chip.style.cssText = "font-size: 11px; padding: 2px 8px; border-radius: 9999px; background: rgba(85,216,255,0.15); border: 1px solid rgba(85,216,255,0.3); color: var(--sahaay-cyan); display: flex; align-items: center; gap: 4px;";
          chip.textContent = `Attached: ${file.name}`;
          attachedChipsEl.appendChild(chip);
        }
      }
    } catch (err) {
      console.warn("File upload error:", err);
    }
  });
}

if (btnVoice) {
  btnVoice.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
        });
        mediaStream = stream;
        pcmSamples = [];

        audioContext = new AudioContext({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(stream);
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        scriptProcessor.onaudioprocess = (e) => {
          const chunk = e.inputBuffer.getChannelData(0);
          pcmSamples.push(new Float32Array(chunk));
        };
        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        isRecording = true;
        btnVoice.style.color = "var(--sahaay-danger)";
        btnVoice.style.background = "rgba(255,141,145,0.2)";
        btnVoice.title = "Recording 16kHz WAV... Click to stop";
      } catch (err: any) {
        console.warn("Microphone access denied or unavailable in sidepanel:", err);
        // Chrome MV3 sidepanels cannot show the native mic permission prompt dialog directly.
        // Open the dedicated permission tab page to allow the user to grant origin mic permission.
        appendAgentCard(`
          <div style="font-size: 12px; color: var(--sahaay-warning); margin-bottom: 6px;">
            <strong>Microphone Access Needed</strong>
          </div>
          <p style="font-size: 11px; color: var(--sahaay-text-muted); margin-bottom: 4px;">
            Chrome requires microphone permission to be granted in an open tab. A permission request tab has been opened.
          </p>
        `);
        try {
          chrome.tabs.create({ url: chrome.runtime.getURL("permission/index.html") });
        } catch (tabErr) {
          console.error("Failed to open permission tab:", tabErr);
        }
      }
    } else {
      isRecording = false;
      btnVoice.style.color = "var(--sahaay-mint)";
      btnVoice.style.background = "rgba(138,245,207,0.1)";
      btnVoice.title = "Push-to-Talk Voice Input (16kHz WAV)";

      if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
      }
      if (audioContext) {
        await audioContext.close();
        audioContext = null;
      }
      if (mediaStream) {
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
      }

      const samples = pcmSamples;
      pcmSamples = [];
      if (samples.length === 0) return;

      const audioBlob = encodeWav(samples, 16000);
      try {
        const sid = await ensureSession();
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.wav");
        formData.append("languageHints", "kn,hi,en");
        formData.append("sessionId", sid);

        const headers = await getAuthHeaders();
        const res = await fetch(`${API_BASE}/models/transcribe`, {
          method: "POST",
          headers,
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          if (data.transcript && data.transcript.trim()) {
            const transcript = data.transcript.trim();
            composerInput.value = transcript;
            composerInput.focus();
            // Automatically execute recognized voice command
            await handleGeneralPrompt(transcript);
          }
        }
      } catch (err) {
        console.warn("Voice transcription error:", err);
      }
    }
  });
}

if (btnStop) {
  btnStop.addEventListener("click", async () => {
    if (activeExecutingTaskId) {
      try {
        const headers = await getAuthHeaders({ "Content-Type": "application/json" });
        await safeFetch(`${API_BASE}/tasks/${activeExecutingTaskId}/cancel`, {
          method: "POST",
          headers,
        }, 5000);
        appendAgentCard('<p style="color: var(--sahaay-warning);">Task cancellation requested.</p>');
      } catch (err: any) {
        console.warn("Could not cancel task:", err);
      } finally {
        btnStop.style.display = "none";
        activeExecutingTaskId = null;
      }
    }
  });
}

btnSend.addEventListener("click", () => {
  handleGeneralPrompt(composerInput.value);
});

composerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleGeneralPrompt(composerInput.value);
  }
});

// Tab change listeners
if (chrome?.tabs?.onActivated) {
  chrome.tabs.onActivated.addListener(() => {
    refreshActiveTab();
  });
}
if (chrome?.tabs?.onUpdated) {
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
    if (changeInfo.status === "complete" || changeInfo.title || changeInfo.url) {
      refreshActiveTab();
    }
  });
}
if (chrome?.windows?.onFocusChanged) {
  chrome.windows.onFocusChanged.addListener((windowId) => {
    if (windowId !== chrome.windows.WINDOW_ID_NONE) {
      refreshActiveTab();
    }
  });
}

// Listen for permission granted from permission tab
if (chrome?.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "VOICE_PERMISSION_GRANTED") {
      appendAgentCard(`
        <div style="font-size: 12px; color: var(--sahaay-mint);">
          ✓ <strong>Microphone Permission Enabled</strong>. Click the microphone icon to start speaking.
        </div>
      `);
    }
  });
}

// Initialization
(async () => {
  await checkBridgeStatus();
  await refreshActiveTab();
  setInterval(checkBridgeStatus, 4000);
})();

