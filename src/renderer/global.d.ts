export {};

declare global {
  interface Window {
    desktop?: {
      selectFile: (filters?: { name: string; extensions: string[] }[]) => Promise<string | null>;
      selectDirectory: () => Promise<string | null>;
      openPath: (targetPath: string) => Promise<string>;
      backendUrl: () => Promise<string>;
    };
  }
}
