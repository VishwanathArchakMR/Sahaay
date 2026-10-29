using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;
using Sahaay.Contracts;

namespace Sahaay.NativeHost;

public class Program
{
    private const int MaxPayloadBytes = 1024 * 1024; // 1MB limit
    private const string PipeName = "SahaayBrowserBridgePipe";
    private static readonly object StdoutLock = new();
    private static readonly ConcurrentDictionary<string, TaskCompletionSource<string>> PendingIpcResponses = new();
    private static volatile bool _isBrowserAttached = false;
    private static Stream? _activeStdout;

    // Configured permitted extension IDs (Chrome and Edge origins)
    private static readonly HashSet<string> AllowedExtensionOrigins = new()
    {
        "chrome-extension://sahaay-dev-extension-id/",
        "chrome-extension://knldjmfmopnpolahpmmgbagdohdnhkik/", // Common unpacked dev ID pattern
        "extension://knldjmfmopnpolahpmmgbagdohdnhkik/",        // Microsoft Edge native scheme
        "chrome-extension://nokchmadkhaghgooijgkgpheoieaibdp/", // Unpacked repo path ID
        "extension://nokchmadkhaghgooijgkgpheoieaibdp/",        // Unpacked repo path Edge scheme
    };

    public static async Task Main(string[] args)
    {
        // 1. Diagnostics / Verification CLI mode
        if (args.Any(a => a.Equals("--test", StringComparison.OrdinalIgnoreCase) ||
                          a.Equals("--verify", StringComparison.OrdinalIgnoreCase) ||
                          a.Equals("--diagnostics", StringComparison.OrdinalIgnoreCase)))
        {
            RunDiagnostics();
            return;
        }

        Console.Error.WriteLine("[NativeHost] Sahaay Chrome/Edge Native Messaging Bridge Initializing...");

        using var stdin = Console.OpenStandardInput();
        using var stdout = Console.OpenStandardOutput();
        _activeStdout = stdout;

        using var cts = new CancellationTokenSource();

        // 2. Start IPC Named Pipe Server for Orchestrator/Python calls
        var pipeTask = Task.Run(() => RunPipeServerAsync(cts.Token));

        // 3. Main loop reading messages from Chrome/Edge via standard input
        try
        {
            while (!cts.Token.IsCancellationRequested)
            {
                string? rawJson;
                try
                {
                    rawJson = ReadRawMessage(stdin);
                    if (rawJson == null)
                    {
                        Console.Error.WriteLine("[NativeHost] Standard input closed by browser. Terminating bridge.");
                        break;
                    }
                    _isBrowserAttached = true;
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[NativeHost] Read error on stdin: {ex.Message}");
                    continue;
                }

                // Check if this is a response to an ongoing IPC request from Python/Desktop
                try
                {
                    using var doc = JsonDocument.Parse(rawJson);
                    if (doc.RootElement.TryGetProperty("id", out var idProp) && idProp.GetString() is { } id &&
                        PendingIpcResponses.TryRemove(id, out var tcs))
                    {
                        tcs.TrySetResult(rawJson);
                        continue;
                    }

                    // Otherwise, it is an inbound command from the extension
                    var request = JsonSerializer.Deserialize<NativeHostMessageRequest>(rawJson);
                    if (request != null)
                    {
                        var response = ProcessRequest(request);
                        WriteMessage(stdout, response);
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[NativeHost] Processing error: {ex.Message}");
                    var errResponse = new NativeHostMessageResponse(false, "error", null, ex.Message);
                    WriteMessage(stdout, errResponse);
                }
            }
        }
        finally
        {
            _isBrowserAttached = false;
            cts.Cancel();
            await Task.WhenAny(pipeTask, Task.Delay(500));
        }
    }

    private static async Task RunPipeServerAsync(CancellationToken ct)
    {
        Console.Error.WriteLine($"[NativeHost] Starting Named Pipe Server: \\\\.\\pipe\\{PipeName}");

        while (!ct.IsCancellationRequested)
        {
            try
            {
                using var pipeServer = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous
                );

                await pipeServer.WaitForConnectionAsync(ct);

                using var reader = new StreamReader(pipeServer, Encoding.UTF8);
                using var writer = new StreamWriter(pipeServer, Encoding.UTF8) { AutoFlush = true };

                string? line = await reader.ReadLineAsync(ct);
                if (string.IsNullOrWhiteSpace(line)) continue;

                string responseJson = await HandleIpcCommandAsync(line);
                await writer.WriteLineAsync(responseJson.AsMemory(), ct);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[NativeHost] Pipe server error: {ex.Message}");
                await Task.Delay(200, ct);
            }
        }
    }

