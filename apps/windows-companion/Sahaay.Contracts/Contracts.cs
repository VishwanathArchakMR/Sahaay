using System;
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

public record NativeHostMessageRequest(
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("sessionId")] string SessionId,
    [property: JsonPropertyName("taskId")] string? TaskId,
    [property: JsonPropertyName("parameters")] object? Parameters
);

public record NativeHostMessageResponse(
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("command")] string Command,
    [property: JsonPropertyName("data")] object? Data,
    [property: JsonPropertyName("error")] string? Error
);

public record WindowDescriptor(
    [property: JsonPropertyName("hwnd")] long Hwnd,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("processName")] string ProcessName,
    [property: JsonPropertyName("bounds")] string Bounds
);

public record ControllerCapabilityReport(
    [property: JsonPropertyName("isUiAutomationSupported")] bool IsUiAutomationSupported,
    [property: JsonPropertyName("isControlledCaptureSupported")] bool IsControlledCaptureSupported,
    [property: JsonPropertyName("isShellExecutionDisabled")] bool IsShellExecutionDisabled,
    [property: JsonPropertyName("version")] string Version
);
