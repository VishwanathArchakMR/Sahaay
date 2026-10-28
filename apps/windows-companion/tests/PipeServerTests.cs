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
}

