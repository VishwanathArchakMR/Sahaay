using System;
using System.Text.Json;
using Sahaay.Contracts;
using Sahaay.Controller;
using Xunit;

namespace Sahaay.Tests;

public class PipeServerTests
{
    [Fact]
    public void HandleRequest_Ping_ReturnsPong()
    {
        var req = new IpcMessageRequest("req-1", "ping", "sess-1", null, null, null);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.True(res.Success);
        Assert.Equal("ping", res.Command);
    }

    [Fact]
    public void HandleRequest_ShellCommands_ArePermanentlyDisabled()
    {
        var req = new IpcMessageRequest("req-2", "powershell_exec", "sess-1", null, null, null);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.False(res.Success);
        Assert.Contains("Shell execution is disabled", res.Error);
    }

    [Fact]
    public void HandleRequest_GetCapabilities_ReportsTrueCapabilities()
    {
        var req = new IpcMessageRequest("req-3", "get_capabilities", "sess-1", null, null, null);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.True(res.Success);
        var report = Assert.IsType<ControllerCapabilityReport>(res.Data);
        Assert.True(report.IsUiAutomationSupported);
        Assert.True(report.IsControlledCaptureSupported);
        Assert.True(report.IsShellExecutionDisabled);
    }

    [Fact]
    public void HandleRequest_SetControlText_FailsGracefully_WhenHwndMissing()
    {
        var req = new IpcMessageRequest("req-5", "set_control_text", "sess-1", null, null, null);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.False(res.Success);
        Assert.Contains("Missing required parameter 'hwnd'", res.Error);
    }

    [Fact]
    public void HandleRequest_GetControlText_FailsGracefully_WhenHwndMissing()
    {
        var req = new IpcMessageRequest("req-6", "get_control_text", "sess-1", null, null, null);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.False(res.Success);
        Assert.Contains("Missing required parameter 'hwnd'", res.Error);
    }

    [Fact]
    public void HandleRequest_LaunchApplication_RejectsUnauthorizedApps()
    {
        var parameters = new System.Collections.Generic.Dictionary<string, object>
        {
            { "application", "malicious_script.bat" }
        };
        var req = new IpcMessageRequest("req-7", "launch_application", "sess-1", null, null, parameters);
        string json = JsonSerializer.Serialize(req);

        var res = PipeServer.HandleRequest(json);

        Assert.False(res.Success);
        Assert.Contains("not in the authorized launch allowlist", res.Error);
    }

    [Fact]
    public void HandleRequest_SetAndGetSystemVolume_ReturnsValidVolumeState()
    {
        var setParams = new System.Collections.Generic.Dictionary<string, object>
        {
            { "volume", 60 }
        };
        var setReq = new IpcMessageRequest("req-8", "set_system_volume", "sess-1", null, null, setParams);
        var setRes = PipeServer.HandleRequest(JsonSerializer.Serialize(setReq));

        Assert.True(setRes.Success);

        var getReq = new IpcMessageRequest("req-9", "get_system_volume", "sess-1", null, null, null);
        var getRes = PipeServer.HandleRequest(JsonSerializer.Serialize(getReq));

        Assert.True(getRes.Success);
    }

    [Fact]
    public void HandleRequest_ClickControl_FailsGracefully_WhenHwndMissing()
    {
        var req = new IpcMessageRequest("req-10", "click_control", "sess-1", null, null, null);
        var res = PipeServer.HandleRequest(JsonSerializer.Serialize(req));

        Assert.False(res.Success);
        Assert.Contains("Missing required parameter 'hwnd'", res.Error);
    }

    [Fact]
    public void IsBrokenPipe_IdentifiesStandardDisconnectionErrors()
    {
        var ex1 = new System.IO.IOException("Pipe is broken.");
        var ex2 = new System.IO.IOException("The pipe has been ended.", unchecked((int)0x8007006D));
        var ex3 = new System.IO.IOException("Another disk failure");

        Assert.True(PipeServer.IsBrokenPipe(ex1));
        Assert.True(PipeServer.IsBrokenPipe(ex2));
        Assert.False(PipeServer.IsBrokenPipe(ex3));
    }

    [Fact]
    public void HandleRequest_MalformedJson_ReturnsErrorGracefully()
    {
        string malformed = "{ this is not json }";
        var res = PipeServer.HandleRequest(malformed);

        Assert.False(res.Success);
        Assert.Contains("Malformed JSON request", res.Error);
    }

    [Fact]
    public void HandleRequest_EmptyOrWhitespaceJson_ReturnsError()
    {
        var res = PipeServer.HandleRequest("");
        Assert.False(res.Success);
    }

    [Fact]
    public void HandleRequest_RepeatedPings_ReturnSuccess()
    {
        for (int i = 0; i < 10; i++)
        {
            var req = new IpcMessageRequest($"ping-{i}", "ping", "sess-1", null, null, null);
            var res = PipeServer.HandleRequest(JsonSerializer.Serialize(req));
            Assert.True(res.Success);
            Assert.Equal("ping", res.Command);
            Assert.Equal($"ping-{i}", res.Id);
        }
    }

    [Fact]
    public void HandleRequest_SequentialVariedCommands_MaintainIndependentContext()
    {
        var pingReq = new IpcMessageRequest("req-ping", "ping", "sess-1", null, null, null);
        var pingRes = PipeServer.HandleRequest(JsonSerializer.Serialize(pingReq));
        Assert.True(pingRes.Success);

        var capsReq = new IpcMessageRequest("req-caps", "get_capabilities", "sess-1", null, null, null);
        var capsRes = PipeServer.HandleRequest(JsonSerializer.Serialize(capsReq));
        Assert.True(capsRes.Success);

        var badReq = new IpcMessageRequest("req-bad", "unauthorized_command", "sess-1", null, null, null);
        var badRes = PipeServer.HandleRequest(JsonSerializer.Serialize(badReq));
        Assert.False(badRes.Success);
        Assert.Contains("forbidden", badRes.Error);
    }
}

