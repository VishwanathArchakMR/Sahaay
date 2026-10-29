/**
 * Electron Preload Script for Sahaay.
 * Bridges renderer with main process via a narrow, typed API using contextBridge.
 */

import { contextBridge, ipcRenderer } from "electron";

export interface ComponentHealth {
  name: string;
  status: "ONLINE" | "STARTING" | "STOPPED" | "ERROR" | "NOT_FOUND";
  pid?: number;
  endpoint: string;
  details: string;
  error?: string;
  restartCount: number;
}

export interface RuntimeHealthReport {
  backend: ComponentHealth;
  controller: ComponentHealth;
  nativeHost: ComponentHealth;
  overallReady: boolean;
  platform: string;
}

export interface SahaayAPI {
  getSystemStatus: () => Promise<{
    platform: string;
    arch: string;
    electronVersion: string;
    chromeVersion: string;
    nodeVersion: string;
  }>;
  getApiToken: () => Promise<string>;
  getRuntimeHealth: () => Promise<RuntimeHealthReport>;
  restartComponent: (component: "backend" | "controller") => Promise<boolean>;
}

const api: SahaayAPI = {
  getSystemStatus: () => ipcRenderer.invoke("sahaay:get-system-status"),
  getApiToken: () => ipcRenderer.invoke("sahaay:get-api-token"),
  getRuntimeHealth: () => ipcRenderer.invoke("sahaay:get-runtime-health"),
  restartComponent: (component: "backend" | "controller") =>
    ipcRenderer.invoke("sahaay:restart-component", component),
};

contextBridge.exposeInMainWorld("sahaay", api);
