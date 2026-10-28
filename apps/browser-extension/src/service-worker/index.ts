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

function handleNativeMessage(msg: any) {
  if (!msg || !msg.command) return;
  const id = msg.id || "msg-" + Date.now();
  const command = msg.command;
  const payload = msg.parameters || msg.payload || {};

  if (command === "ping") {
    nativePort?.postMessage({
      id,
      success: true,
      command: "ping",
      data: { status: "pong", timestamp: new Date().toISOString() },
    });
    return;
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    if (!activeTab || !activeTab.id) {
      nativePort?.postMessage({ id, success: false, command, error: "No active browser tab found." });
      return;
    }
    if (
      activeTab.url &&
      (activeTab.url.startsWith("chrome:") ||
        activeTab.url.startsWith("edge:") ||
        activeTab.url.startsWith("about:"))
    ) {
      nativePort?.postMessage({
        id,
        success: false,
        command,
        error: "Cannot operate on protected internal browser pages.",
      });
      return;
    }

    chrome.tabs.sendMessage(activeTab.id, { command, payload, ...payload }, (contentRes) => {
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
                ...contentRes.data,
              }
            : contentRes.data,
      });
    });
  });
}

function ensureNativePort(): chrome.runtime.Port {
  if (!nativePort) {
    try {
      nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);
      nativePort.onDisconnect.addListener(() => {
        console.warn("[Sahaay ServiceWorker] Native port disconnected:", chrome.runtime.lastError?.message);
        nativePort = null;
      });
      nativePort.onMessage.addListener(handleNativeMessage);
    } catch (err) {
      console.error("[Sahaay ServiceWorker] Failed to connect to native host:", err);
      throw err;
    }
  }
  return nativePort;
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Sahaay ServiceWorker] Installed and initialized.");
  try {
    ensureNativePort();
  } catch (_) {}
});

chrome.runtime.onStartup?.addListener(() => {
  try {
    ensureNativePort();
  } catch (_) {}
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

  if (validMsg.command === "get_tab_observation" || validMsg.command === "get_sanitized_dom") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: validMsg.command, error: "No active tab found." });
        return;
      }

      // Check scheme - exclude chrome://, edge://, about:
      if (activeTab.url && (activeTab.url.startsWith("chrome:") || activeTab.url.startsWith("edge:") || activeTab.url.startsWith("about:"))) {
        sendResponse({ success: false, command: validMsg.command, error: "Cannot inspect protected browser internal pages." });
        return;
      }

      chrome.tabs.sendMessage(activeTab.id, { command: "get_tab_observation" }, (contentRes) => {
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
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "scroll_tab", error: "No active tab found." });
        return;
      }

      const deltaY = (validMsg.payload?.deltaY as number) || 300;
      chrome.tabs.sendMessage(activeTab.id, { command: "scroll_tab", deltaY }, (contentRes) => {
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
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "fill_form_fields", error: "No active tab found." });
        return;
      }

      chrome.tabs.sendMessage(activeTab.id, { command: "fill_form_fields", payload: validMsg.payload }, (contentRes) => {
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
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (!activeTab || !activeTab.id) {
        sendResponse({ success: false, command: "get_field_values", error: "No active tab found." });
        return;
      }

      chrome.tabs.sendMessage(activeTab.id, { command: "get_field_values", payload: validMsg.payload }, (contentRes) => {
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
