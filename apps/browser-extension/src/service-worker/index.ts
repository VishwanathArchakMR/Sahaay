/**
 * Sahaay Browser Extension Service Worker (Manifest V3).
 * Bridges authorized tabs with the installed Sahaay native messaging host.
 */

import {
  ExtensionMessageRequest,
  ExtensionMessageResponse,
  validateExtensionMessage,
} from "../contracts/messages.js";

const NATIVE_HOST_NAME = "com.sahaay.nativehost";
let nativePort: chrome.runtime.Port | null = null;
let isConnecting = false;

export type NativeHostConnectionState =
  | "DISCONNECTED"
  | "CONNECTING"
  | "CONNECTED"
  | "FAILED"
  | "RECONNECTING";

let connectionState: NativeHostConnectionState = "DISCONNECTED";
let lastConnectionError: string | null = null;
let handshakeTimeoutTimer: any = null;
let lastConnectionAttemptTime = 0;

// Configure Chrome/Edge Side Panel to open on action toolbar click
try {
  if ((chrome as any).sidePanel && (chrome as any).sidePanel.setPanelBehavior) {
    (chrome as any).sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
} catch {
  // Ignore in environments where sidePanel API is not yet initialized
}

chrome.runtime.onInstalled?.addListener(() => {
  try {
    if ((chrome as any).sidePanel && (chrome as any).sidePanel.setPanelBehavior) {
      (chrome as any).sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
    }
  } catch {
    // Ignore
  }
});

function isInternalBrowserUrl(url?: string): boolean {
  if (!url) return false;
  return (
    url.startsWith("chrome:") ||
    url.startsWith("edge:") ||
    url.startsWith("about:") ||
    url.startsWith("chrome-extension:") ||
    url.startsWith("extension:")
  );
}

function findActiveWebTab(callback: (tab: chrome.tabs.Tab | null) => void) {
  // 1. First check lastFocusedWindow
  chrome.tabs.query({ active: true, lastFocusedWindow: true }, (tabs) => {
    const tab = tabs && tabs.length > 0 ? tabs[0] : null;
    if (tab && tab.id && !isInternalBrowserUrl(tab.url)) {
      callback(tab);
      return;
    }
    // 2. Fall back to any active tab across all windows
    chrome.tabs.query({ active: true }, (allTabs) => {
      const candidate = (allTabs || []).find((t) => t.id && !isInternalBrowserUrl(t.url));
      callback(candidate || null);
    });
  });
}

function sendMessageWithAutoInject(
  tabId: number,
  message: any,
  callback: (response: any) => void
) {
  chrome.tabs.sendMessage(tabId, message, (res) => {
    const lastErr = chrome.runtime.lastError?.message || "";
    if (
      lastErr.includes("Receiving end does not exist") ||
      lastErr.includes("Could not establish connection")
    ) {
      console.log(`[Sahaay ServiceWorker] Injecting content script into tab ${tabId}...`);
      if (chrome.scripting) {
        chrome.scripting.executeScript(
          {
            target: { tabId },
            files: ["dist/content/index.js"],
          },
          () => {
            if (chrome.runtime.lastError) {
              callback({ success: false, error: chrome.runtime.lastError.message });
              return;
            }
            setTimeout(() => {
              chrome.tabs.sendMessage(tabId, message, (retryRes) => {
                if (chrome.runtime.lastError) {
                  callback({ success: false, error: chrome.runtime.lastError.message });
                } else {
                  callback(retryRes);
                }
              });
            }, 100);
          }
        );
        return;
      }
    }
    callback(res);
  });
}

function handleNativeMessage(msg: any) {
  if (!msg) return;

  // 1. Handshake / hello confirmation from Native Host
  if ((msg.command === "hello" || msg.command === "handshake") && msg.success) {
    connectionState = "CONNECTED";
    lastConnectionError = null;
    if (handshakeTimeoutTimer) {
      clearTimeout(handshakeTimeoutTimer);
      handshakeTimeoutTimer = null;
    }
    console.log("[Sahaay ServiceWorker] Handshake verified. Native Host CONNECTED:", msg.data);
    return;
  }

  const id = msg.id || "msg-" + Date.now();
  const command = msg.command;
  const payload = msg.parameters || msg.payload || {};

  if (command === "ping") {
    nativePort?.postMessage({
      id,
      success: true,
      command: "ping",
      data: { status: "pong", timestamp: new Date().toISOString(), extensionId: chrome.runtime.id },
    });
    return;
  }

  if (command === "get_status") {
    findActiveWebTab((activeTab) => {
      nativePort?.postMessage({
        id,
        success: true,
        command: "get_status",
        data: {
          extensionId: chrome.runtime.id,
          hasActiveTab: !!activeTab,
          activeTabUrl: activeTab?.url || null,
          activeTabTitle: activeTab?.title || null,
          timestamp: new Date().toISOString(),
        },
      });
    });
    return;
  }

  findActiveWebTab((activeTab) => {
    if (!activeTab || !activeTab.id) {
      nativePort?.postMessage({
        id,
        success: false,
        command,
        error: "No active browser tab found. Please open an accessible webpage in Chrome or Edge.",
      });
      return;
    }

    sendMessageWithAutoInject(activeTab.id, { command, payload, ...payload }, (contentRes) => {
      if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
        nativePort?.postMessage({
          id,
          success: false,
          command,
          error:
            chrome.runtime.lastError?.message ||
            contentRes?.error ||
            "Content script did not respond.",
        });
        return;
      }
      nativePort?.postMessage({
        id,
        success: true,
        command,
        data:
          command === "get_tab_observation" || command === "get_sanitized_dom"
            ? {
                observationId: crypto.randomUUID(),
                tabId: activeTab.id,
                capturedAt: new Date().toISOString(),
                driverProvenance: "real_browser_extension",
                ...contentRes.data,
              }
            : contentRes.data,
      });
    });
  });
}

