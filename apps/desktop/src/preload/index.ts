/**
 * Electron Preload Script for Sahaay.
 * Bridges renderer with main process via a narrow, typed API using contextBridge.
 */

import { contextBridge, ipcRenderer } from "electron";

export interface SahaayAPI {
  getSystemStatus: () => Promise<{
    platform: string;
    arch: string;
    electronVersion: string;
    chromeVersion: string;
    nodeVersion: string;
  }>;
  getApiToken: () => Promise<string>;
}

const api: SahaayAPI = {
  getSystemStatus: () => ipcRenderer.invoke("sahaay:get-system-status"),
  getApiToken: () => ipcRenderer.invoke("sahaay:get-api-token"),
};

contextBridge.exposeInMainWorld("sahaay", api);
