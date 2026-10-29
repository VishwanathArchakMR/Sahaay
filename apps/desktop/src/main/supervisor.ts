/**
 * Runtime Supervisor for Sahaay Desktop Application.
 *
 * Manages the complete lifecycle of required user-session processes:
 * 1. Sahaay Core Backend (FastAPI / Uvicorn on 127.0.0.1:8000)
 * 2. Sahaay Windows Companion (Interactive UI Automation Controller on \\.\pipe\SahaayControllerPipe)
 * 3. Browser Native Messaging Host status monitoring
 *
 * Implements:
 * - Duplicate process detection and connection reuse
 * - Health check polling and timeout handling
 * - Bounded auto-recovery for crashed components
 * - Clean process tree termination on application quit
 * - Diagnostic reporting for the user interface
 */

import { ChildProcess, spawn } from "child_process";
import { existsSync } from "fs";
import * as http from "http";
import * as net from "net";
import { join, resolve } from "path";

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

export class RuntimeSupervisor {
  private repoRoot: string;
  private backendProcess: ChildProcess | null = null;
  private controllerProcess: ChildProcess | null = null;
  private backendRestartCount = 0;
  private controllerRestartCount = 0;
  private maxRestarts = 3;
  private isShuttingDown = false;

  constructor(appPath: string) {
    this.repoRoot = this.detectRepoRoot(appPath);
    console.log(`[Supervisor] Initialized with repository root: ${this.repoRoot}`);
  }

  private detectRepoRoot(startPath: string): string {
    let current = resolve(startPath);
    for (let i = 0; i < 4; i++) {
      if (existsSync(join(current, "core")) && existsSync(join(current, "apps"))) {
        return current;
      }
      current = resolve(current, "..");
    }
    // Fallback default
    return "C:\\Sahaay";
  }

  public async startSupervisedRuntime(): Promise<void> {
    console.log("[Supervisor] Starting managed Sahaay runtime...");
    await this.ensureBackendRunning();
    await this.ensureControllerRunning();
  }

  // -------------------------------------------------------------------------
  // 1. CORE BACKEND MANAGEMENT
  // -------------------------------------------------------------------------
  public async ensureBackendRunning(): Promise<boolean> {
    const isHealthy = await this.probeBackendHealth();
    if (isHealthy) {
      console.log("[Supervisor] Backend is already running and healthy on 127.0.0.1:8000 (reusing instance).");
      return true;
    }

    if (this.backendProcess && !this.backendProcess.killed) {
      console.log("[Supervisor] Backend process already spawned; waiting for ready...");
      return this.waitForBackendReady(10000);
    }

    const pythonVenv = join(this.repoRoot, "core", ".venv", "Scripts", "python.exe");
    const pythonExe = existsSync(pythonVenv) ? pythonVenv : "python";

    console.log(`[Supervisor] Spawning Core Backend using ${pythonExe}...`);

    try {
      this.backendProcess = spawn(
        pythonExe,
        ["-m", "uvicorn", "sahaay_core.main:app", "--host", "127.0.0.1", "--port", "8000"],
        {
          cwd: join(this.repoRoot, "core"),
          windowsHide: true,
          env: {
            ...process.env,
            PYTHONPATH: join(this.repoRoot, "core", "src"),
          },
        }
      );

      this.backendProcess.stdout?.on("data", (data) => {
        const line = data.toString().trim();
        if (line) console.log(`[Backend] ${line}`);
      });

      this.backendProcess.stderr?.on("data", (data) => {
        const line = data.toString().trim();
        if (line) console.error(`[Backend] ${line}`);
      });

      this.backendProcess.on("exit", (code, signal) => {
        console.warn(`[Supervisor] Backend process exited (code: ${code}, signal: ${signal})`);
        this.backendProcess = null;
        if (!this.isShuttingDown && this.backendRestartCount < this.maxRestarts) {
          this.backendRestartCount++;
          console.log(`[Supervisor] Auto-recovering backend (attempt ${this.backendRestartCount}/${this.maxRestarts})...`);
          setTimeout(() => this.ensureBackendRunning(), 2000);
        }
      });

      return await this.waitForBackendReady(12000);
    } catch (err: any) {
      console.error(`[Supervisor] Failed to spawn backend: ${err.message}`);
      return false;
    }
  }

