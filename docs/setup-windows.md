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
- **.NET Runtime**: .NET 6.0.21 Desktop App runtime installed
  * *Note*: Compiling the C# native companion solution requires installing the [.NET 8 or 9 SDK](https://dotnet.microsoft.com/download).

---

## 2. Quick Setup (Automated)

Run the root setup script in PowerShell:
```powershell
.\scripts\setup.ps1
```

---

## 3. Manual Component Setup

### 3.1 Python Backend Setup
```powershell
cd C:\Sahaay\core
# Create venv and install dependencies with uv
uv venv .venv
.\.venv\Scripts\activate
uv pip install -e ".[dev]"
```

### 3.2 Desktop App Setup
```powershell
cd C:\Sahaay\apps\desktop
npm install
npm run build
```

### 3.3 Browser Extension Setup
```powershell
cd C:\Sahaay\apps\browser-extension
npm install
npm run build
```

### 3.4 Windows Companion (.NET)
Requires .NET SDK 8.0+:
```powershell
cd C:\Sahaay\apps\windows-companion
dotnet build Sahaay.sln
```

---

## 4. Running Components Locally

### 4.1 Launch Backend
```powershell
.\scripts\start-backend.ps1
# Backend runs at http://127.0.0.1:8000
# OpenAPI Swagger docs at http://127.0.0.1:8000/docs
```

### 4.2 Launch Desktop App
```powershell
.\scripts\start-desktop.ps1
```

### 4.3 Load Browser Extension in Chrome or Edge
1. Open `chrome://extensions/` or `edge://extensions/`.
2. Enable **Developer mode** toggle.
3. Click **Load unpacked**.
4. Select `C:\Sahaay\apps\browser-extension`.
