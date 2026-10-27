using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Sahaay.Contracts;

public enum PolicyDecision
{
    ALLOW,
    DENY,
    CLARIFY,
    HANDOFF,
    REOBSERVE
}

public enum VerificationStatus
{
    VERIFIED,
    FAILED,
    UNVERIFIED,
    CONFLICT,
    NOT_ATTEMPTED
}

public record IpcMessageRequest(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("sessionId")] string SessionId,
    [property: JsonPropertyName("taskId")] string? TaskId,
    [property: JsonPropertyName("token")] string? Token,
    [property: JsonPropertyName("parameters")] Dictionary<string, object>? Parameters
);

public record IpcMessageResponse(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("data")] object? Data,
    [property: JsonPropertyName("error")] string? Error
);

public record WindowDescriptor(
    [property: JsonPropertyName("hwnd")] long Hwnd,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("processName")] string ProcessName,
    [property: JsonPropertyName("processId")] int ProcessId,
    [property: JsonPropertyName("bounds")] WindowBounds Bounds,
    [property: JsonPropertyName("isVisible")] bool IsVisible,
    [property: JsonPropertyName("isMinimized")] bool IsMinimized
);

public record WindowBounds(
    [property: JsonPropertyName("left")] int Left,
    [property: JsonPropertyName("top")] int Top,
    [property: JsonPropertyName("width")] int Width,
    [property: JsonPropertyName("height")] int Height
);

public record UiElementDescriptor(
    [property: JsonPropertyName("automationId")] string AutomationId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("controlType")] string ControlType,
    [property: JsonPropertyName("bounds")] WindowBounds Bounds,
    [property: JsonPropertyName("isEnabled")] bool IsEnabled,
    [property: JsonPropertyName("isKeyboardFocusable")] bool IsKeyboardFocusable,
    [property: JsonPropertyName("supportedPatterns")] List<string> SupportedPatterns
);

public record WindowObservationResult(
    [property: JsonPropertyName("observationId")] string ObservationId,
    [property: JsonPropertyName("capturedAt")] DateTime CapturedAt,
    [property: JsonPropertyName("hwnd")] long Hwnd,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("processName")] string ProcessName,
    [property: JsonPropertyName("elementsCount")] int ElementsCount,
    [property: JsonPropertyName("elements")] List<UiElementDescriptor>? Elements,
    [property: JsonPropertyName("screenshotPath")] string? ScreenshotPath
);

public record ControllerCapabilityReport(
    [property: JsonPropertyName("isUiAutomationSupported")] bool IsUiAutomationSupported,
    [property: JsonPropertyName("isControlledCaptureSupported")] bool IsControlledCaptureSupported,
    [property: JsonPropertyName("isShellExecutionDisabled")] bool IsShellExecutionDisabled,
    [property: JsonPropertyName("version")] string Version,
    [property: JsonPropertyName("pid")] int ProcessId
);

public record NativeHostMessageRequest(
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("sessionId")] string SessionId,
    [property: JsonPropertyName("taskId")] string? TaskId,
    [property: JsonPropertyName("parameters")] Dictionary<string, object>? Parameters
);

public record NativeHostMessageResponse(
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("data")] object? Data,
    [property: JsonPropertyName("error")] string? Error
);
