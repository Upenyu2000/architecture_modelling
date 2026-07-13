import type {
  AssetCategory, Job, MaterialUpdate, ModelUnits, OpeningPayload, PlanType, Project, SaveSlot,
  SceneManifest, UpAxis, WallDetectionMode,
} from '../types';
import type { FurniturePayload, InteriorLibrary } from '../interior-types';

export type AppSettingValue = string | boolean | number;

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

function analysisPayload(
  planWidthM: number,
  wallHeightM: number,
  wallDetection: WallDetectionMode,
  minimumWallLengthM: number,
  planType: PlanType,
  useVisionAi = false,
) {
  return {
    plan_width_m: planWidthM,
    wall_height_m: wallHeightM,
    wall_detection: wallDetection,
    minimum_wall_length_m: minimumWallLengthM,
    plan_type: planType,
    detect_openings: true,
    auto_furnish: true,
    use_vision_ai: useVisionAi,
  };
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
  resetProject: (id: string) => request<Project>(`/api/v1/projects/${id}/reset`, { method: 'POST' }),
  listSaveSlots: (id: string) => request<SaveSlot[]>(`/api/v1/projects/${id}/save-slots`),
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
  uploadBuildingModel: async (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Project>(`/api/v1/projects/${id}/building-model`, { method: 'POST', body });
  },
  createDrawings: (
    id: string,
    sliceHeightM: number,
    upAxis: UpAxis,
    modelUnits: ModelUnits,
    includeDimensions = true,
  ) => request<Job>(`/api/v1/projects/${id}/drawings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      slice_height_m: sliceHeightM,
      up_axis: upAxis,
      model_units: modelUnits,
      include_dimensions: includeDimensions,
    }),
  }),
  uploadAsset: async (id: string, category: AssetCategory, slot: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    body.append('label', file.name.replace(/\.[^.]+$/, ''));
    const route = category === 'flooring' || category === 'walls'
      ? `/api/v1/projects/${id}/assets/${category}/${slot}`
      : `/api/v1/projects/${id}/interior-assets/${category}/${slot}`;
    return request<Project>(route, { method: 'POST', body });
  },
  analyze: (
    id: string,
    planWidthM: number,
    wallHeightM: number,
    wallDetection: WallDetectionMode,
    minimumWallLengthM: number,
    planType: PlanType,
  ) => request<SceneManifest>(`/api/v1/projects/${id}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(analysisPayload(planWidthM, wallHeightM, wallDetection, minimumWallLengthM, planType)),
  }),
  compileArchitecture: (
    id: string,
    planWidthM: number,
    wallHeightM: number,
    wallDetection: WallDetectionMode,
    minimumWallLengthM: number,
    planType: PlanType,
    useVisionAi = false,
  ) => request<SceneManifest>(`/api/v1/projects/${id}/compile-architecture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(analysisPayload(
      planWidthM,
      wallHeightM,
      wallDetection,
      minimumWallLengthM,
      planType,
      useVisionAi,
    )),
  }),
  exportTrainingExample: (id: string) =>
    request<{ id: string; split: string; workspace: string; image: string; mask: string; scene: string }>(`/api/v1/projects/${id}/training-example`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed_rights: true }),
    }),
  updateMaterials: (id: string, materials: MaterialUpdate) =>
    request<SceneManifest>(`/api/v1/projects/${id}/materials`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(materials),
    }),
  architectureJsonUrl: (id: string) => absoluteUrl(`/api/v1/projects/${id}/architecture.json`)! ,
  startManualLayout: (id: string, planWidthM: number, wallHeightM: number, clearExisting = true) =>
    request<SceneManifest>(`/api/v1/projects/${id}/manual-layout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan_width_m: planWidthM,
        wall_height_m: wallHeightM,
        clear_existing: clearExisting,
      }),
    }),
  addRoom: (id: string, name: string, x: number, z: number, width: number, depth: number) =>
    request<SceneManifest>(`/api/v1/projects/${id}/rooms`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, x, z, width, depth }),
    }),
  updateRoomGeometry: (id: string, roomId: string, polygon: [number, number][]) =>
    request<SceneManifest>(`/api/v1/projects/${id}/rooms/${roomId}/geometry`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ polygon }),
    }),
  deleteRoom: (id: string, roomId: string) =>
    request<SceneManifest>(`/api/v1/projects/${id}/rooms/${roomId}`, { method: 'DELETE' }),
  updateRoom: (id: string, roomId: string, name: string) =>
    request<SceneManifest>(`/api/v1/projects/${id}/rooms/${roomId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  addOpening: (id: string, opening: OpeningPayload) =>
    request<SceneManifest>(`/api/v1/projects/${id}/openings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opening),
    }),
  updateOpening: (id: string, openingId: string, opening: Partial<OpeningPayload>) =>
    request<SceneManifest>(`/api/v1/projects/${id}/openings/${openingId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opening),
    }),
  deleteOpening: (id: string, openingId: string) =>
    request<SceneManifest>(`/api/v1/projects/${id}/openings/${openingId}`, { method: 'DELETE' }),
  interiorLibrary: () => request<InteriorLibrary>('/api/v1/interior-library'),
  addFurniture: (id: string, furniture: FurniturePayload) =>
    request<SceneManifest>(`/api/v1/projects/${id}/furniture`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(furniture),
    }),
  updateFurniture: (id: string, objectId: string, furniture: Partial<FurniturePayload>) =>
    request<SceneManifest>(`/api/v1/projects/${id}/furniture/${objectId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(furniture),
    }),
  deleteFurniture: (id: string, objectId: string) =>
    request<SceneManifest>(`/api/v1/projects/${id}/furniture/${objectId}`, { method: 'DELETE' }),
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
  getSettings: () => request<Record<string, AppSettingValue>>('/api/v1/settings'),
  saveSettings: (settings: Record<string, AppSettingValue>) =>
    request<Record<string, AppSettingValue>>('/api/v1/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),
};