  private probeBackendHealth(): Promise<boolean> {
    return new Promise((res) => {
      const req = http.get("http://127.0.0.1:8000/api/v1/health", { timeout: 1500 }, (r) => {
        res(r.statusCode === 200);
      });
      req.on("error", () => res(false));
      req.on("timeout", () => {
        req.destroy();
        res(false);
      });
    });
  }

  private async waitForBackendReady(timeoutMs: number): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (await this.probeBackendHealth()) return true;
      await new Promise((r) => setTimeout(r, 600));
    }
    return false;
  }

  // -------------------------------------------------------------------------
  // 2. WINDOWS INTERACTIVE CONTROLLER MANAGEMENT
  // -------------------------------------------------------------------------
  public async ensureControllerRunning(): Promise<boolean> {
    const isPipeUp = await this.probeControllerPipe();
    if (isPipeUp) {
      console.log("[Supervisor] Windows Controller pipe is already listening (reusing instance).");
      return true;
    }

    if (this.controllerProcess && !this.controllerProcess.killed) {
      return this.waitForControllerReady(8000);
    }

    const candidateBinaries = [
      join(this.repoRoot, "apps", "windows-companion", "Sahaay.Controller", "bin", "Release", "net10.0-windows", "Sahaay.Controller.exe"),
      join(this.repoRoot, "apps", "windows-companion", "Sahaay.Controller", "bin", "Debug", "net10.0-windows", "Sahaay.Controller.exe"),
      join(this.repoRoot, "bin", "dist", "Sahaay.Controller.exe"),
    ];

    const controllerExe = candidateBinaries.find((p) => existsSync(p));
    if (!controllerExe) {
      console.warn("[Supervisor] Sahaay.Controller.exe binary not found. Real UI Automation requires companion compilation.");
      return false;
    }

    console.log(`[Supervisor] Spawning interactive Windows Controller: ${controllerExe}...`);

    try {
      this.controllerProcess = spawn(controllerExe, [], {
        cwd: join(this.repoRoot, "apps", "windows-companion", "Sahaay.Controller"),
        windowsHide: true,
        env: process.env,
      });

      this.controllerProcess.stdout?.on("data", (data) => {
        const line = data.toString().trim();
        if (line) console.log(`[Controller] ${line}`);
      });

      this.controllerProcess.stderr?.on("data", (data) => {
        const line = data.toString().trim();
        if (line) console.error(`[Controller] ${line}`);
      });

      this.controllerProcess.on("exit", (code, signal) => {
        console.warn(`[Supervisor] Controller process exited (code: ${code}, signal: ${signal})`);
        this.controllerProcess = null;
        if (!this.isShuttingDown && this.controllerRestartCount < this.maxRestarts) {
          this.controllerRestartCount++;
          console.log(`[Supervisor] Auto-recovering controller (attempt ${this.controllerRestartCount}/${this.maxRestarts})...`);
          setTimeout(() => this.ensureControllerRunning(), 2000);
        }
      });

      return await this.waitForControllerReady(8000);
    } catch (err: any) {
      console.error(`[Supervisor] Failed to spawn controller: ${err.message}`);
      return false;
    }
  }

  private probeControllerPipe(): Promise<boolean> {
    return new Promise((res) => {
      const client = net.connect("\\\\.\\pipe\\SahaayControllerPipe", () => {
        client.write(JSON.stringify({ id: "probe-1", command: "ping" }) + "\n");
      });
      client.on("data", () => {
        client.destroy();
        res(true);
      });
      client.on("error", () => {
        res(false);
      });
      client.setTimeout(1200, () => {
        client.destroy();
        res(false);
      });
    });
  }

  private async waitForControllerReady(timeoutMs: number): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (await this.probeControllerPipe()) return true;
      await new Promise((r) => setTimeout(r, 500));
    }
    return false;
  }

  // -------------------------------------------------------------------------
  // 3. BROWSER BRIDGE PROBING
  // -------------------------------------------------------------------------
  private probeBrowserBridgePipe(): Promise<boolean> {
    return new Promise((res) => {
      const client = net.connect("\\\\.\\pipe\\SahaayBrowserBridgePipe", () => {
        client.write(JSON.stringify({ id: "probe-br", command: "ping" }) + "\n");
      });
      client.on("data", () => {
        client.destroy();
        res(true);
      });
      client.on("error", () => {
        res(false);
      });
      client.setTimeout(1000, () => {
        client.destroy();
        res(false);
      });
    });
  }

  // -------------------------------------------------------------------------
  // 4. DIAGNOSTICS & STATUS
  // -------------------------------------------------------------------------
  public async getHealthReport(): Promise<RuntimeHealthReport> {
    const backendUp = await this.probeBackendHealth();
    const controllerUp = await this.probeControllerPipe();
    const bridgeUp = await this.probeBrowserBridgePipe();

    const candidateController = join(this.repoRoot, "apps", "windows-companion", "Sahaay.Controller", "bin", "Release", "net10.0-windows", "Sahaay.Controller.exe");
    const candidateDebug = join(this.repoRoot, "apps", "windows-companion", "Sahaay.Controller", "bin", "Debug", "net10.0-windows", "Sahaay.Controller.exe");
    const controllerExists = existsSync(candidateController) || existsSync(candidateDebug);

    const backendStatus: ComponentHealth = {
      name: "Sahaay Core Backend",
      status: backendUp ? "ONLINE" : (this.backendProcess ? "STARTING" : "STOPPED"),
      pid: this.backendProcess?.pid,
      endpoint: "http://127.0.0.1:8000/api/v1",
      details: backendUp ? "Authoritative Python backend running." : "Backend not responding on loopback port 8000.",
      restartCount: this.backendRestartCount,
    };

    const controllerStatus: ComponentHealth = {
      name: "Windows Interactive Controller",
      status: controllerUp ? "ONLINE" : (controllerExists ? (this.controllerProcess ? "STARTING" : "STOPPED") : "NOT_FOUND"),
      pid: this.controllerProcess?.pid,
      endpoint: "\\\\.\\pipe\\SahaayControllerPipe",
      details: controllerUp
        ? "UI Automation companion connected in user session."
        : (controllerExists
          ? "Controller process stopped or named pipe disconnected."
          : "Sahaay.Controller.exe not compiled. Run .\\scripts\\build-companion.ps1 to build."),
      restartCount: this.controllerRestartCount,
    };

    const nativeHostStatus: ComponentHealth = {
      name: "Browser Native Messaging Host",
      status: bridgeUp ? "ONLINE" : "STOPPED",
      endpoint: "\\\\.\\pipe\\SahaayBrowserBridgePipe",
      details: bridgeUp
        ? "Browser bridge active and listening for tab commands."
        : "Browser bridge waiting for Chrome/Edge tab connection.",
      restartCount: 0,
    };

    return {
      backend: backendStatus,
      controller: controllerStatus,
      nativeHost: nativeHostStatus,
      overallReady: backendUp && controllerUp,
      platform: process.platform,
    };
  }

  // -------------------------------------------------------------------------
  // 5. SHUTDOWN & CLEANUP
  // -------------------------------------------------------------------------
  public shutdown(): void {
    console.log("[Supervisor] Gracefully terminating managed child processes...");
    this.isShuttingDown = true;

    if (this.backendProcess && this.backendProcess.pid) {
      try {
        console.log(`[Supervisor] Terminating backend PID ${this.backendProcess.pid}...`);
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", this.backendProcess.pid.toString(), "/T", "/F"]);
        } else {
          this.backendProcess.kill("SIGTERM");
        }
      } catch (e) {
        console.error("[Supervisor] Error stopping backend:", e);
      }
      this.backendProcess = null;
    }

    if (this.controllerProcess && this.controllerProcess.pid) {
      try {
        console.log(`[Supervisor] Terminating controller PID ${this.controllerProcess.pid}...`);
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", this.controllerProcess.pid.toString(), "/T", "/F"]);
        } else {
          this.controllerProcess.kill("SIGTERM");
        }
      } catch (e) {
        console.error("[Supervisor] Error stopping controller:", e);
      }
      this.controllerProcess = null;
    }
  }
}
