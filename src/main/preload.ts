import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('desktop', {
  selectFile: (filters?: Electron.FileFilter[]) => ipcRenderer.invoke('desktop:select-file', { filters }),
  selectDirectory: () => ipcRenderer.invoke('desktop:select-directory'),
  openPath: (targetPath: string) => ipcRenderer.invoke('desktop:open-path', targetPath),
  backendUrl: () => ipcRenderer.invoke('desktop:backend-url'),
});
