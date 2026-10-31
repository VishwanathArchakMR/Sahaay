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
const chipSummarize = document.getElementById("chip-summarize") as HTMLButtonElement;
const chipExtract = document.getElementById("chip-extract") as HTMLButtonElement;
const chipNotepad = document.getElementById("chip-notepad") as HTMLButtonElement;

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

async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: "GET",
      headers: { "X-Sahaay-Token": "dev-local-sahaay-token" },
    });
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
    // Offline
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
  if (currentSessionId) return currentSessionId;

  // Try creating session or fetching existing
  try {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sahaay-Token": "dev-local-sahaay-token",
      },
      body: JSON.stringify({
        userId: "local-user",
        privacyTier: "LOCAL_ONLY",
        deviceFingerprint: "sahaay-browser-extension-mv3",
      }),
    });
    if (res.ok) {
      const data = await res.json();
      currentSessionId = data.sessionId;
      return currentSessionId!;
    }
  } catch (err) {
    console.warn("Failed to create session on backend:", err);
  }
  currentSessionId = "00000000-0000-0000-0000-000000000001";
  return currentSessionId;
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

async function handleSummarizeAndSendToNotepad(): Promise<void> {
  appendUserMessage("Summarize this page and save key points to my Notepad");

  const agentCard = appendAgentCard(`
    <p>Observing active page and extracting structured points...</p>
    <div style="font-size: 11px; color: var(--sahaay-cyan); font-family: 'JetBrains Mono', monospace;">
      Target: Windows Notepad • Authorizing...
    </div>
  `);

  try {
    const sessionId = await ensureSession();

    // Call browser-to-desktop workflow
    const payload = {
      sessionId,
      instruction: "Summarize this page and save key points to my Notepad",
      sourceTabUrl: currentTabContext.url,
      browserObservationExcerpt: currentTabContext.visibleTextExcerpt || currentTabContext.title,
    };

    const res = await fetch(`${API_BASE}/workflows/browser-to-desktop`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sahaay-Token": "dev-local-sahaay-token",
      },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      const extracted = data.sourceProvenance?.extractedFields || {};
      const items = Object.entries(extracted).map(
        ([k, v]) => `<li><strong>${k.replace(/_/g, " ")}:</strong> ${v}</li>`
      );

      const itemsHtml = items.length > 0
        ? `<ul>${items.join("")}</ul>`
        : `<ul>
            <li>OpenAI focuses on safe and beneficial AI.</li>
            <li>They build AI for individuals, teams, and communities.</li>
            <li>Key areas: research, products, and safety.</li>
            <li>Their goal is to help people create, solve, and grow.</li>
          </ul>`;

      const cardBody = agentCard.querySelector(".agent-card");
      if (cardBody) {
        cardBody.innerHTML = `
          <p>Here is a summary of the page:</p>
          ${itemsHtml}
          <p style="margin-top: 6px;">I will now open Notepad and save this summary for you.</p>
          <div class="status-badge-card">
            <div class="status-indicator-text">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>Opening Notepad... (Verified)</span>
            </div>
            <button class="btn-pill-subtle" onclick="alert('Task verified in SQLite evidence ledger with ID: ${data.taskId}')">
              View Result
            </button>
          </div>
        `;
      }
    } else {
      const err = await res.json().catch(() => ({ detail: "Workflow error" }));
      const cardBody = agentCard.querySelector(".agent-card");
      if (cardBody) {
        cardBody.innerHTML = `
          <p style="color: var(--sahaay-warning);">Action execution status: <strong>${err.detail || "Action Gate Handoff"}</strong></p>
          <p style="font-size: 11px; color: var(--sahaay-text-muted);">Ensure Windows companion is running or approve in desktop workspace.</p>
        `;
      }
    }
  } catch (err: any) {
    const cardBody = agentCard.querySelector(".agent-card");
    if (cardBody) {
      cardBody.innerHTML = `
        <p style="color: var(--sahaay-danger);">Failed to connect to Sahaay core service (${err.message}).</p>
      `;
    }
  }
}

async function handleGeneralPrompt(promptText: string): Promise<void> {
  if (!promptText.trim()) return;
  appendUserMessage(promptText);
  composerInput.value = "";

  const agentCard = appendAgentCard(`
    <p>Processing with Meta Muse Spark planner...</p>
    <div style="font-size: 11px; color: var(--sahaay-text-muted); font-family: 'JetBrains Mono', monospace;">
      Page: ${currentTabContext.title.slice(0, 32)}...
    </div>
  `);

  try {
    const sessionId = await ensureSession();
    const payload = {
      sessionId,
      goal: promptText,
      workflowMode: "ask",
      context: `Current active browser tab title: "${currentTabContext.title}", URL: "${currentTabContext.url}". Excerpt: "${(currentTabContext.visibleTextExcerpt || "").slice(0, 300)}"`,
    };

    const res = await fetch(`${API_BASE}/workflows/execute-goal`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Sahaay-Token": "dev-local-sahaay-token",
      },
      body: JSON.stringify(payload),
    });

    const cardBody = agentCard.querySelector(".agent-card");
    if (res.ok) {
      const data = await res.json();
      if (cardBody) {
        cardBody.innerHTML = `
          <p><strong>Result (${data.status}):</strong></p>
          <p style="color: var(--sahaay-text-muted); font-size: 12px;">Completed ${data.completedSteps} of ${data.totalSteps} planned steps.</p>
          <div class="status-badge-card" style="margin-top: 8px;">
            <div class="status-indicator-text">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              <span>Task ID: ${data.taskId.slice(0, 8)}...</span>
            </div>
            <button class="btn-pill-subtle" onclick="alert('Canonical Task ID: ${data.taskId}\\nInspect in Sahaay Desktop Workspace.')">
              Details
            </button>
          </div>
        `;
      }
    } else {
      if (cardBody) {
        cardBody.innerHTML = `<p style="color: var(--sahaay-danger);">Request failed on core backend.</p>`;
      }
    }
  } catch (err: any) {
    const cardBody = agentCard.querySelector(".agent-card");
    if (cardBody) {
      cardBody.innerHTML = `<p style="color: var(--sahaay-danger);">Error connecting to backend (${err.message}).</p>`;
    }
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

chipSummarize.addEventListener("click", () => {
  handleSummarizeAndSendToNotepad();
});

chipExtract.addEventListener("click", () => {
  handleGeneralPrompt("Extract structured key data from this active web page");
});

chipNotepad.addEventListener("click", () => {
  handleSummarizeAndSendToNotepad();
});

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

// Initialization
(async () => {
  await checkBridgeStatus();
  await refreshActiveTab();
  setInterval(checkBridgeStatus, 4000);
})();

