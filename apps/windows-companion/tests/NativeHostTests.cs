using System;
using System.IO;
using System.Text;
using System.Text.Json;
using Sahaay.Contracts;
using Xunit;

namespace Sahaay.Tests;

public class NativeHostTests
{
    [Fact]
    public void ReadMessage_WithValidPayload_ReturnsRequest()
    {
        var request = new NativeHostMessageRequest("ping", "session-1", null, null);
        string json = JsonSerializer.Serialize(request);
        byte[] payloadBytes = Encoding.UTF8.GetBytes(json);
        byte[] lengthBytes = BitConverter.GetBytes(payloadBytes.Length);

        using var ms = new MemoryStream();
        ms.Write(lengthBytes, 0, 4);
        ms.Write(payloadBytes, 0, payloadBytes.Length);
        ms.Position = 0;

        var result = NativeHost.Program.ReadMessage(ms);

        Assert.NotNull(result);
        Assert.Equal("ping", result.Command);
        Assert.Equal("session-1", result.SessionId);
    }

    [Fact]
    public void ReadMessage_WithOversizedLength_ThrowsInvalidOperationException()
    {
        // 2MB is over the 1MB limit
        int oversizedLength = 2 * 1024 * 1024;
        byte[] lengthBytes = BitConverter.GetBytes(oversizedLength);

        using var ms = new MemoryStream();
        ms.Write(lengthBytes, 0, 4);
        ms.Position = 0;

        Assert.Throws<InvalidOperationException>(() => NativeHost.Program.ReadMessage(ms));
    }

    [Fact]
    public void ProcessRequest_WithUnknownCommand_RejectsWithFailure()
    {
        var request = new NativeHostMessageRequest("arbitrary_shell_command", "session-1", null, null);
        var response = NativeHost.Program.ProcessRequest(request);

        Assert.False(response.Success);
        Assert.Contains("rejects unallowlisted operations", response.Error);
    }

    [Fact]
    public void ProcessRequest_Ping_ReturnsSuccess()
    {
        var request = new NativeHostMessageRequest("ping", "session-1", null, null);
        var response = NativeHost.Program.ProcessRequest(request);

        Assert.True(response.Success);
        Assert.Equal("ping", response.Command);
    }
}
