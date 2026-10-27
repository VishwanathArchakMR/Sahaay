using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public static class ScreenCaptureService
{
    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static string CaptureWindow(long hwnd, string outputDirectory)
    {
        Directory.CreateDirectory(outputDirectory);
        string filename = $"window_{hwnd}_{Guid.NewGuid():N}.png";
        string filePath = Path.Combine(outputDirectory, filename);

        var handle = new IntPtr(hwnd);
        GetWindowRect(handle, out RECT rect);
        int width = rect.Right - rect.Left;
        int height = rect.Bottom - rect.Top;

        if (width <= 0 || height <= 0)
        {
            throw new InvalidOperationException($"Invalid window bounds: {width}x{height}");
        }

        using var bitmap = new Bitmap(width, height);
        using var graphics = Graphics.FromImage(bitmap);
        graphics.CopyFromScreen(rect.Left, rect.Top, 0, 0, new Size(width, height), CopyPixelOperation.SourceCopy);
        bitmap.Save(filePath, ImageFormat.Png);

        return filePath;
    }
}
