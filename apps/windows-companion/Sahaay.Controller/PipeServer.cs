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
                var pipe = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous,
                    65536,
                    65536
                );

                await pipe.WaitForConnectionAsync(_cts.Token);
                _ = Task.Run(() => HandleClientSessionAsync(pipe, _cts.Token));
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[PipeServer] Server listener error: {ex.Message}");
                await Task.Delay(200, _cts.Token);
            }
        }
    }

    private static readonly System.Text.UTF8Encoding Utf8NoBom = new(false);

    private async Task HandleClientSessionAsync(NamedPipeServerStream pipe, CancellationToken ct)
    {
        using (pipe)
        {
            try
            {
                using var reader = new StreamReader(pipe, Utf8NoBom, detectEncodingFromByteOrderMarks: false, bufferSize: 4096, leaveOpen: true);
                using var writer = new StreamWriter(pipe, Utf8NoBom, bufferSize: 4096, leaveOpen: true) { AutoFlush = true };

                while (pipe.IsConnected && !ct.IsCancellationRequested)
                {
                    string? line;
                    try
                    {
                        line = await reader.ReadLineAsync(ct);
                    }
                    catch (IOException ex) when (IsBrokenPipe(ex))
                    {
                        break;
                    }
                    catch (InvalidOperationException ex) when (ex.Message.Contains("disconnected", StringComparison.OrdinalIgnoreCase))
                    {
                        break;
                    }

                    if (line == null) break;

                    var response = HandleRequest(line);
                    string jsonResponse = JsonSerializer.Serialize(response);
                    await writer.WriteLineAsync(jsonResponse.AsMemory(), ct);
                    await writer.FlushAsync(ct);
                }

                if (pipe.IsConnected)
                {
                    try { pipe.Disconnect(); } catch { }
                }
            }
            catch (OperationCanceledException)
            {
            }
            catch (IOException ex) when (IsBrokenPipe(ex))
            {
            }
            catch (InvalidOperationException ex) when (ex.Message.Contains("disconnected", StringComparison.OrdinalIgnoreCase))
            {
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[PipeServer] Connection session error: {ex.GetType().Name}: {ex.Message}");
            }
        }
    }

    public static bool IsBrokenPipe(IOException ex)
    {
        return ex.HResult == unchecked((int)0x8007006D) ||
               ex.Message.Contains("Pipe is broken", StringComparison.OrdinalIgnoreCase) ||
               ex.Message.Contains("broken pipe", StringComparison.OrdinalIgnoreCase);
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

                "launch_application" => HandleLaunchApplication(request),

                "click_control" => HandleClickControl(request),

                "focus_window" => HandleFocusWindow(request),

                "set_system_volume" => HandleSetSystemVolume(request),

                "get_system_volume" => HandleGetSystemVolume(request),

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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
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

    private static readonly Dictionary<string, string> AllowedApplicationMap = new(StringComparer.OrdinalIgnoreCase)
    {
        { "calc", "calc.exe" },
        { "calc.exe", "calc.exe" },
        { "calculator", "calc.exe" },
        { "notepad", "notepad.exe" },
        { "notepad.exe", "notepad.exe" },
        { "explorer", "explorer.exe" },
        { "explorer.exe", "explorer.exe" },
        { "chrome", "chrome.exe" },
        { "chrome.exe", "chrome.exe" },
        { "edge", "msedge.exe" },
        { "msedge", "msedge.exe" },
        { "msedge.exe", "msedge.exe" },
        { "code", "code.cmd" },
        { "code.cmd", "code.cmd" },
        { "vscode", "code.cmd" },
        { "paint", "mspaint.exe" },
        { "mspaint", "mspaint.exe" },
        { "terminal", "wt.exe" },
        { "wt", "wt.exe" },
        { "taskmgr", "taskmgr.exe" },
        { "control", "control.exe" },
        { "write", "write.exe" },
        { "wordpad", "write.exe" }
    };

    private static IpcMessageResponse HandleLaunchApplication(IpcMessageRequest request)
    {
        string? appName = null;
        if (request.Parameters != null && request.Parameters.TryGetValue("application", out var appObj) && appObj != null)
        {
            appName = appObj.ToString();
        }
        else if (request.Parameters != null && request.Parameters.TryGetValue("appName", out var appNameObj) && appNameObj != null)
        {
            appName = appNameObj.ToString();
        }

        if (string.IsNullOrWhiteSpace(appName))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'application'.");
        }

        if (!AllowedApplicationMap.TryGetValue(appName.Trim(), out string? exeName))
        {
            return new IpcMessageResponse(
                request.Id,
                request.Command,
                false,
                null,
                $"Application '{appName}' is not in the authorized launch allowlist. Shell execution of arbitrary programs is prohibited."
            );
        }

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = exeName,
                UseShellExecute = true
            };
            using var proc = Process.Start(startInfo);
            int procId = proc?.Id ?? 0;

            // Give process a moment to initialize its top-level window
            Thread.Sleep(300);

            long detectedHwnd = 0;
            string detectedTitle = string.Empty;
            string searchProcess = Path.GetFileNameWithoutExtension(exeName);

            // Wait up to 3 seconds for the window to initialize and be discovered
            for (int retry = 0; retry < 10; retry++)
            {
                Thread.Sleep(300);
                var openWindows = WindowDiscovery.GetOpenWindows();
                foreach (var win in openWindows)
                {
                    bool isMatch = win.ProcessName.Equals(searchProcess, StringComparison.OrdinalIgnoreCase) ||
                                   win.ProcessName.Contains(searchProcess, StringComparison.OrdinalIgnoreCase) ||
                                   win.Title.Contains(searchProcess, StringComparison.OrdinalIgnoreCase);

                    if (!isMatch && searchProcess.Equals("calc", StringComparison.OrdinalIgnoreCase))
                    {
                        isMatch = win.ProcessName.Contains("Calculator", StringComparison.OrdinalIgnoreCase) ||
                                  win.Title.Contains("Calculator", StringComparison.OrdinalIgnoreCase) ||
                                  (win.ProcessName.Contains("ApplicationFrameHost", StringComparison.OrdinalIgnoreCase) && win.Title.Contains("Calculator", StringComparison.OrdinalIgnoreCase));
                    }

                    if (isMatch && win.Hwnd > 0)
                    {
                        detectedHwnd = win.Hwnd;
                        detectedTitle = win.Title;
                        break;
                    }
                }
                if (detectedHwnd > 0) break;
            }

            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: true,
                Data: new
                {
                    isLaunched = true,
                    processName = exeName,
                    processId = procId,
                    hwnd = detectedHwnd,
                    windowTitle = detectedTitle
                },
                Error: null
            );
        }
        catch (Exception ex)
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, $"Failed to launch '{appName}': {ex.Message}");
        }
    }

    private static IpcMessageResponse HandleClickControl(IpcMessageRequest request)
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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
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

        var result = UiAutomationInspector.ClickControl(hwnd, targetId);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: result.Success,
            Data: new { verified = result.Success, targetId = result.TargetId },
            Error: result.Error
        );
    }

    private static IpcMessageResponse HandleFocusWindow(IpcMessageRequest request)
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

        if (hwnd <= 0)
        {
            var active = WindowDiscovery.GetActiveWindow();
            if (active != null)
            {
                hwnd = active.Hwnd;
            }
        }

        if (hwnd <= 0)
        {
            return new IpcMessageResponse(
                Id: request.Id,
                Command: request.Command,
                Success: false,
                Data: new { noExternalTarget = true },
                Error: "No external target window available."
            );
        }

        bool success = WindowDiscovery.FocusWindow(hwnd);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: success,
            Data: new { verified = success, hwnd },
            Error: success ? null : $"Could not focus window with HWND {hwnd}."
        );
    }

    private static IpcMessageResponse HandleSetSystemVolume(IpcMessageRequest request)
    {
        if (request.Parameters == null || (!request.Parameters.TryGetValue("volume", out var volObj) && !request.Parameters.TryGetValue("volumePercent", out volObj)))
        {
            return new IpcMessageResponse(request.Id, request.Command, false, null, "Missing required parameter 'volume' or 'volumePercent'.");
        }

        int targetVolume = 50;
        if (volObj is JsonElement jsonElem && jsonElem.TryGetInt32(out int parsedVol))
        {
            targetVolume = parsedVol;
        }
        else if (int.TryParse(volObj.ToString(), out int parsedStrVol))
        {
            targetVolume = parsedStrVol;
        }

        var result = SystemAudioService.SetVolume(targetVolume);
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: result.Success,
            Data: new
            {
                verified = result.Success,
                volumePercent = result.VolumePercent,
                previousVolumePercent = result.PreviousVolumePercent,
                isMuted = result.IsMuted
            },
            Error: result.Error
        );
    }

    private static IpcMessageResponse HandleGetSystemVolume(IpcMessageRequest request)
    {
        var result = SystemAudioService.GetVolume();
        return new IpcMessageResponse(
            Id: request.Id,
            Command: request.Command,
            Success: result.Success,
            Data: new
            {
                verified = result.Success,
                volumePercent = result.VolumePercent,
                isMuted = result.IsMuted
            },
            Error: result.Error
        );
    }
}

