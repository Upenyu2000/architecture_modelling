export type AssetCategory = 'flooring' | 'walls' | 'kitchen' | 'living_room' | 'bathroom';
export type WallDetectionMode = 'clean' | 'balanced' | 'detailed';
export type ModelUnits = 'auto' | 'metres' | 'millimetres' | 'centimetres' | 'feet';
export type UpAxis = 'y' | 'z';

export interface WallSegment {
  id: string;
  start: [number, number];
  end: [number, number];
  height: number;
  thickness: number;
}

export interface RoomShape {
  id: string;
  name: string;
  polygon: [number, number][];
  area_m2: number;
  centroid: [number, number];
}

export interface SceneAsset {
  id: string;
  category: AssetCategory;
  slot: string;
  label: string;
  room_id?: string | null;
  position: [number, number, number];
  rotation_y: number;
  size: [number, number, number];
  source_url?: string | null;
  mesh_url?: string | null;
}

export interface SceneManifest {
  project_id: string;
  width_m: number;
  depth_m: number;
  wall_height_m: number;
  walls: WallSegment[];
  rooms: RoomShape[];
  assets: SceneAsset[];
  camera_path: [number, number, number][];
  floor_texture_url?: string | null;
  wall_texture_url?: string | null;
  detection_preview_url?: string | null;
  wall_detection_mode?: WallDetectionMode;
  warnings: string[];
}

export interface BuildingModelFile {
  filename: string;
  url: string;
  format: string;
  size_bytes: number;
}

export interface DrawingFile {
  kind: string;
  format: string;
  filename: string;
  path: string;
  url: string;
}

export interface DrawingSet {
  project_id: string;
  source_filename: string;
  created_at: string;
  slice_height_m: number;
  up_axis: UpAxis;
  model_units: string;
  bounds_m: [number, number, number];
  files: DrawingFile[];
  warnings: string[];
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  floorplan?: { filename: string; preview_url: string } | null;
  building_model?: BuildingModelFile | null;
  assets: Record<string, { filename: string; url: string; status: string }>;
  status: string;
  scene?: SceneManifest | null;
  drawing_set?: DrawingSet | null;
}

export interface SaveSlot {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  status: string;
  floorplan_filename?: string | null;
  building_model_filename?: string | null;
  preview_url?: string | null;
  asset_count: number;
  has_scene: boolean;
  has_drawings?: boolean;
}

export interface Job {
  id: string;
  project_id: string;
  kind: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  output_url?: string | null;
  output_path?: string | null;
  error?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
