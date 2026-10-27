# Sahaay Windows Development Setup Guide

## 1. System Requirements & Detected Environment
This setup was verified on:
- **Operating System**: Microsoft Windows 11 (x64)
- **CPU**: 12th Gen Intel Core i5-12500H (12 Cores, 16 Logical Processors)
- **RAM**: 16 GB Physical Memory
- **GPU**: NVIDIA GeForce RTX 3050 4GB Laptop GPU + Intel Iris Xe
- **Node.js**: v22.18.0 (npm v10.9.3)
- **Python**: 3.12.8 (64-bit)
- **uv**: 0.7.13 (installed in user profile at `$env:APPDATA\Python\Python312\Scripts\uv.exe`)
- **Git**: 2.50.1.windows.1
- **Browsers**: Google Chrome (installed), Microsoft Edge (installed)
- **.NET SDK**: .NET 10 LTS SDK (`10.0.403`) and WindowsDesktop runtime (`10.0.14`) installed at `$env:LOCALAPPDATA\Microsoft\dotnet`

---

## 2. Quick Setup (Automated)

Run the root setup script in PowerShell:
```powershell
.\scripts\setup.ps1
```
This script automatically:
1. Configures Python virtual environment with `uv` and installs `core/` dependencies.
2. Compiles the Browser Extension with `npm install` and `npm run build`.
3. Compiles the Desktop Application with `npm install` and `npm run build`.
4. Builds the .NET 10 companion solution (`Sahaay.sln`).

---

## 3. Native Messaging Host Registration

Register the native messaging host for Chrome and Edge (HKCU user-level registry):
```powershell
# In PowerShell:
.\apps\windows-companion\register-native-host.ps1 -ExtensionId "<your-extension-id>" -TargetBrowser "All"
```
To unregister when finished:
```powershell
.\apps\windows-companion\unregister-native-host.ps1 -TargetBrowser "All"
```

---

## 4. Running the Complete Vertical Slice

### Step 1: Start the Windows Companion Daemon
```powershell
cd C:\Sahaay\apps\windows-companion
$env:PATH = "$env:LOCALAPPDATA\Microsoft\dotnet;$env:PATH"
dotnet run --project Sahaay.Controller
```
The controller listens on `\\.\pipe\SahaayControllerPipe` for UI Automation queries.

### Step 2: Start the FastAPI Backend
```powershell
cd C:\Sahaay
.\core\.venv\Scripts\activate
$env:PYTHONPATH = "core/src"
uvicorn sahaay_core.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 3: Load the Browser Extension
1. Open Google Chrome or Microsoft Edge.
2. Navigate to `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and select `C:\Sahaay\apps\browser-extension\dist`.
5. Copy the generated Extension ID and run `register-native-host.ps1` with that ID.

### Step 4: Launch the Sahaay Desktop Interface
```powershell
cd C:\Sahaay\apps\desktop
npm run dev
```

---

## 5. Running Quality Checks and Test Suites

Execute all quality checks, linters, and unit test suites:
```powershell
.\scripts\run-tests.ps1
```
This runs:
- `ruff check core tests`
- `pytest tests` (36 tests)
- `dotnet test apps/windows-companion/Sahaay.sln` (8 xUnit tests)
- Browser extension TypeScript typecheck
- Desktop application TypeScript typecheck
