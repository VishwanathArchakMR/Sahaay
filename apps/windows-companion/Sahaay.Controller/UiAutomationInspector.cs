using System;
using System.Collections.Generic;
using System.Windows.Automation;
using Sahaay.Contracts;

namespace Sahaay.Controller;

public static class UiAutomationInspector
{
    private const int MaxElements = 80;
    private const int MaxDepth = 4;

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
                valPattern.SetValue(text);
                return (true, valPattern.Current.Value, null);
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
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit))
                    ?? root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Document));
            }

            if (target == null)
            {
                return (false, string.Empty, "No readable control found in target window.");
            }

            if (target.TryGetCurrentPattern(ValuePattern.Pattern, out object? patternObj) && patternObj is ValuePattern valPattern)
            {
                return (true, valPattern.Current.Value, null);
            }

            return (true, target.Current.Name ?? string.Empty, null);
        }
        catch (Exception ex)
        {
            return (false, string.Empty, $"Failed to get control text: {ex.Message}");
        }
    }
}
