import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import { spawn, ChildProcessWithoutNullStreams } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT = 8765;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let backendFailure: string | null = null;
let backendLogPath = '';
let mainWindow: BrowserWindow | null = null;

function backendUrl(): string {
  return `http://${BACKEND_HOST}:${BACKEND_PORT}`;
}

function appendBackendLog(message: string): void {
  if (!backendLogPath) return;
  try {
    fs.appendFileSync(backendLogPath, `${new Date().toISOString()} ${message}\n`, 'utf8');
  } catch {
    // Logging must never prevent the application from starting.
  }
}

function resolveBackendCommand(): { command: string; args: string[]; cwd: string } {
  const appRoot = app.getAppPath();
  if (app.isPackaged) {
    const executable = path.join(process.resourcesPath, 'backend', 'dreamhome-ai.exe');
    if (!fs.existsSync(executable)) {
      throw new Error(`Bundled AI service not found at ${executable}`);
    }
    return { command: executable, args: [], cwd: path.dirname(executable) };
  }

  const python = process.env.DREAMHOME_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  return {
    command: python,
    args: ['-m', 'uvicorn', 'backend.app.asgi:app', '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)],
    cwd: appRoot,
  };
}

function startBackend(): void {
  const { command, args, cwd } = resolveBackendCommand();
  const userDataDir = app.getPath('userData');
  const dataDir = path.join(userDataDir, 'data');
  const logsDir = path.join(userDataDir, 'logs');
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(logsDir, { recursive: true });
  backendLogPath = path.join(logsDir, 'backend.log');
  backendFailure = null;
  fs.writeFileSync(
    backendLogPath,
    `${new Date().toISOString()} Starting local AI service\nCommand: ${command} ${args.join(' ')}\nWorking directory: ${cwd}\n`,
    'utf8',
  );

  backendProcess = spawn(command, args, {
    cwd,
    windowsHide: true,
    env: {
      ...process.env,
      DREAMHOME_DATA_DIR: dataDir,
      DREAMHOME_HOST: BACKEND_HOST,
      DREAMHOME_PORT: String(BACKEND_PORT),
    },
  });

  backendProcess.stdout.on('data', (data) => {
    const message = String(data).trim();
    console.log(`[AI service] ${message}`);
    appendBackendLog(`[stdout] ${message}`);
  });
  backendProcess.stderr.on('data', (data) => {
    const message = String(data).trim();
    console.error(`[AI service] ${message}`);
    appendBackendLog(`[stderr] ${message}`);
  });
  backendProcess.on('error', (error) => {
    backendFailure = `The local AI service could not be launched: ${error.message}`;
    appendBackendLog(`[spawn error] ${error.stack || error.message}`);
  });
  backendProcess.on('exit', (code, signal) => {
    appendBackendLog(`[exit] code=${String(code)} signal=${String(signal)}`);
    if (code !== 0 && backendFailure === null) {
      backendFailure = `The local AI service exited unexpectedly with code ${String(code)}.`;
    }
    backendProcess = null;
  });
}

async function waitForBackend(timeoutMs = 90000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (backendFailure) {
      throw new Error(`${backendFailure}\n\nDiagnostic log:\n${backendLogPath}`);
    }
    try {
      const response = await fetch(`${backendUrl()}/health`);
      if (response.ok) {
        appendBackendLog('[health] Local AI service is ready.');
        return;
      }
    } catch {
      // PyInstaller one-file applications can take time to unpack on first launch.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(
    `The local AI service did not start within 90 seconds.\n\nDiagnostic log:\n${backendLogPath}`,
  );
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1540,
    height: 980,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: '#07130e',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow?.show());
  const devServer = process.env.VITE_DEV_SERVER_URL;
  if (devServer) {
    await mainWindow.loadURL(devServer);
  } else {
    await mainWindow.loadFile(path.join(app.getAppPath(), 'dist', 'index.html'));
  }
}

ipcMain.handle('desktop:select-file', async (_event, options?: { filters?: Electron.FileFilter[] }) => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openFile'],
    filters: options?.filters,
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('desktop:select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, { properties: ['openDirectory', 'createDirectory'] });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('desktop:open-path', async (_event, targetPath: string) => shell.openPath(targetPath));
ipcMain.handle('desktop:backend-url', () => backendUrl());

app.whenReady().then(async () => {
  try {
    startBackend();
    await waitForBackend();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox('Dream Home Visualizer could not start', error instanceof Error ? error.message : String(error));
    app.quit();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  backendProcess?.kill();
});