function ensureNativePort(forceReconnect: boolean = false): chrome.runtime.Port | null {
  if (nativePort && connectionState === "CONNECTED" && !forceReconnect) {
    return nativePort;
  }

  const now = Date.now();
  if (isConnecting || (!forceReconnect && now - lastConnectionAttemptTime < 1500)) {
    return nativePort;
  }

  lastConnectionAttemptTime = now;
  isConnecting = true;
  connectionState = forceReconnect ? "RECONNECTING" : "CONNECTING";
  lastConnectionError = null;

  try {
    if (nativePort) {
      try {
        nativePort.disconnect();
      } catch {}
      nativePort = null;
    }

    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

    nativePort.onDisconnect.addListener(() => {
      const lastErr =
        chrome.runtime.lastError?.message ||
        "Specified native messaging host not found or port closed.";
      console.warn("[Sahaay ServiceWorker] Native port disconnected:", lastErr);
      lastConnectionError = lastErr;
      connectionState = "FAILED";
      nativePort = null;
      isConnecting = false;
      if (handshakeTimeoutTimer) {
        clearTimeout(handshakeTimeoutTimer);
        handshakeTimeoutTimer = null;
      }
    });

    nativePort.onMessage.addListener(handleNativeMessage);

    // Dispatch initial handshake to establish authenticated bidirectional bridge
    try {
      nativePort.postMessage({
        id: "hs-" + Date.now(),
        command: "hello",
        sessionId: "browser-service-worker",
        payload: {
          extensionId: chrome.runtime.id,
          timestamp: new Date().toISOString(),
        },
      });
      console.log(
        "[Sahaay ServiceWorker] Dispatched handshake to Native Host. Awaiting confirmation..."
      );

      // Start 3-second handshake confirmation timer
      if (handshakeTimeoutTimer) clearTimeout(handshakeTimeoutTimer);
      handshakeTimeoutTimer = setTimeout(() => {
        if (connectionState === "CONNECTING" || connectionState === "RECONNECTING") {
          console.warn("[Sahaay ServiceWorker] Handshake timed out waiting for Native Host.");
          connectionState = "FAILED";
          lastConnectionError = "Handshake timed out waiting for confirmation from Native Host.";
        }
      }, 3000);
    } catch (postErr: any) {
      console.warn("[Sahaay ServiceWorker] Handshake dispatch failed:", postErr);
      connectionState = "FAILED";
      lastConnectionError = postErr?.message || "Failed to dispatch handshake message.";
    }
  } catch (err: any) {
    console.error("[Sahaay ServiceWorker] connectNative exception:", err);
    connectionState = "FAILED";
    lastConnectionError = err?.message || "connectNative threw an exception.";
    nativePort = null;
  } finally {
    isConnecting = false;
  }

  return nativePort;
}

