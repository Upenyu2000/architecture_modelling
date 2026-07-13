export type AssetCategory = 'flooring' | 'walls' | 'kitchen' | 'living_room' | 'bathroom';

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
  warnings: string[];
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  floorplan?: { filename: string; preview_url: string } | null;
  assets: Record<string, { filename: string; url: string; status: string }>;
  status: string;
  scene?: SceneManifest | null;
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
  created_at: string;
  updated_at: string;
}
