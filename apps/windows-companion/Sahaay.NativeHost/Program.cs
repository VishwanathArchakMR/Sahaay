using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Sahaay.Contracts;

namespace Sahaay.NativeHost;

public class Program
{
    private const int MaxPayloadBytes = 1024 * 1024; // 1MB limit

    // Configured permitted extension IDs
    private static readonly HashSet<string> AllowedExtensionOrigins = new()
    {
        "chrome-extension://sahaay-dev-extension-id/",
        "chrome-extension://knldjmfmopnpolahpmmgbagdohdnhkik/", // Common unpacked dev ID pattern
    };

    public static void Main(string[] args)
    {
        Console.Error.WriteLine("[NativeHost] Sahaay Chrome/Edge Native Messaging Bridge Initializing...");

        using var stdin = Console.OpenStandardInput();
        using var stdout = Console.OpenStandardOutput();

        while (true)
        {
            NativeHostMessageRequest? request;
            try
            {
                request = ReadMessage(stdin);
                if (request == null)
                {
                    Console.Error.WriteLine("[NativeHost] Standard input closed. Terminating bridge.");
                    break;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[NativeHost] Read error: {ex.Message}");
                var errResponse = new NativeHostMessageResponse(false, "unknown", null, ex.Message);
                WriteMessage(stdout, errResponse);
                continue;
            }

            var response = ProcessRequest(request);
            WriteMessage(stdout, response);
        }
    }

    public static NativeHostMessageRequest? ReadMessage(Stream stream)
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

        string json = Encoding.UTF8.GetString(messageBuffer);
        return JsonSerializer.Deserialize<NativeHostMessageRequest>(json);
    }

    public static void WriteMessage(Stream stream, NativeHostMessageResponse response)
    {
        string json = JsonSerializer.Serialize(response);
        byte[] messageBuffer = Encoding.UTF8.GetBytes(json);
        byte[] lengthBytes = BitConverter.GetBytes(messageBuffer.Length);

        stream.Write(lengthBytes, 0, 4);
        stream.Write(messageBuffer, 0, messageBuffer.Length);
        stream.Flush();
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

            "get_active_window" or "list_open_windows" => ForwardToController(request),

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
}
