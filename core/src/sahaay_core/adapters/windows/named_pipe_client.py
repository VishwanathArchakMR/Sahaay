r"""Windows Named Pipe Client using ctypes for reliable local IPC.

Connects to \\.\pipe\SahaayControllerPipe without third-party dependencies.
"""

import ctypes
import json
import uuid
from ctypes import wintypes
from typing import Any, Dict, Optional

# Win32 Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PIPE_READMODE_MESSAGE = 0x00000002

kernel32 = ctypes.windll.kernel32

CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
CreateFileW.restype = wintypes.HANDLE

ReadFile = kernel32.ReadFile
ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
ReadFile.restype = wintypes.BOOL

WriteFile = kernel32.WriteFile
WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
WriteFile.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


class NamedPipeClient:
    """Client for synchronous or async calls to \\\\.\\pipe\\SahaayControllerPipe."""

    def __init__(self, pipe_name: str = "SahaayControllerPipe") -> None:
        self.pipe_path = f"\\\\.\\pipe\\{pipe_name}"

    def send_command(
        self,
        command: str,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_ms: int = 3000,
    ) -> Dict[str, Any]:
        """Send a typed command to the Sahaay Windows Controller via Named Pipe."""
        handle = CreateFileW(
            self.pipe_path,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )

        if handle in (INVALID_HANDLE_VALUE, -1, None, 0):
            error_code = kernel32.GetLastError()
            raise ConnectionError(
                f"Could not connect to Sahaay Controller Named Pipe '{self.pipe_path}' (Win32 Error: {error_code}). "
                "Ensure Sahaay.Controller daemon is running."
            )

        try:
            req_payload = {
                "id": uuid.uuid4().hex,
                "command": command,
                "sessionId": session_id or "default-session",
                "taskId": task_id,
                "parameters": parameters or {},
            }

            req_bytes = (json.dumps(req_payload) + "\n").encode("utf-8")
            bytes_written = wintypes.DWORD(0)

            success = WriteFile(
                handle, req_bytes, len(req_bytes), ctypes.byref(bytes_written), None
            )
            if not success:
                raise OSError(f"WriteFile failed with error {kernel32.GetLastError()}")

            # Read response line
            buffer = ctypes.create_string_buffer(65536)
            bytes_read = wintypes.DWORD(0)
            success = ReadFile(handle, buffer, 65536, ctypes.byref(bytes_read), None)
            if not success and kernel32.GetLastError() != 0:
                raise OSError(f"ReadFile failed with error {kernel32.GetLastError()}")

            resp_raw = buffer.raw[: bytes_read.value].decode("utf-8").strip()
            return json.loads(resp_raw)
        finally:
            CloseHandle(handle)
