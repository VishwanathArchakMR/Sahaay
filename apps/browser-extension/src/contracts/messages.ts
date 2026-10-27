/**
 * Message schemas and validators for Sahaay Browser Extension.
 * Enforces strict allowlists, origin validation, and maximum payload size limits.
 */

export const MAX_MESSAGE_BYTES = 1024 * 1024; // 1MB maximum message size limit

export const ALLOWED_EXTENSION_COMMANDS = [
  "ping",
  "get_tab_metadata",
  "get_sanitized_dom",
  "get_tab_observation",
  "scroll_tab",
  "get_active_window",
  "list_open_windows",
  "check_authorization",
] as const;

export type ExtensionCommand = typeof ALLOWED_EXTENSION_COMMANDS[number];

export interface ExtensionMessageRequest {
  command: ExtensionCommand;
  sessionId: string;
  taskId?: string;
  payload?: Record<string, unknown>;
}

export interface ExtensionMessageResponse {
  success: boolean;
  command: string;
  data?: unknown;
  error?: string;
}

export interface TabObservationData {
  observationId: string;
  tabId: number;
  url: string;
  title: string;
  capturedAt: string;
  scrollPosition: { x: number; y: number };
  documentDimensions: {
    scrollHeight: number;
    clientHeight: number;
    scrollWidth: number;
    clientWidth: number;
  };
  visibleTextExcerpt: string;
  accessibleElements: Array<{
    tag: string;
    type?: string;
    text: string;
    id?: string;
  }>;
}

export interface ScrollActionResult {
  preScrollY: number;
  postScrollY: number;
  requestedDeltaY: number;
  actualDeltaY: number;
  isVerified: boolean;
}

export function validateExtensionMessage(rawMessage: unknown): {
  isValid: boolean;
  error?: string;
  message?: ExtensionMessageRequest;
} {
  if (!rawMessage || typeof rawMessage !== "object") {
    return { isValid: false, error: "Message must be a non-null JSON object." };
  }

  const jsonString = JSON.stringify(rawMessage);
  if (new TextEncoder().encode(jsonString).length > MAX_MESSAGE_BYTES) {
    return { isValid: false, error: `Message payload exceeds maximum size limit of ${MAX_MESSAGE_BYTES} bytes.` };
  }

  const candidate = rawMessage as Partial<ExtensionMessageRequest>;

  if (!candidate.command || typeof candidate.command !== "string") {
    return { isValid: false, error: "Field 'command' is required and must be a string." };
  }

  if (!ALLOWED_EXTENSION_COMMANDS.includes(candidate.command as ExtensionCommand)) {
    return { isValid: false, error: `Command '${candidate.command}' is not in the permitted allowlist.` };
  }

  if (!candidate.sessionId || typeof candidate.sessionId !== "string") {
    return { isValid: false, error: "Field 'sessionId' is required and must be a string." };
  }

  return { isValid: true, message: candidate as ExtensionMessageRequest };
}
