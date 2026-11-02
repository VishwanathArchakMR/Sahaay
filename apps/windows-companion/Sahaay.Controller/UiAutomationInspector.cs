using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Automation;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public static class UiAutomationInspector
{
    private const int MaxElements = 80;
    private const int MaxDepth = 4;

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, string lParam);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, StringBuilder lParam);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    private const uint WM_SETTEXT = 0x000C;
    private const uint WM_GETTEXT = 0x000D;
    private const uint WM_GETTEXTLENGTH = 0x000E;

    public static List<UiElementDescriptor> InspectWindow(long hwnd)
    {
        var elements = new List<UiElementDescriptor>();

        try
        {
            var windowHandle = new IntPtr(hwnd);
            var rootElement = AutomationElement.FromHandle(windowHandle);

            if (rootElement == null) return elements;

            TraverseElement(rootElement, elements, currentDepth: 0);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[UIAutomation] Error inspecting HWND {hwnd}: {ex.Message}");
        }

        return elements;
    }

    private static void TraverseElement(AutomationElement element, List<UiElementDescriptor> list, int currentDepth)
    {
        if (element == null || list.Count >= MaxElements || currentDepth > MaxDepth) return;

        try
        {
            string name = element.Current.Name ?? string.Empty;
            string automationId = element.Current.AutomationId ?? string.Empty;
            string controlType = element.Current.ControlType.ProgrammaticName
                .Replace("ControlType.", string.Empty);
            var rect = element.Current.BoundingRectangle;
            bool isEnabled = element.Current.IsEnabled;
            bool isKeyboardFocusable = element.Current.IsKeyboardFocusable;

            var patterns = new List<string>();
            var supportedPatterns = element.GetSupportedPatterns();
            foreach (var p in supportedPatterns)
            {
                patterns.Add(p.ProgrammaticName.Replace("PatternIdentifiers.Pattern", string.Empty));
            }

            var bounds = new WindowBounds(
                Left: (int)rect.Left,
                Top: (int)rect.Top,
                Width: (int)rect.Width,
                Height: (int)rect.Height
            );

            // Filter out unnamed container elements with zero size
            if (!string.IsNullOrWhiteSpace(name) || !string.IsNullOrWhiteSpace(automationId) || bounds.Width > 0)
            {
                list.Add(new UiElementDescriptor(
                    AutomationId: automationId,
                    Name: name,
                    ControlType: controlType,
                    Bounds: bounds,
                    IsEnabled: isEnabled,
                    IsKeyboardFocusable: isKeyboardFocusable,
                    SupportedPatterns: patterns
                ));
            }

            // Enumerate children using TreeWalker
            var walker = TreeWalker.ControlViewWalker;
            var child = walker.GetFirstChild(element);
            while (child != null && list.Count < MaxElements)
            {
                TraverseElement(child, list, currentDepth + 1);
                child = walker.GetNextSibling(child);
            }
        }
        catch (ElementNotAvailableException)
        {
            // Element disappeared or invalidated
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[UIAutomation] Error reading element: {ex.Message}");
        }
    }

    public static (bool Success, string ActualText, string? Error) SetControlText(long hwnd, string? targetIdentifier, string text)
    {
        try
        {
            var windowHandle = new IntPtr(hwnd);
            var root = AutomationElement.FromHandle(windowHandle);
            if (root == null)
            {
                return (false, string.Empty, $"Window HWND {hwnd} not found.");
            }

            AutomationElement? target = null;
            if (!string.IsNullOrWhiteSpace(targetIdentifier))
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, targetIdentifier));
                if (target == null)
                {
                    target = root.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.NameProperty, targetIdentifier));
                }
            }

            if (target == null)
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Document));
            }

            if (target == null)
            {
                return (false, string.Empty, "No editable control found in target window.");
            }

            if (target.TryGetCurrentPattern(ValuePattern.Pattern, out object? patternObj) && patternObj is ValuePattern valPattern)
            {
                try
                {
                    valPattern.SetValue(text);
                    return (true, valPattern.Current.Value, null);
                }
                catch
                {
                    // Fall through to NativeWindowHandle
                }
            }

            int nativeHandle = target.Current.NativeWindowHandle;
            if (nativeHandle != 0)
            {
                SendMessage(new IntPtr(nativeHandle), WM_SETTEXT, IntPtr.Zero, text);
                return (true, text, null);
            }

            target.SetFocus();
            return (true, text, null);
        }
        catch (Exception ex)
        {
            return (false, string.Empty, $"Failed to set control text: {ex.Message}");
        }
    }

    public static (bool Success, string Text, string? Error) GetControlText(long hwnd, string? targetIdentifier)
    {
        try
        {
            var windowHandle = new IntPtr(hwnd);
            var root = AutomationElement.FromHandle(windowHandle);
            if (root == null)
            {
                return (false, string.Empty, $"Window HWND {hwnd} not found.");
            }

            AutomationElement? target = null;
            if (!string.IsNullOrWhiteSpace(targetIdentifier))
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, targetIdentifier))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.NameProperty, targetIdentifier));
            }

            if (target == null)
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, "CalculatorResults"))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Document))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text));
            }

            if (target == null)
            {
                return (false, string.Empty, "No readable control found in target window.");
            }

            if (target.TryGetCurrentPattern(ValuePattern.Pattern, out object? patternObj) && patternObj is ValuePattern valPattern)
            {
                string val = valPattern.Current.Value;
                if (!string.IsNullOrEmpty(val))
                {
                    return (true, val, null);
                }
            }

            if (target.TryGetCurrentPattern(TextPattern.Pattern, out object? textObj) && textObj is TextPattern textPattern)
            {
                string docText = textPattern.DocumentRange.GetText(-1);
                if (!string.IsNullOrEmpty(docText))
                {
                    return (true, docText, null);
                }
            }

            int nativeHandle = target.Current.NativeWindowHandle;
            if (nativeHandle != 0)
            {
                int len = (int)SendMessage(new IntPtr(nativeHandle), WM_GETTEXTLENGTH, IntPtr.Zero, IntPtr.Zero);
                if (len > 0)
                {
                    var sb = new StringBuilder(len + 1);
                    SendMessage(new IntPtr(nativeHandle), WM_GETTEXT, new IntPtr(len + 1), sb);
                    return (true, sb.ToString(), null);
                }
            }

            string text = target.Current.Name ?? string.Empty;
            if (text.StartsWith("Display is ", StringComparison.OrdinalIgnoreCase))
            {
                text = text.Substring("Display is ".Length).Trim().Replace(",", "");
            }
            return (true, text, null);
        }
        catch (Exception ex)
        {
            return (false, string.Empty, $"Failed to get control text: {ex.Message}");
        }
    }

    public static (bool Success, string TargetId, string? Error) ClickControl(long hwnd, string? targetIdentifier)
    {
        try
        {
            var windowHandle = new IntPtr(hwnd);
            var root = AutomationElement.FromHandle(windowHandle);
            if (root == null)
            {
                return (false, targetIdentifier ?? string.Empty, $"Window HWND {hwnd} not found.");
            }

            // Check if this is a Calculator multi-step expression like "125 multiplied by 48" or "125 * 48"
            if (!string.IsNullOrWhiteSpace(targetIdentifier) &&
                (targetIdentifier.Contains("multiplied by") || targetIdentifier.Contains("*") || targetIdentifier.Contains("+") || targetIdentifier.Contains("-") || targetIdentifier.Contains("/")))
            {
                string expr = targetIdentifier.ToLowerInvariant()
                    .Replace("multiplied by", "*")
                    .Replace("multiply by", "*")
                    .Replace("times", "*")
                    .Replace("x", "*")
                    .Replace("plus", "+")
                    .Replace("minus", "-")
                    .Replace("divided by", "/")
                    .Replace("divide by", "/")
                    .Replace("equals", "=")
                    .Replace("equal", "=");

                var buttonMap = new Dictionary<char, string>
                {
                    { '0', "num0Button" },
                    { '1', "num1Button" },
                    { '2', "num2Button" },
                    { '3', "num3Button" },
                    { '4', "num4Button" },
                    { '5', "num5Button" },
                    { '6', "num6Button" },
                    { '7', "num7Button" },
                    { '8', "num8Button" },
                    { '9', "num9Button" },
                    { '*', "multiplyButton" },
                    { '+', "plusButton" },
                    { '-', "minusButton" },
                    { '/', "divideButton" },
                    { '=', "equalButton" },
                };

                bool anyClicked = false;
                foreach (char c in expr)
                {
                    if (buttonMap.TryGetValue(c, out string? btnId))
                    {
                        var btn = root.FindFirst(TreeScope.Descendants,
                            new PropertyCondition(AutomationElement.AutomationIdProperty, btnId));
                        if (btn != null && btn.TryGetCurrentPattern(InvokePattern.Pattern, out object? inv) && inv is InvokePattern ip)
                        {
                            ip.Invoke();
                            anyClicked = true;
                            Thread.Sleep(60);
                        }
                    }
                }

                if (!expr.Contains("="))
                {
                    var eqBtn = root.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.AutomationIdProperty, "equalButton"));
                    if (eqBtn != null && eqBtn.TryGetCurrentPattern(InvokePattern.Pattern, out object? inv) && inv is InvokePattern ip)
                    {
                        ip.Invoke();
                        anyClicked = true;
                        Thread.Sleep(60);
                    }
                }

                if (anyClicked)
                {
                    return (true, targetIdentifier, null);
                }
            }

            AutomationElement? target = null;
            if (!string.IsNullOrWhiteSpace(targetIdentifier))
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, targetIdentifier))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.NameProperty, targetIdentifier));
            }

            if (target == null)
            {
                target = root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button));
            }

            if (target == null)
            {
                return (false, targetIdentifier ?? string.Empty, "Target clickable control not found in window.");
            }

            if (target.TryGetCurrentPattern(InvokePattern.Pattern, out object? invObj) && invObj is InvokePattern invPattern)
            {
                invPattern.Invoke();
                return (true, targetIdentifier ?? target.Current.Name, null);
            }

            if (target.TryGetCurrentPattern(TogglePattern.Pattern, out object? togObj) && togObj is TogglePattern togPattern)
            {
                togPattern.Toggle();
                return (true, targetIdentifier ?? target.Current.Name, null);
            }

            target.SetFocus();
            return (true, targetIdentifier ?? target.Current.Name, null);
        }
        catch (Exception ex)
        {
            return (false, targetIdentifier ?? string.Empty, $"Failed to click control: {ex.Message}");
        }
    }
}
