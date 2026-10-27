/**
 * Sahaay Browser Extension Service Worker.
 * Handles native messaging with Sahaay Windows Native Host and tab management.
 */

import {
  ExtensionMessageRequest,
  ExtensionMessageResponse,
  validateExtensionMessage,
} from "../contracts/messages.js";

const NATIVE_HOST_NAME = "com.sahaay.nativehost";

chrome.runtime.onInstalled.addListener(() => {
  console.log("Sahaay Browser Bridge Service Worker installed (Manifest V3).");
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

  if (validMsg.command === "get_tab_metadata") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (!activeTab) {
        sendResponse({ success: false, command: validMsg.command, error: "No active tab found." });
        return;
      }
      sendResponse({
        success: true,
        command: validMsg.command,
        data: {
          id: activeTab.id,
          url: activeTab.url,
          title: activeTab.title,
        },
      } as ExtensionMessageResponse);
    });
    return true;
  }

  sendResponse({
    success: false,
    command: validMsg.command,
    error: "Operation not implemented in Stage 01 foundation.",
  } as ExtensionMessageResponse);
  return true;
});
