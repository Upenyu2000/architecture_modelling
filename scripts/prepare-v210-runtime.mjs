import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./prepare-v200-runtime.mjs');

function replaceOne(source, pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`2.1 mobile runtime patch could not find: ${label}`);
  return source.replace(pattern, replacement);
}

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = (await readFile(appPath, 'utf8')).replace(/\r\n/g, '\n');
app = app.replace('<span>Roomify Studio 2.0</span>', '<span>Roomify Studio 2.1</span>');
app = app.replace('Local-first Windows app', 'Android + Windows');
if (!app.includes('<span>Roomify Studio 2.1</span>')) {
  throw new Error('2.1 mobile runtime patch could not update the application release label.');
}
await writeFile(appPath, app, 'utf8');

const apiPath = path.join(root, 'src', 'renderer', 'lib', 'api.ts');
let api = (await readFile(apiPath, 'utf8')).replace(/\r\n/g, '\n');

if (!api.includes("from './mobile-platform'")) {
  api = replaceOne(
    api,
    /import type \{ FurniturePayload, InteriorLibrary \} from '\.\.\/interior-types';/,
    `import type { FurniturePayload, InteriorLibrary } from '../interior-types';
import { isNativeMobile, loadMobileBackendConfig, normalizeBackendUrl } from './mobile-platform';`,
    'mobile platform import',
  );
}

if (!api.includes('configureApiConnection')) {
  api = replaceOne(
    api,
    /let cachedBaseUrl = 'http:\/\/127\.0\.0\.1:8765';[\s\S]*?export function absoluteUrl\(path\?: string \| null\): string \| undefined \{[\s\S]*?\n\}/,
    `let cachedBaseUrl = import.meta.env.VITE_DREAMHOME_API_URL || 'http://127.0.0.1:8765';
let cachedApiToken = import.meta.env.VITE_DREAMHOME_API_TOKEN || '';

export function configureApiConnection(baseUrl: string, apiToken = ''): void {
  cachedBaseUrl = normalizeBackendUrl(baseUrl);
  cachedApiToken = apiToken.trim();
}

export function currentApiConnection(): { baseUrl: string; apiToken: string } {
  return { baseUrl: cachedBaseUrl, apiToken: cachedApiToken };
}

export function apiAuthHeaders(): HeadersInit {
  return cachedApiToken ? { Authorization: \`Bearer \${cachedApiToken}\` } : {};
}

export async function initApi(): Promise<void> {
  if (window.desktop) {
    configureApiConnection(await window.desktop.backendUrl());
    return;
  }
  if (isNativeMobile()) {
    const stored = await loadMobileBackendConfig();
    if (!stored) throw new Error('Connect the Android app to a Roomify rendering server.');
    configureApiConnection(stored.baseUrl, stored.apiToken);
  }
}

function requestHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  if (cachedApiToken && !headers.has('Authorization')) {
    headers.set('Authorization', \`Bearer \${cachedApiToken}\`);
  }
  return headers;
}

export async function testApiConnection(
  baseUrl: string,
  apiToken = '',
): Promise<{ version: string }> {
  const normalized = normalizeBackendUrl(baseUrl);
  const headers = new Headers();
  if (apiToken.trim()) headers.set('Authorization', \`Bearer \${apiToken.trim()}\`);
  let health: Response;
  try {
    health = await fetch(\`\${normalized}/health\`, { headers });
  } catch {
    throw new Error('The server could not be reached. Check the address, Wi-Fi and firewall.');
  }
  if (!health.ok) throw new Error((await health.text()) || 'The Roomify health check failed.');
  const payload = await health.json() as { version?: string };
  const projects = await fetch(\`\${normalized}/api/v1/projects\`, { headers });
  if (projects.status === 401) throw new Error('The API token was rejected by the rendering server.');
  if (!projects.ok) throw new Error((await projects.text()) || 'The Roomify project API is unavailable.');
  return { version: payload.version || 'unknown' };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(\`\${cachedBaseUrl}\${path}\`, { ...init, headers: requestHeaders(init) });
  } catch {
    throw new Error('The Roomify rendering server is offline or unreachable. Open the server settings on Android and verify the address.');
  }
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || \`\${response.status} \${response.statusText}\`);
  }
  return response.json() as Promise<T>;
}

export function absoluteUrl(path?: string | null): string | undefined {
  if (!path) return undefined;
  if (path.startsWith('data:') || path.startsWith('blob:') || path.startsWith('file:')) return path;
  const url = path.startsWith('http') ? new URL(path) : new URL(path, \`\${cachedBaseUrl}/\`);
  if (cachedApiToken && url.origin === new URL(cachedBaseUrl).origin && !url.searchParams.has('access_token')) {
    url.searchParams.set('access_token', cachedApiToken);
  }
  return url.toString();
}`,
    'API connection block',
  );
}

if (!api.includes('testApiConnection') || !api.includes('apiAuthHeaders')) {
  throw new Error('2.1 mobile runtime patch did not install authenticated Android API support.');
}
await writeFile(apiPath, api, 'utf8');

console.log('Prepared Roomify Studio 2.1 Android and Windows runtime with configurable authenticated backend connectivity.');
