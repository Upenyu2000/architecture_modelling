import { Capacitor } from '@capacitor/core';
import { Directory, Filesystem } from '@capacitor/filesystem';
import { Preferences } from '@capacitor/preferences';
import { Share } from '@capacitor/share';

const MOBILE_BACKEND_KEY = 'roomify.mobileBackend';

export interface MobileBackendConfig {
  baseUrl: string;
  apiToken: string;
}

export function isNativeMobile(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() !== 'web';
}

export function normalizeBackendUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) throw new Error('Enter the address of the Roomify rendering server.');
  const withProtocol = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  const parsed = new URL(withProtocol);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('The rendering server must use an http:// or https:// address.');
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/, '');
  parsed.search = '';
  parsed.hash = '';
  return parsed.toString().replace(/\/$/, '');
}

export async function loadMobileBackendConfig(): Promise<MobileBackendConfig | null> {
  const { value } = await Preferences.get({ key: MOBILE_BACKEND_KEY });
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as Partial<MobileBackendConfig>;
    if (!parsed.baseUrl) return null;
    return {
      baseUrl: normalizeBackendUrl(parsed.baseUrl),
      apiToken: String(parsed.apiToken ?? ''),
    };
  } catch {
    return null;
  }
}

export async function saveMobileBackendConfig(config: MobileBackendConfig): Promise<void> {
  await Preferences.set({
    key: MOBILE_BACKEND_KEY,
    value: JSON.stringify({
      baseUrl: normalizeBackendUrl(config.baseUrl),
      apiToken: config.apiToken.trim(),
    }),
  });
}

export async function clearMobileBackendConfig(): Promise<void> {
  await Preferences.remove({ key: MOBILE_BACKEND_KEY });
}

function safeFilename(value: string): string {
  return value.replace(/[^a-z0-9._-]+/gi, '-').replace(/^-+|-+$/g, '') || 'roomify-export';
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? '');
      resolve(result.includes(',') ? result.split(',', 2)[1] : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error('Unable to read downloaded file.'));
    reader.readAsDataURL(blob);
  });
}

export async function downloadOrShare(
  url: string,
  filename: string,
  headers?: HeadersInit,
): Promise<void> {
  if (!isNativeMobile()) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    return;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error((await response.text()) || `Download failed with status ${response.status}.`);
  }

  const exportDirectory = 'roomify-exports';
  const path = `${exportDirectory}/${safeFilename(filename)}`;
  const data = await blobToBase64(await response.blob());
  await Filesystem.mkdir({ path: exportDirectory, directory: Directory.Cache, recursive: true });
  await Filesystem.writeFile({ path, data, directory: Directory.Cache });
  const { uri } = await Filesystem.getUri({ path, directory: Directory.Cache });
  const canShare = await Share.canShare();

  if (canShare.value) {
    await Share.share({
      title: filename,
      text: 'Generated with Roomify Studio',
      files: [uri],
      dialogTitle: 'Save or share architectural output',
    });
    return;
  }

  window.open(uri, '_blank', 'noopener,noreferrer');
}
