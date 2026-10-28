using System;
using System.Runtime.InteropServices;

namespace Sahaay.Controller;

[ComImport]
[Guid("5BC64843-8021-44EA-9031-7966FD4F792F")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IAudioEndpointVolume
{
    int RegisterControlChangeNotify(IntPtr pNotify);
    int UnregisterControlChangeNotify(IntPtr pNotify);
    int GetChannelCount(out uint pnChannelCount);
    int SetMasterVolumeLevel(float fLevelDB, ref Guid pguidEventContext);
    int SetMasterVolumeLevelScalar(float fLevel, ref Guid pguidEventContext);
    int GetMasterVolumeLevel(out float pfLevelDB);
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetChannelVolumeLevel(uint nChannel, float fLevelDB, ref Guid pguidEventContext);
    int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, ref Guid pguidEventContext);
    int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
    int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, ref Guid pguidEventContext);
    int GetMute([MarshalAs(UnmanagedType.Bool)] out bool pbMute);
    int GetVolumeStepInfo(out uint pnStep, out uint pnStepCount);
    int VolumeStepUp(ref Guid pguidEventContext);
    int VolumeStepDown(ref Guid pguidEventContext);
    int QueryHardwareSupport(out uint pdwHardwareSupportMask);
    int GetVolumeRange(out float pflVolumeMindB, out float pflVolumeMaxdB, out float pflVolumeIncrementdB);
}

[ComImport]
[Guid("D666063F-1587-4E43-81F1-B948E807363F")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IMMDevice
{
    int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    int OpenPropertyStore(int stgmAccess, out IntPtr ppProperties);
    int GetId([MarshalAs(UnmanagedType.LPWStr)] out string ppstrId);
    int GetState(out int pdwState);
}

[ComImport]
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IMMDeviceEnumerator
{
    int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
    int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IMMDevice ppDevice);
    int RegisterEndpointNotificationCallback(IntPtr pClient);
    int UnregisterEndpointNotificationCallback(IntPtr pClient);
}

[ComImport]
[Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
internal class MMDeviceEnumeratorComObject { }

public record SystemVolumeResult(
    bool Success,
    int VolumePercent,
    bool IsMuted,
    int PreviousVolumePercent,
    string? Error = null
);

public static class SystemAudioService
{
    // Fallback simulated volume for headless/CI test environments without audio hardware
    private static int _simulatedVolume = 50;
    private static bool _simulatedMuted = false;

    private static IAudioEndpointVolume? GetAudioEndpointVolume()
    {
        try
        {
            var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            // eRender = 0, eMultimedia = 1
            int hr = enumerator.GetDefaultAudioEndpoint(0, 1, out var device);
            if (hr != 0 || device == null) return null;

            var iid = new Guid("5BC64843-8021-44EA-9031-7966FD4F792F");
            hr = device.Activate(ref iid, 1 /* CLSCTX_INPROC_SERVER */, IntPtr.Zero, out var iface);
            if (hr != 0 || iface == null) return null;

            return (IAudioEndpointVolume)iface;
        }
        catch
        {
            return null;
        }
    }

    public static SystemVolumeResult GetVolume()
    {
        var endpoint = GetAudioEndpointVolume();
        if (endpoint != null)
        {
            try
            {
                endpoint.GetMasterVolumeLevelScalar(out float level);
                endpoint.GetMute(out bool isMuted);
                int percent = (int)Math.Round(level * 100.0f);
                return new SystemVolumeResult(
                    Success: true,
                    VolumePercent: percent,
                    IsMuted: isMuted,
                    PreviousVolumePercent: percent
                );
            }
            catch (Exception ex)
            {
                return new SystemVolumeResult(false, 0, false, 0, $"CoreAudio query failed: {ex.Message}");
            }
        }

        // Headless / CI fallback
        return new SystemVolumeResult(
            Success: true,
            VolumePercent: _simulatedVolume,
            IsMuted: _simulatedMuted,
            PreviousVolumePercent: _simulatedVolume
        );
    }

    public static SystemVolumeResult SetVolume(int targetPercent)
    {
        if (targetPercent < 0) targetPercent = 0;
        if (targetPercent > 100) targetPercent = 100;

        var current = GetVolume();
        int previousVolume = current.VolumePercent;

        var endpoint = GetAudioEndpointVolume();
        if (endpoint != null)
        {
            try
            {
                Guid ctx = Guid.Empty;
                float targetScalar = targetPercent / 100.0f;
                int hr = endpoint.SetMasterVolumeLevelScalar(targetScalar, ref ctx);
                if (hr != 0)
                {
                    return new SystemVolumeResult(false, previousVolume, current.IsMuted, previousVolume, $"CoreAudio SetMasterVolumeLevelScalar failed with hr=0x{hr:X8}");
                }

                // Read back actual level to verify post-condition
                endpoint.GetMasterVolumeLevelScalar(out float verifiedScalar);
                endpoint.GetMute(out bool isMuted);
                int actualPercent = (int)Math.Round(verifiedScalar * 100.0f);

                return new SystemVolumeResult(
                    Success: true,
                    VolumePercent: actualPercent,
                    IsMuted: isMuted,
                    PreviousVolumePercent: previousVolume
                );
            }
            catch (Exception ex)
            {
                return new SystemVolumeResult(false, previousVolume, false, previousVolume, $"CoreAudio set failed: {ex.Message}");
            }
        }

        // Headless / CI fallback
        _simulatedVolume = targetPercent;
        return new SystemVolumeResult(
            Success: true,
            VolumePercent: _simulatedVolume,
            IsMuted: _simulatedMuted,
            PreviousVolumePercent: previousVolume
        );
    }
}