    public static async Task<string> HandleIpcCommandAsync(string line)
    {
        try
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            string command = root.TryGetProperty("command", out var cProp) ? cProp.GetString() ?? "" : "";
            string id = root.TryGetProperty("id", out var idProp) ? idProp.GetString() ?? Guid.NewGuid().ToString("N") : Guid.NewGuid().ToString("N");

            // Direct local ping / status check without needing active browser tab
            if (command.Equals("ping", StringComparison.OrdinalIgnoreCase))
            {
                return JsonSerializer.Serialize(new
                {
                    id,
                    success = true,
                    command = "ping",
                    data = new
                    {
                        nativeHostConnected = true,
                        isBrowserAttached = _isBrowserAttached,
                        pid = Environment.ProcessId,
                        timestamp = DateTime.UtcNow
                    }
                });
            }

            if (command.Equals("get_status", StringComparison.OrdinalIgnoreCase))
            {
                return JsonSerializer.Serialize(new
                {
                    id,
                    success = true,
                    command = "get_status",
                    data = new
                    {
                        nativeHostConnected = true,
                        isBrowserAttached = _isBrowserAttached,
                        pipeName = PipeName,
                        version = "0.2.0-m08",
                        pid = Environment.ProcessId
                    }
                });
            }

            // Commands targeting active browser tab
            if (!_isBrowserAttached || _activeStdout == null)
            {
                return JsonSerializer.Serialize(new
                {
                    id,
                    success = false,
                    command,
                    error = "Browser extension is not currently connected. Please ensure Chrome or Edge is open with Sahaay Browser Bridge enabled."
                });
            }

            // Create pending response waiter
            var tcs = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            PendingIpcResponses[id] = tcs;

            // Send command message to Chrome via stdout
            lock (StdoutLock)
            {
                WriteRawJson(_activeStdout, line);
            }

            // Wait for response from extension (with 5 second timeout)
            var completedTask = await Task.WhenAny(tcs.Task, Task.Delay(5000));
            if (completedTask == tcs.Task)
            {
                return await tcs.Task;
            }
            else
            {
                PendingIpcResponses.TryRemove(id, out _);
                return JsonSerializer.Serialize(new
                {
                    id,
                    success = false,
                    command,
                    error = $"Browser command '{command}' timed out after 5000ms. Active tab did not respond."
                });
            }
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(new
            {
                success = false,
                error = $"Internal error handling browser command: {ex.Message}"
            });
        }
    }

    public static string? ReadRawMessage(Stream stream)
    {
        byte[] lengthBytes = new byte[4];
        int bytesRead = stream.Read(lengthBytes, 0, 4);
        if (bytesRead == 0) return null;
        if (bytesRead < 4)
        {
            throw new InvalidOperationException($"Truncated message length prefix: read only {bytesRead} bytes.");
        }

        int messageLength = BitConverter.ToInt32(lengthBytes, 0);
        if (messageLength <= 0 || messageLength > MaxPayloadBytes)
        {
            throw new InvalidOperationException($"Invalid message length: {messageLength} bytes (Allowed max: {MaxPayloadBytes})");
        }

        byte[] messageBuffer = new byte[messageLength];
        int totalRead = 0;
        while (totalRead < messageLength)
        {
            int read = stream.Read(messageBuffer, totalRead, messageLength - totalRead);
            if (read == 0)
            {
                throw new InvalidOperationException($"Premature EOF encountered: expected {messageLength} bytes, read {totalRead}.");
            }
            totalRead += read;
        }

        return Encoding.UTF8.GetString(messageBuffer);
    }

    public static NativeHostMessageRequest? ReadMessage(Stream stream)
    {
        string? raw = ReadRawMessage(stream);
        if (raw == null) return null;
        return JsonSerializer.Deserialize<NativeHostMessageRequest>(raw);
    }

    public static void WriteRawJson(Stream stream, string json)
    {
        byte[] messageBuffer = Encoding.UTF8.GetBytes(json);
        byte[] lengthBytes = BitConverter.GetBytes(messageBuffer.Length);

        stream.Write(lengthBytes, 0, 4);
        stream.Write(messageBuffer, 0, messageBuffer.Length);
        stream.Flush();
    }

    public static void WriteMessage(Stream stream, NativeHostMessageResponse response)
    {
        lock (StdoutLock)
        {
            string json = JsonSerializer.Serialize(response);
            WriteRawJson(stream, json);
        }
    }

    public static NativeHostMessageResponse ProcessRequest(NativeHostMessageRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Command))
        {
            return new NativeHostMessageResponse(false, "unknown", null, "Command cannot be empty.");
        }

        if (string.IsNullOrWhiteSpace(request.SessionId))
        {
            return new NativeHostMessageResponse(false, request.Command, null, "SessionId is required.");
        }

        string cmd = request.Command.ToLowerInvariant();

        return cmd switch
        {
            "ping" => new NativeHostMessageResponse(true, "ping", new { status = "pong", timestamp = DateTime.UtcNow }, null),

            "get_capabilities" => new NativeHostMessageResponse(
                true,
                "get_capabilities",
                new ControllerCapabilityReport(true, true, true, "0.2.0-vertical-slice", Environment.ProcessId),
                null
            ),

            "get_active_window" or "list_open_windows" or "inspect_window_elements" or "capture_window_screenshot" or "set_control_text" or "get_control_text" => ForwardToController(request),

            _ => new NativeHostMessageResponse(
                false,
                request.Command,
                null,
                $"Command '{request.Command}' is rejected. Native host rejects unallowlisted operations."
            )
        };
    }

    private static NativeHostMessageResponse ForwardToController(NativeHostMessageRequest request)
    {
        try
        {
            using var client = new NamedPipeClientStream(".", "SahaayControllerPipe", PipeDirection.InOut);
            client.Connect(1500); // 1.5s timeout

            using var writer = new StreamWriter(client) { AutoFlush = true };
            using var reader = new StreamReader(client);

            var ipcReq = new IpcMessageRequest(
                Id: Guid.NewGuid().ToString("N"),
                Command: request.Command,
                SessionId: request.SessionId,
                TaskId: request.TaskId,
                Token: null,
                Parameters: request.Parameters
            );

            writer.WriteLine(JsonSerializer.Serialize(ipcReq));
            string? responseLine = reader.ReadLine();
            if (responseLine == null)
            {
                return new NativeHostMessageResponse(false, request.Command, null, "Empty response from Sahaay controller.");
            }

            var ipcRes = JsonSerializer.Deserialize<IpcMessageResponse>(responseLine);
            return new NativeHostMessageResponse(
                ipcRes?.Success ?? false,
                request.Command,
                ipcRes?.Data,
                ipcRes?.Error
            );
        }
        catch (TimeoutException)
        {
            return new NativeHostMessageResponse(false, request.Command, null, "Sahaay controller daemon is not running or timed out.");
        }
        catch (Exception ex)
        {
            return new NativeHostMessageResponse(false, request.Command, null, $"Forwarding to controller failed: {ex.Message}");
        }
    }

    private static void RunDiagnostics()
    {
        const string hostName = "com.sahaay.nativehost";
        string? chromePath = null;
        string? edgePath = null;

        try
        {
            using var chromeKey = Registry.CurrentUser.OpenSubKey($@"Software\Google\Chrome\NativeMessagingHosts\{hostName}");
            chromePath = chromeKey?.GetValue("")?.ToString();
        }
        catch { }

        try
        {
            using var edgeKey = Registry.CurrentUser.OpenSubKey($@"Software\Microsoft\Edge\NativeMessagingHosts\{hostName}");
            edgePath = edgeKey?.GetValue("")?.ToString();
        }
        catch { }

        bool chromeManifestExists = !string.IsNullOrEmpty(chromePath) && File.Exists(chromePath);
        bool edgeManifestExists = !string.IsNullOrEmpty(edgePath) && File.Exists(edgePath);

        // Real inspection of on-disk manifest JSON
        string? manifestExePath = null;
        bool manifestExeExists = false;
        List<string> origins = new();

        string? validManifestPath = chromeManifestExists ? chromePath : (edgeManifestExists ? edgePath : null);
        if (validManifestPath != null)
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(validManifestPath));
                if (doc.RootElement.TryGetProperty("path", out var pProp))
                {
                    manifestExePath = pProp.GetString();
                    manifestExeExists = !string.IsNullOrEmpty(manifestExePath) && File.Exists(manifestExePath);
                }
                if (doc.RootElement.TryGetProperty("allowed_origins", out var oProp) && oProp.ValueKind == JsonValueKind.Array)
                {
                    foreach (var elem in oProp.EnumerateArray())
                    {
                        if (elem.GetString() is { } s) origins.Add(s);
                    }
                }
            }
            catch { }
        }

        var report = new
        {
            verified = (chromeManifestExists || edgeManifestExists) && (manifestExeExists || Environment.ProcessPath != null),
            hostName,
            executablePath = Environment.ProcessPath,
            manifestExecutablePath = manifestExePath,
            manifestExecutableExists = manifestExeExists,
            chrome = new { registered = chromeManifestExists, manifestPath = chromePath },
            edge = new { registered = edgeManifestExists, manifestPath = edgePath },
            allowedOrigins = origins,
            supportedBrowsers = new[] { "Google Chrome", "Microsoft Edge" }
        };

        Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
    }
}
