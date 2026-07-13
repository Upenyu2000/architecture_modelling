import type { FurnitureMaterialProfile } from './components/ProceduralFurniture';

export interface FurniturePayload {
  object_type: string;
  room_id?: string | null;
  x: number;
  z: number;
  rotation_deg: number;
  width: number;
  height: number;
  depth: number;
  style: string;
  material: FurnitureMaterialProfile;
  color: string;
  reference_asset_key?: string | null;
}

export interface InteriorLibraryItem {
  type: string;
  size: [number, number, number];
}

export interface InteriorLibrary {
  objects: InteriorLibraryItem[];
  styles: string[];
  materials: FurnitureMaterialProfile[];
}
