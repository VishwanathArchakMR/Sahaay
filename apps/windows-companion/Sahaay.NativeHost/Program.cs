using System;
using System.IO;
using System.Text;
using System.Text.Json;
using Sahaay.Contracts;

namespace Sahaay.NativeHost;

public class Program
{
    private const int MaxPayloadBytes = 1024 * 1024; // 1MB

    public static void Main(string[] args)
    {
        using var stdin = Console.OpenStandardInput();
        using var stdout = Console.OpenStandardOutput();

        while (true)
        {
            var request = ReadMessage(stdin);
            if (request == null) break;

            var response = ProcessRequest(request);
            WriteMessage(stdout, response);
        }
    }

    public static NativeHostMessageRequest? ReadMessage(Stream stream)
    {
        byte[] lengthBytes = new byte[4];
        int bytesRead = stream.Read(lengthBytes, 0, 4);
        if (bytesRead < 4) return null;

        int messageLength = BitConverter.ToInt32(lengthBytes, 0);
        if (messageLength <= 0 || messageLength > MaxPayloadBytes)
        {
            throw new InvalidOperationException($"Invalid message length: {messageLength} bytes (Max: {MaxPayloadBytes})");
        }

        byte[] messageBuffer = new byte[messageLength];
        int totalRead = 0;
        while (totalRead < messageLength)
        {
            int read = stream.Read(messageBuffer, totalRead, messageLength - totalRead);
            if (read == 0) break;
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

        return request.Command switch
        {
            "ping" => new NativeHostMessageResponse(true, "ping", new { status = "pong" }, null),
            "get_capabilities" => new NativeHostMessageResponse(true, "get_capabilities", new ControllerCapabilityReport(true, true, true, "0.1.0-foundation"), null),
            "get_active_window" => new NativeHostMessageResponse(false, "get_active_window", null, "Windows companion interaction scaffolded for Stage 02."),
            _ => new NativeHostMessageResponse(false, request.Command, null, $"Unknown command '{request.Command}'. Native host rejects unallowlisted operations.")
        };
    }
}
