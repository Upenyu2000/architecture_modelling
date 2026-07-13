import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import { spawn, ChildProcessWithoutNullStreams } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

const BACKEND_HOST = '127.0.0.1';
const BACKEND_PORT = 8765;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let mainWindow: BrowserWindow | null = null;

function backendUrl(): string {
  return `http://${BACKEND_HOST}:${BACKEND_PORT}`;
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
    args: ['-m', 'uvicorn', 'backend.app.main:app', '--host', BACKEND_HOST, '--port', String(BACKEND_PORT)],
    cwd: appRoot,
  };
}

function startBackend(): void {
  const { command, args, cwd } = resolveBackendCommand();
  const dataDir = path.join(app.getPath('userData'), 'data');
  fs.mkdirSync(dataDir, { recursive: true });

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

  backendProcess.stdout.on('data', (data) => console.log(`[AI service] ${String(data).trim()}`));
  backendProcess.stderr.on('data', (data) => console.error(`[AI service] ${String(data).trim()}`));
  backendProcess.on('exit', (code) => {
    console.log(`AI service exited with code ${code}`);
    backendProcess = null;
  });
}

async function waitForBackend(timeoutMs = 30000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${backendUrl()}/health`);
      if (response.ok) return;
    } catch {
      // Service is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error('The local AI service did not start within 30 seconds.');
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
