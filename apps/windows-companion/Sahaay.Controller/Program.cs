using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public class Program
{
    public static async Task Main(string[] args)
    {
        Console.WriteLine("Sahaay Windows Controller Daemon Initializing...");
        Console.WriteLine("Status: Stage 01 Skeleton (Deterministic Security Boundary)");
        Console.WriteLine("CRITICAL: General-purpose shell and PowerShell execution are strictly prohibited.");

        var capabilities = new ControllerCapabilityReport(
            IsUiAutomationSupported: true,
            IsControlledCaptureSupported: true,
            IsShellExecutionDisabled: true,
            Version: "0.1.0-foundation"
        );

        string json = JsonSerializer.Serialize(capabilities, new JsonSerializerOptions { WriteIndented = true });
        Console.WriteLine($"Capabilities:\n{json}");

        // In Stage 01, this process acts as verification baseline.
        // Stage 02 connects the interactive named pipe / loopback IPC listener.
    }

    /// <summary>
    /// Executes strictly allowlisted, typed operations. Arbitrary shell commands are permanently rejected.
    /// </summary>
    public static NativeHostMessageResponse ExecuteAllowlistedOperation(NativeHostMessageRequest request)
    {
        return request.Command switch
        {
            "ping" => new NativeHostMessageResponse(true, "ping", new { status = "pong", timestamp = DateTime.UtcNow }, null),
            "get_capabilities" => new NativeHostMessageResponse(true, "get_capabilities", new ControllerCapabilityReport(true, true, true, "0.1.0"), null),
            "discover_windows" => new NativeHostMessageResponse(false, "discover_windows", null, "UI Automation discovery scaffolded - requires Stage 02 interactive runtime."),
            "read_permitted_file" => new NativeHostMessageResponse(false, "read_permitted_file", null, "File access requires active Action Gate grant."),
            _ => new NativeHostMessageResponse(false, request.Command, null, $"Unknown or forbidden command '{request.Command}'. Shell execution is disabled.")
        };
    }
}
