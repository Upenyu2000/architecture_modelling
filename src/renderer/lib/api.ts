import type { AssetCategory, Job, Project, SaveSlot, SceneManifest } from '../types';

let cachedBaseUrl = 'http://127.0.0.1:8765';

export async function initApi(): Promise<void> {
  if (window.desktop) cachedBaseUrl = await window.desktop.backendUrl();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${cachedBaseUrl}${path}`, init);
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function absoluteUrl(path?: string | null): string | undefined {
  if (!path) return undefined;
  return path.startsWith('http') ? path : `${cachedBaseUrl}${path}`;
}

export const api = {
  listProjects: () => request<Project[]>('/api/v1/projects'),
  createProject: (name = 'My Dream Home') =>
    request<Project>('/api/v1/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),
  resetProject: (id: string) =>
    request<Project>(`/api/v1/projects/${id}/reset`, { method: 'POST' }),
  listSaveSlots: (id: string) =>
    request<SaveSlot[]>(`/api/v1/projects/${id}/save-slots`),
  createSaveSlot: (id: string, name: string) =>
    request<SaveSlot>(`/api/v1/projects/${id}/save-slots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  loadSaveSlot: (id: string, slotId: string) =>
    request<Project>(`/api/v1/projects/${id}/save-slots/${slotId}/load`, { method: 'POST' }),
  deleteSaveSlot: (id: string, slotId: string) =>
    request<{ deleted: string }>(`/api/v1/projects/${id}/save-slots/${slotId}`, { method: 'DELETE' }),
  uploadFloorplan: async (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Project>(`/api/v1/projects/${id}/floorplan`, { method: 'POST', body });
  },
  uploadAsset: async (id: string, category: AssetCategory, slot: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    body.append('label', file.name.replace(/\.[^.]+$/, ''));
    return request<Project>(`/api/v1/projects/${id}/assets/${category}/${slot}`, { method: 'POST', body });
  },
  analyze: (id: string, planWidthM: number, wallHeightM: number) =>
    request<SceneManifest>(`/api/v1/projects/${id}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_width_m: planWidthM, wall_height_m: wallHeightM }),
    }),
  updateRoom: (id: string, roomId: string, name: string) =>
    request<SceneManifest>(`/api/v1/projects/${id}/rooms/${roomId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  render: (id: string, quality: 'preview' | '1080p' | '4k', engine: 'auto' | 'technical' | 'blender') =>
    request<Job>(`/api/v1/projects/${id}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quality, engine }),
    }),
  walkthrough: (id: string, seconds: number, quality: '1080p' | '4k', engine: 'auto' | 'blender') =>
    request<Job>(`/api/v1/projects/${id}/walkthrough`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seconds, quality, engine }),
    }),
  getJob: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
  getSettings: () => request<Record<string, string | boolean>>('/api/v1/settings'),
  saveSettings: (settings: Record<string, string | boolean>) =>
    request<Record<string, string | boolean>>('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),
};
