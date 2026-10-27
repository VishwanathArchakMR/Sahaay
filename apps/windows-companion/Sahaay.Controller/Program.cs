using System;
using System.Text.Json;
using System.Threading.Tasks;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public class Program
{
    public static async Task Main(string[] args)
    {
        Console.WriteLine("==================================================");
        Console.WriteLine("  Sahaay Windows Controller Daemon (v0.2.0)");
        Console.WriteLine("  Process ID: " + Environment.ProcessId);
        Console.WriteLine("  Named Pipe: \\\\.\\pipe\\" + PipeServer.PipeName);
        Console.WriteLine("  Security: Shell and arbitrary execution DISABLED.");
        Console.WriteLine("==================================================");

        var capabilities = new ControllerCapabilityReport(
            IsUiAutomationSupported: true,
            IsControlledCaptureSupported: true,
            IsShellExecutionDisabled: true,
            Version: "0.2.0-vertical-slice",
            ProcessId: Environment.ProcessId
        );

        string json = JsonSerializer.Serialize(capabilities, new JsonSerializerOptions { WriteIndented = true });
        Console.WriteLine($"Capabilities:\n{json}");

        var server = new PipeServer();
        Console.CancelKeyPress += (s, e) =>
        {
            Console.WriteLine("[Controller] Shutdown requested via Ctrl+C.");
            server.Stop();
            e.Cancel = true;
        };

        await server.StartAsync();
    }
}
