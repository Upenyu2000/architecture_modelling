export type AssetCategory = 'flooring' | 'walls' | 'kitchen' | 'living_room' | 'bathroom';
export type WallDetectionMode = 'clean' | 'balanced' | 'detailed';
export type PlanType = 'auto' | 'blueprint' | 'rendered';
export type UpAxis = 'y' | 'z';
export type ModelUnits = 'auto' | 'metres' | 'millimetres' | 'centimetres' | 'feet';

export type OpeningType =
  | 'door'
  | 'double_door'
  | 'pocket_door'
  | 'double_pocket_door'
  | 'bypass_door'
  | 'sliding_door'
  | 'double_sliding_door'
  | 'sliding_glass_door'
  | 'bifold_door'
  | 'double_bifold_door'
  | 'folding_door'
  | 'overhead_door'
  | 'revolving_door'
  | 'open_passage'
  | 'window'
  | 'fixed_window'
  | 'casement_window'
  | 'double_casement_window'
  | 'glider_window'
  | 'garden_window'
  | 'bay_window'
  | 'bow_window'
  | 'double_hung_window'
  | 'vertical_sliding_window'
  | 'horizontal_sliding_window';

export interface WallSegment {
  id: string;
  start: [number, number];
  end: [number, number];
  height: number;
  thickness: number;
  wall_type: 'exterior' | 'interior' | 'partition';
  confidence: number;
}

export interface RoomShape {
  id: string;
  name: string;
  polygon: [number, number][];
  area_m2: number;
  centroid: [number, number];
  room_type: string;
  width_m?: number | null;
  depth_m?: number | null;
  extracted_dimension?: string | null;
  label_confidence: number;
}

export interface Opening {
  id: string;
  opening_type: OpeningType;
  position: [number, number];
  width: number;
  height: number;
  rotation_deg: number;
  wall_id?: string | null;
  placement_ratio?: number | null;
  swing_direction: 'clockwise' | 'counterclockwise' | 'none';
  hinge_side: 'left' | 'right' | 'centre' | 'none';
  swing_angle_deg: number;
  sill_height: number;
  interactive: boolean;
  default_open: boolean;
  source: 'heuristic' | 'model' | 'vision' | 'manual';
  confidence: number;
}

export interface OpeningPayload {
  opening_type: OpeningType;
  wall_id: string;
  placement_ratio: number;
  width?: number;
  height?: number;
  swing_direction: 'clockwise' | 'counterclockwise' | 'none';
  hinge_side: 'left' | 'right' | 'centre' | 'none';
  swing_angle_deg: number;
  sill_height: number;
  interactive: boolean;
  default_open: boolean;
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
  source: string;
  confidence: number;
}

export interface ArchitecturalObject {
  id: string;
  object_type: string;
  asset_id: string;
  category: 'furniture' | 'fixture' | 'utility' | 'structure';
  room_id?: string | null;
  coordinates: [number, number, number];
  rotation_deg: number;
  scale: [number, number, number];
  size: [number, number, number];
  source: 'vision' | 'symbol_heuristic' | 'room_inference' | 'user';
  confidence: number;
}

export interface MaterialSpec {
  name: string;
  material_type: string;
  hex_color: string;
  roughness: number;
  metallic: number;
  specular: number;
  texture_url?: string | null;
  normal_url?: string | null;
  displacement_url?: string | null;
  texture_scale: number;
}

export interface SceneMaterials {
  palette_name: string;
  floor_global: MaterialSpec;
  walls_global: MaterialSpec;
  exterior_walls: MaterialSpec;
  accent: MaterialSpec;
  fixture_metal: MaterialSpec;
}

export interface ProjectMetadata {
  scale_ratio: string;
  detected_rooms: number;
  detected_openings: number;
  detected_objects: number;
  parser_version: string;
  source_plan_type: string;
  structural_confidence: number;
  ocr_status: string;
  extracted_labels: string[];
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
  openings: Opening[];
  fixtures_and_furniture: ArchitecturalObject[];
  materials: SceneMaterials;
  project_metadata: ProjectMetadata;
  first_person_start?: [number, number, number] | null;
  collision_segments: [[number, number], [number, number]][];
  ceiling_height_m: number;
  cutaway_height_m: number;
  floor_texture_url?: string | null;
  wall_texture_url?: string | null;
  reference_image_url?: string | null;
  detection_preview_url?: string | null;
  architecture_json_url?: string | null;
  wall_detection_mode: string;
  plan_type: PlanType;
  layout_mode: 'automatic' | 'manual';
  warnings: string[];
}

export interface MaterialUpdate {
  palette_name: string;
  floor_type: string;
  floor_color: string;
  wall_color: string;
  exterior_color: string;
  accent_color: string;
  roughness: number;
  cutaway_height_m: number;
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
  floorplan?: { filename: string; preview_url: string; width_px?: number; height_px?: number } | null;
  building_model?: { filename: string; url: string; format: string; size_bytes: number } | null;
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
  has_drawings: boolean;
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
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
