/**
 * Electron Main Process for Sahaay.
 * Implements strict security policies and active runtime supervision:
 * - contextIsolation: true
 * - nodeIntegration: false
 * - sandbox: true
 * - navigation & popup restrictions
 * - validated IPC handlers
 * - supervised backend & interactive Windows companion lifecycle
 */

import { app, BrowserWindow, ipcMain } from "electron";
import { existsSync } from "fs";
import { join } from "path";
import { RuntimeSupervisor } from "./supervisor";

let mainWindow: BrowserWindow | null = null;
let supervisor: RuntimeSupervisor | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#06131D",
      symbolColor: "#8AF5CF",
      height: 38,
    },
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  mainWindow.on("ready-to-show", () => {
    mainWindow?.show();
  });

  // Security: Prevent all untrusted navigation and new windows/popups
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    console.warn(`Blocked unauthorized popup request to: ${url}`);
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (event, navigationUrl) => {
    const parsed = new URL(navigationUrl);
    // Only allow local development or application bundle
    if (parsed.origin !== "http://localhost:5173" && parsed.protocol !== "file:") {
      event.preventDefault();
      console.warn(`Blocked external navigation to: ${navigationUrl}`);
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    const candidates = [
      join(__dirname, "../../dist/index.html"),
      join(app.getAppPath(), "dist/index.html"),
      join(__dirname, "../renderer/index.html"),
    ];
    const htmlPath = candidates.find((p) => existsSync(p));
    if (htmlPath) {
      mainWindow.loadFile(htmlPath);
    } else {
      console.error(`[Main] Could not find compiled UI at candidate paths: ${candidates.join(", ")}`);
      mainWindow.loadURL("data:text/html,<h2>Sahaay UI not built</h2><p>Please run: <code>npm run build</code> in apps/desktop</p>");
    }
  }
}

// IPC Handlers with sender validation
ipcMain.handle("sahaay:get-system-status", async (event) => {
  if (!mainWindow || event.sender !== mainWindow.webContents) {
    throw new Error("Unauthorized IPC invocation from unknown webContents.");
  }
  return {
    platform: process.platform,
    arch: process.arch,
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
    nodeVersion: process.versions.node,
  };
});

ipcMain.handle("sahaay:get-api-token", () => {
  return process.env.SAHAAY_API_TOKEN || process.env.VITE_SAHAAY_TOKEN || "";
});

ipcMain.handle("sahaay:get-runtime-health", async (event) => {
  if (!mainWindow || event.sender !== mainWindow.webContents) {
    throw new Error("Unauthorized IPC invocation from unknown webContents.");
  }
  if (!supervisor) {
    return {
      backend: { name: "Backend", status: "STOPPED", endpoint: "", details: "Supervisor not initialized", restartCount: 0 },
      controller: { name: "Controller", status: "STOPPED", endpoint: "", details: "Supervisor not initialized", restartCount: 0 },
      nativeHost: { name: "NativeHost", status: "STOPPED", endpoint: "", details: "Supervisor not initialized", restartCount: 0 },
      overallReady: false,
      platform: process.platform,
    };
  }
  return await supervisor.getHealthReport();
});

ipcMain.handle("sahaay:restart-component", async (event, component: "backend" | "controller") => {
  if (!mainWindow || event.sender !== mainWindow.webContents) {
    throw new Error("Unauthorized IPC invocation from unknown webContents.");
  }
  if (!supervisor) return false;
  if (component === "backend") {
    return await supervisor.ensureBackendRunning();
  } else if (component === "controller") {
    return await supervisor.ensureControllerRunning();
  }
  return false;
});

// Isolate userData to dedicated directory to prevent Chromium simple cache sharing conflicts
try {
  const dedicatedUserData = join(app.getPath("appData"), "SahaayDesktop");
  app.setPath("userData", dedicatedUserData);
} catch (e) {
  console.warn("[Main] Dedicated userData initialization notice:", e);
}

app.whenReady().then(async () => {
  supervisor = new RuntimeSupervisor(app.getAppPath());
  await supervisor.startSupervisedRuntime();

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", () => {
  supervisor?.shutdown();
});

app.on("will-quit", () => {
  supervisor?.shutdown();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    supervisor?.shutdown();
    app.quit();
  }
});