// Lifecycle listeners
chrome.runtime.onInstalled.addListener(() => {
  console.log("[Sahaay ServiceWorker] Installed and initialized.");
  ensureNativePort();
});

chrome.runtime.onStartup?.addListener(() => {
  ensureNativePort();
});

chrome.tabs.onActivated?.addListener(() => {
  ensureNativePort();
});

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  const validation = validateExtensionMessage(message);

  if (!validation.isValid || !validation.message) {
    sendResponse({
      success: false,
      command: "unknown",
      error: validation.error || "Malformed message.",
    } as ExtensionMessageResponse);
    return true;
  }

  const validMsg = validation.message;

  if (validMsg.command === "ping") {
    sendResponse({
      success: true,
      command: "ping",
      data: { status: "pong", timestamp: new Date().toISOString() },
    } as ExtensionMessageResponse);
    return true;
  }

  if (validMsg.command === "get_status") {
    findActiveWebTab((activeTab) => {
      sendResponse({
        success: true,
        command: "get_status",
        data: {
          extensionId: chrome.runtime.id,
          hasActiveTab: !!activeTab,
          activeTabUrl: activeTab?.url || null,
          isNativePortConnected: !!nativePort && connectionState === "CONNECTED",
          nativeHostConnectionState: connectionState,
          nativeHostError: lastConnectionError,
        },
      } as ExtensionMessageResponse);
    });
    return true;
  }

  if (validMsg.command === "get_native_status") {
    sendResponse({
      success: true,
      command: "get_native_status",
      data: {
        connectionState,
        lastError: lastConnectionError,
        extensionId: chrome.runtime.id,
        nativeHostName: NATIVE_HOST_NAME,
        isPortConnected: !!nativePort && connectionState === "CONNECTED",
      },
    } as ExtensionMessageResponse);
    return true;
  }

  if (validMsg.command === "reconnect_native") {
    ensureNativePort(true);
    sendResponse({
      success: true,
      command: "reconnect_native",
      data: {
        connectionState,
        lastError: lastConnectionError,
      },
    } as ExtensionMessageResponse);
    return true;
  }

  if (validMsg.command === "inspect_tab") {
    findActiveWebTab((activeTab) => {
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "inspect_tab", error: "No active browser tab found." });
        return;
      }
      sendMessageWithAutoInject(activeTab.id, { command: "get_tab_observation" }, (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          sendResponse({
            success: false,
            command: "inspect_tab",
            error: chrome.runtime.lastError?.message || contentRes?.error || "Content script did not respond.",
          });
          return;
        }
        sendResponse({
          success: true,
          command: "inspect_tab",
          data: {
            observationId: crypto.randomUUID(),
            tabId: activeTab.id,
            url: activeTab.url,
            title: activeTab.title,
            capturedAt: new Date().toISOString(),
            driverProvenance: "real_browser_extension",
            ...contentRes.data,
          },
        });
      });
    });
    return true;
  }

  if (validMsg.command === "get_tab_observation" || validMsg.command === "get_sanitized_dom") {
    findActiveWebTab((activeTab) => {
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: validMsg.command, error: "No active browser tab found." });
        return;
      }

      sendMessageWithAutoInject(activeTab.id, { command: "get_tab_observation" }, (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          sendResponse({
            success: false,
            command: validMsg.command,
            error: chrome.runtime.lastError?.message || contentRes?.error || "Content script did not respond.",
          });
          return;
        }

        const observationData = {
          observationId: crypto.randomUUID(),
          tabId: activeTab.id,
          capturedAt: new Date().toISOString(),
          driverProvenance: "real_browser_extension",
          ...contentRes.data,
        };

        sendResponse({
          success: true,
          command: validMsg.command,
          data: observationData,
        } as ExtensionMessageResponse);
      });
    });
    return true;
  }

  if (validMsg.command === "scroll_tab") {
    findActiveWebTab((activeTab) => {
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "scroll_tab", error: "No active tab found." });
        return;
      }

      const deltaY = (validMsg.payload?.deltaY as number) || 300;
      sendMessageWithAutoInject(activeTab.id, { command: "scroll_tab", deltaY }, (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          sendResponse({
            success: false,
            command: "scroll_tab",
            error: chrome.runtime.lastError?.message || contentRes?.error || "Failed to execute scroll on tab.",
          });
          return;
        }

        sendResponse({
          success: true,
          command: "scroll_tab",
          data: contentRes.data,
        } as ExtensionMessageResponse);
      });
    });
    return true;
  }

  if (validMsg.command === "fill_form_fields") {
    findActiveWebTab((activeTab) => {
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "fill_form_fields", error: "No active tab found." });
        return;
      }

      sendMessageWithAutoInject(activeTab.id, { command: "fill_form_fields", payload: validMsg.payload }, (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          sendResponse({
            success: false,
            command: "fill_form_fields",
            error: chrome.runtime.lastError?.message || contentRes?.error || "Failed to fill form fields.",
          });
          return;
        }

        sendResponse({
          success: true,
          command: "fill_form_fields",
          data: contentRes.data,
        } as ExtensionMessageResponse);
      });
    });
    return true;
  }

  if (validMsg.command === "get_field_values") {
    findActiveWebTab((activeTab) => {
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "get_field_values", error: "No active tab found." });
        return;
      }

      sendMessageWithAutoInject(activeTab.id, { command: "get_field_values", payload: validMsg.payload }, (contentRes) => {
        if (chrome.runtime.lastError || !contentRes || !contentRes.success) {
          sendResponse({
            success: false,
            command: "get_field_values",
            error: chrome.runtime.lastError?.message || contentRes?.error || "Failed to get field values.",
          });
          return;
        }

        sendResponse({
          success: true,
          command: "get_field_values",
          data: contentRes.data,
        } as ExtensionMessageResponse);
      });
    });
    return true;
  }

  // Forward native commands to NativeHost
  if (validMsg.command === "get_active_window" || validMsg.command === "list_open_windows") {
    try {
      chrome.runtime.sendNativeMessage(
        NATIVE_HOST_NAME,
        {
          command: validMsg.command,
          sessionId: validMsg.sessionId,
          taskId: validMsg.taskId,
          parameters: validMsg.payload,
        },
        (nativeRes) => {
          if (chrome.runtime.lastError) {
            sendResponse({
              success: false,
              command: validMsg.command,
              error: `Native messaging failed: ${chrome.runtime.lastError.message}`,
            });
            return;
          }
          sendResponse(nativeRes);
        }
      );
    } catch (err: any) {
      sendResponse({
        success: false,
        command: validMsg.command,
        error: `Could not send message to native host: ${err.message}`,
      });
    }
    return true;
  }

  sendResponse({
    success: false,
    command: validMsg.command,
    error: `Command '${validMsg.command}' not implemented.`,
  } as ExtensionMessageResponse);
  return true;
});
