using System;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public class PipeServer
{
    public const string PipeName = "SahaayControllerPipe";
    private readonly CancellationTokenSource _cts = new();

    public void Stop() => _cts.Cancel();

    public async Task StartAsync()
    {
        Console.WriteLine($"[PipeServer] Starting Named Pipe Server: \\\\.\\pipe\\{PipeName}");

        while (!_cts.IsCancellationRequested)
        {
            try
            {
                using var pipe = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous
                );

                Console.WriteLine("[PipeServer] Waiting for client connection...");
                await pipe.WaitForConnectionAsync(_cts.Token);
                Console.WriteLine("[PipeServer] Client connected.");

                using var reader = new StreamReader(pipe);
                using var writer = new StreamWriter(pipe) { AutoFlush = true };

                while (pipe.IsConnected && !_cts.IsCancellationRequested)
                {
                    string? line = await reader.ReadLineAsync(_cts.Token);
                    if (line == null) break;

                    var response = HandleRequest(line);
                    string jsonResponse = JsonSerializer.Serialize(response);
                    await writer.WriteLineAsync(jsonResponse.AsMemory(), _cts.Token);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[PipeServer] Connection error: {ex.Message}");
            }
        }
    }

    public static IpcMessageResponse HandleRequest(string jsonRequest)
    {
        IpcMessageRequest? request = null;
        try
        {
            request = JsonSerializer.Deserialize<IpcMessageRequest>(jsonRequest);
        }
        catch (Exception ex)
        {
            return new IpcMessageResponse(
                Id: Guid.NewGuid().ToString("N"),
                Command: "unknown",
                Success: false,
                Data: null,
                Error: $"Malformed JSON request: {ex.Message}"
            );
        }

        if (request == null)
        {
            return new IpcMessageResponse(
                Id: Guid.NewGuid().ToString("N"),
                Command: "unknown",
                Success: false,
                Data: null,
                Error: "Null request payload."
            );
        }

        string cmd = request.Command.ToLowerInvariant();

        try
        {
            return cmd switch
            {
                "ping" => new IpcMessageResponse(
                    Id: request.Id,
                    Command: request.Command,
                    Success: true,
                    Data: new { status = "pong", timestamp = DateTime.UtcNow },
                    Error: null
                ),

                "get_capabilities" => new IpcMessageResponse(
                    Id: request.Id,
                    Command: request.Command,
                    Success: true,
                    Data: new ControllerCapabilityReport(
                        IsUiAutomationSupported: true,
                        IsControlledCaptureSupported: true,
                        IsShellExecutionDisabled: true,
                        Version: "0.2.0-vertical-slice",
                        ProcessId: Environment.ProcessId
                    ),
                    Error: null
                ),

                "list_open_windows" => new IpcMessageResponse(
                    Id: request.Id,
                    Command: request.Command,
                    Success: true,
                    Data: WindowDiscovery.GetOpenWindows(),
                    Error: null
                ),

                "get_active_window" => new IpcMessageResponse(
                    Id: request.Id,
                    Command: request.Command,
                    Success: true,
                    Data: WindowDiscovery.GetActiveWindow(),
                    Error: null
                ),

                "inspect_window_elements" => HandleInspectWindow(request),

                "capture_window_screenshot" => HandleCaptureScreenshot(request),

                "set_control_text" => HandleSetControlText(request),

                "get_control_text" => HandleGetControlText(request),

                _ => new IpcMessageResponse(
                    Id: request.Id,
                    Command: request.Command,
                    Success: false,
                    Data: null,
                    Error: $"Command '{request.Command}' is forbidden or not allowlisted. Shell execution is disabled."
                )
            };
        }
        catch (Exception ex)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: null,
                Error: $"Operation failed: {ex.Message}"
            );
        }
    }

    private static IpcMessageResponse HandleInspectWindow(IpcMessageRequest request)
    {
        if (request.Parameters == null || !request.Parameters.TryGetValue("hwnd", out var hwndObj))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'hwnd'.");
        }

        long hwnd = 0;
        if (hwndObj is JsonElement jsonElem && jsonElem.TryGetInt64(out long parsedHwnd))
        {
            hwnd = parsedHwnd;
        }
        else if (long.TryParse(hwndObj.ToString(), out long parsedStrHwnd))
        {
            hwnd = parsedStrHwnd;
        }

        var elements = UiAutomationInspector.InspectWindow(hwnd);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: true,
            Data: elements,
            Error: null
        );
    }

    private static IpcMessageResponse HandleCaptureScreenshot(IpcMessageRequest request)
    {
        if (request.Parameters == null || !request.Parameters.TryGetValue("hwnd", out var hwndObj))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'hwnd'.");
        }

        long hwnd = 0;
        if (hwndObj is JsonElement jsonElem && jsonElem.TryGetInt64(out long parsedHwnd))
        {
            hwnd = parsedHwnd;
        }
        else if (long.TryParse(hwndObj.ToString(), out long parsedStrHwnd))
        {
            hwnd = parsedStrHwnd;
        }

        string outputDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "..", "data", "temp_media");
        if (request.Parameters.TryGetValue("outputDir", out var dirObj) && dirObj != null)
        {
            outputDir = dirObj.ToString()!;
        }

        string fullPath = Path.GetFullPath(outputDir);
        string savedPath = ScreenCaptureService.CaptureWindow(hwnd, fullPath);

        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: true,
            Data: new { filePath = savedPath, timestamp = DateTime.UtcNow },
            Error: null
        );
    }

    private static IpcMessageResponse HandleSetControlText(IpcMessageRequest request)
    {
        if (request.Parameters == null || !request.Parameters.TryGetValue("hwnd", out var hwndObj))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'hwnd'.");
        }

        long hwnd = 0;
        if (hwndObj is JsonElement jsonElem && jsonElem.TryGetInt64(out long parsedHwnd))
        {
            hwnd = parsedHwnd;
        }
        else if (long.TryParse(hwndObj.ToString(), out long parsedStrHwnd))
        {
            hwnd = parsedStrHwnd;
        }

        string? targetId = null;
        if (request.Parameters.TryGetValue("targetId", out var targetIdObj) && targetIdObj != null)
        {
            targetId = targetIdObj.ToString();
        }
        else if (request.Parameters.TryGetValue("automationId", out var autoIdObj) && autoIdObj != null)
        {
            targetId = autoIdObj.ToString();
        }

        string text = string.Empty;
        if (request.Parameters.TryGetValue("text", out var textObj) && textObj != null)
        {
            text = textObj.ToString()!;
        }

        var result = UiAutomationInspector.SetControlText(hwnd, targetId, text);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: result.Success,
            Data: new { verified = result.Success, value = result.ActualText, targetId },
            Error: result.Error
        );
    }

    private static IpcMessageResponse HandleGetControlText(IpcMessageRequest request)
    {
        if (request.Parameters == null || !request.Parameters.TryGetValue("hwnd", out var hwndObj))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'hwnd'.");
        }

        long hwnd = 0;
        if (hwndObj is JsonElement jsonElem && jsonElem.TryGetInt64(out long parsedHwnd))
        {
            hwnd = parsedHwnd;
        }
        else if (long.TryParse(hwndObj.ToString(), out long parsedStrHwnd))
        {
            hwnd = parsedStrHwnd;
        }

        string? targetId = null;
        if (request.Parameters.TryGetValue("targetId", out var targetIdObj) && targetIdObj != null)
        {
            targetId = targetIdObj.ToString();
        }
        else if (request.Parameters.TryGetValue("automationId", out var autoIdObj) && autoIdObj != null)
        {
            targetId = autoIdObj.ToString();
        }

        var result = UiAutomationInspector.GetControlText(hwnd, targetId);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: result.Success,
            Data: new { verified = result.Success, value = result.Text, targetId },
            Error: result.Error
        );
    }
}

