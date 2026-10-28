using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public static class WindowDiscovery
{
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    private static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(IntPtr hWnd);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    private static readonly HashSet<string> ExcludedProcesses = new(StringComparer.OrdinalIgnoreCase)
    {
        "ShellExperienceHost",
        "SearchHost",
        "StartMenuExperienceHost",
        "TextInputHost"
    };

    public static List<WindowDescriptor> GetOpenWindows()
    {
        var windows = new List<WindowDescriptor>();

        EnumWindows((hWnd, lParam) =>
        {
            if (!IsWindowVisible(hWnd)) return true;

            int length = GetWindowTextLength(hWnd);
            if (length == 0) return true;

            var builder = new StringBuilder(length + 1);
            GetWindowText(hWnd, builder, builder.Capacity);
            string title = builder.ToString().Trim();

            if (string.IsNullOrWhiteSpace(title)) return true;

            GetWindowThreadProcessId(hWnd, out uint processId);
            string processName = "Unknown";
            try
            {
                using var proc = Process.GetProcessById((int)processId);
                processName = proc.ProcessName;
            }
            catch
            {
                // Process may have exited or have restricted access
            }

            if (ExcludedProcesses.Contains(processName)) return true;

            GetWindowRect(hWnd, out RECT rect);
            int width = rect.Right - rect.Left;
            int height = rect.Bottom - rect.Top;

            if (width < 50 || height < 50) return true; // Ignore tiny utility/tray windows

            bool isMinimized = IsIconic(hWnd);

            windows.Add(new WindowDescriptor(
                Hwnd: hWnd.ToInt64(),
                Title: title,
                ProcessName: processName,
                ProcessId: (int)processId,
                Bounds: new WindowBounds(rect.Left, rect.Top, width, height),
                IsVisible: true,
                IsMinimized: isMinimized
            ));

            return true;
        }, IntPtr.Zero);

        return windows;
    }

    public static WindowDescriptor? GetActiveWindow()
    {
        IntPtr hWnd = GetForegroundWindow();
        if (hWnd == IntPtr.Zero) return null;

        int length = GetWindowTextLength(hWnd);
        var builder = new StringBuilder(length + 1);
        if (length > 0)
        {
            GetWindowText(hWnd, builder, builder.Capacity);
        }
        string title = builder.ToString().Trim();

        GetWindowThreadProcessId(hWnd, out uint processId);
        string processName = "Unknown";
        try
        {
            using var proc = Process.GetProcessById((int)processId);
            processName = proc.ProcessName;
        }
        catch { }

        GetWindowRect(hWnd, out RECT rect);
        int width = rect.Right - rect.Left;
        int height = rect.Bottom - rect.Top;

        return new WindowDescriptor(
            Hwnd: hWnd.ToInt64(),
            Title: title,
            ProcessName: processName,
            ProcessId: (int)processId,
            Bounds: new WindowBounds(rect.Left, rect.Top, width, height),
            IsVisible: true,
            IsMinimized: IsIconic(hWnd)
        );
    }

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    public static bool FocusWindow(long hwnd)
    {
        try
        {
            var hWnd = new IntPtr(hwnd);
            return SetForegroundWindow(hWnd);
        }
        catch
        {
            return false;
        }
    }
}
