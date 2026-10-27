/**
 * Electron Main Process for Sahaay.
 * Implements strict security policies:
 * - contextIsolation: true
 * - nodeIntegration: false
 * - sandbox: true
 * - navigation & popup restrictions
 * - validated IPC handlers
 */

import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "path";

let mainWindow: BrowserWindow | null = null;

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
      color: "#0f172a",
      symbolColor: "#94a3b8",
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
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

// IPC Handlers with sender validation
ipcMain.handle("sahaay:get-system-status", async (event) => {
  // Validate sender
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

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
