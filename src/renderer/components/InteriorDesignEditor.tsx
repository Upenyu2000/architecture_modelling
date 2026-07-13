import { useEffect, useMemo, useRef, useState } from 'react';
import { Armchair, Image as ImageIcon, Plus, Save, Trash2 } from 'lucide-react';
import { absoluteUrl } from '../lib/api';
import type { FurniturePayload } from '../interior-types';
import type { ArchitecturalObject, Project, SceneManifest } from '../types';
import { decodeFurnitureAssetId, type FurnitureMaterialProfile } from './ProceduralFurniture';

interface Props {
  project: Project;
  scene: SceneManifest;
  busy: boolean;
  onAddFurniture: (payload: FurniturePayload) => Promise<void>;
  onUpdateFurniture: (objectId: string, payload: Partial<FurniturePayload>) => Promise<void>;
  onDeleteFurniture: (objectId: string) => Promise<void>;
}

const LIBRARY: Record<string, [number, number, number]> = {
  sofa: [2.25, 0.92, 0.98],
  sectional_sofa: [2.8, 0.95, 1.45],
  armchair: [1.0, 0.92, 0.95],
  chair: [0.62, 0.92, 0.62],
  bed: [1.65, 0.72, 2.05],
  coffee_table: [1.15, 0.46, 0.68],
  dining_table: [1.9, 0.78, 1.0],
  tv_unit: [1.8, 0.65, 0.45],
  wardrobe: [1.8, 2.1, 0.6],
  kitchen_island: [2.1, 0.94, 0.95],
  countertop: [2.1, 0.94, 0.7],
  cabinetry: [2.4, 0.92, 0.62],
  fridge: [0.9, 2.0, 0.75],
  stove: [0.75, 0.92, 0.68],
  washing_machine: [0.68, 0.9, 0.68],
  dryer: [0.68, 0.9, 0.68],
  sink: [0.65, 0.9, 0.55],
  toilet: [0.48, 0.78, 0.72],
  bathtub: [1.75, 0.62, 0.82],
  vanity: [1.1, 0.9, 0.55],
  light_fixture: [0.5, 0.65, 0.5],
};

const MATERIALS: FurnitureMaterialProfile[] = ['fabric', 'leather', 'oak', 'walnut', 'stone', 'porcelain', 'chrome', 'painted_metal'];
const STYLES = ['modern', 'contemporary', 'classic', 'minimal', 'industrial', 'scandinavian', 'luxury'];

function defaultPayload(scene: SceneManifest): FurniturePayload {
  const room = scene.rooms[0];
  const [width, height, depth] = LIBRARY.sofa;
  return {
    object_type: 'sofa',
    room_id: room?.id ?? null,
    x: room?.centroid[0] ?? scene.width_m / 2,
    z: room?.centroid[1] ?? scene.depth_m / 2,
    rotation_deg: 0,
    width,
    height,
    depth,
    style: 'modern',
    material: 'fabric',
    color: '#486B5A',
    reference_asset_key: null,
  };
}

function payloadFromObject(item: ArchitecturalObject): FurniturePayload {
  const style = decodeFurnitureAssetId(item.asset_id);
  return {
    object_type: item.object_type,
    room_id: item.room_id ?? null,
    x: item.coordinates[0],
    z: item.coordinates[2],
    rotation_deg: item.rotation_deg,
    width: item.size[0],
    height: item.size[1],
    depth: item.size[2],
    style: style.style,
    material: style.material,
    color: style.color,
    reference_asset_key: style.referenceAssetKey ?? null,
  };
}

function pointInPolygon(point: [number, number], polygon: [number, number][]): boolean {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index, index += 1) {
    const [xi, zi] = polygon[index];
    const [xj, zj] = polygon[previous];
    const crosses = (zi > point[1]) !== (zj > point[1])
      && point[0] < ((xj - xi) * (point[1] - zi)) / ((zj - zi) || 1e-9) + xi;
    if (crosses) inside = !inside;
  }
  return inside;
}

export function InteriorDesignEditor({ project, scene, busy, onAddFurniture, onUpdateFurniture, onDeleteFurniture }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<FurniturePayload>(() => defaultPayload(scene));
  const selected = scene.fixtures_and_furniture.find((item) => item.id === selectedId) ?? null;
  const assetKeys = useMemo(() => Object.keys(project.assets).filter((key) => !key.startsWith('flooring/') && !key.startsWith('walls/')), [project.assets]);
  const referenceUrl = draft.reference_asset_key ? absoluteUrl(project.assets[draft.reference_asset_key]?.url) : undefined;

  useEffect(() => {
    if (selected) setDraft(payloadFromObject(selected));
  }, [selected?.id]);

  useEffect(() => {
    if (selectedId && !scene.fixtures_and_furniture.some((item) => item.id === selectedId)) setSelectedId(null);
  }, [scene.fixtures_and_furniture, selectedId]);

  const chooseType = (type: string) => {
    const size = LIBRARY[type] ?? [1, 1, 1];
    setDraft((current) => ({ ...current, object_type: type, width: size[0], height: size[1], depth: size[2] }));
  };

  const scenePoint = (event: React.PointerEvent<SVGElement>): [number, number] | null => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [Math.max(0, Math.min(scene.width_m, point.x)), Math.max(0, Math.min(scene.depth_m, point.y))];
  };

  const placeAt = (event: React.PointerEvent<SVGSVGElement>) => {
    if (busy) return;
    const point = scenePoint(event);
    if (!point) return;
    const room = scene.rooms.find((candidate) => pointInPolygon(point, candidate.polygon)) ?? null;
    setSelectedId(null);
    setDraft((current) => ({ ...current, x: point[0], z: point[1], room_id: room?.id ?? current.room_id ?? null }));
  };

  const add = async () => onAddFurniture(draft);
  const save = async () => {
    if (selected) await onUpdateFurniture(selected.id, draft);
  };
  const remove = async () => {
    if (!selected || !window.confirm(`Remove ${selected.object_type.replaceAll('_', ' ')}?`)) return;
    await onDeleteFurniture(selected.id);
    setSelectedId(null);
  };

  return (
    <div className="interior-editor">
      <div className="interior-stage">
        <svg ref={svgRef} viewBox={`0 0 ${scene.width_m} ${scene.depth_m}`} preserveAspectRatio="xMidYMid meet" onPointerDown={placeAt}>
          {scene.reference_image_url ? <image href={absoluteUrl(scene.reference_image_url)} x="0" y="0" width={scene.width_m} height={scene.depth_m} opacity="0.45" preserveAspectRatio="none" /> : null}
          {scene.rooms.map((room) => (
            <g key={room.id}>
              <polygon points={room.polygon.map(([x, z]) => `${x},${z}`).join(' ')} className="interior-room" />
              <text x={room.centroid[0]} y={room.centroid[1]} className="interior-room-label">{room.name}</text>
            </g>
          ))}
          {scene.fixtures_and_furniture.map((item) => {
            const width = Math.max(0.18, item.size[0]);
            const depth = Math.max(0.18, item.size[2]);
            return (
              <g
                key={item.id}
                className={item.id === selectedId ? 'interior-footprint selected' : 'interior-footprint'}
                transform={`translate(${item.coordinates[0]} ${item.coordinates[2]}) rotate(${item.rotation_deg})`}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  setSelectedId(item.id);
                  setDraft(payloadFromObject(item));
                }}
              >
                <rect x={-width / 2} y={-depth / 2} width={width} height={depth} rx={Math.min(width, depth) * 0.12} />
                <text x="0" y="0">{item.object_type.replaceAll('_', ' ')}</text>
              </g>
            );
          })}
          <g className="interior-crosshair" transform={`translate(${draft.x} ${draft.z})`}>
            <circle r={Math.max(0.09, Math.min(scene.width_m, scene.depth_m) * 0.008)} />
            <line x1="-0.3" x2="0.3" y1="0" y2="0" />
            <line x1="0" x2="0" y1="-0.3" y2="0.3" />
          </g>
        </svg>
        <div className="interior-stage-help">Click the exact position in a room. Select an existing footprint to replace or restyle it.</div>
      </div>

      <aside className="interior-controls">
        <div className="interior-heading"><Armchair size={20} /><div><strong>Interior design studio</strong><span>Detected furniture remains editable and replaceable.</span></div></div>

        <label>Furniture model
          <select value={draft.object_type} onChange={(event) => chooseType(event.target.value)}>
            {Object.keys(LIBRARY).map((type) => <option value={type} key={type}>{type.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <div className="interior-grid">
          <label>Style<select value={draft.style} onChange={(event) => setDraft((current) => ({ ...current, style: event.target.value }))}>{STYLES.map((style) => <option value={style} key={style}>{style}</option>)}</select></label>
          <label>Material<select value={draft.material} onChange={(event) => setDraft((current) => ({ ...current, material: event.target.value as FurnitureMaterialProfile }))}>{MATERIALS.map((material) => <option value={material} key={material}>{material.replaceAll('_', ' ')}</option>)}</select></label>
          <label>Colour<input type="color" value={draft.color} onChange={(event) => setDraft((current) => ({ ...current, color: event.target.value }))} /></label>
          <label>Room<select value={draft.room_id ?? ''} onChange={(event) => setDraft((current) => ({ ...current, room_id: event.target.value || null }))}><option value="">Nearest room</option>{scene.rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}</select></label>
        </div>

        <label>Image reference / texture
          <select value={draft.reference_asset_key ?? ''} onChange={(event) => setDraft((current) => ({ ...current, reference_asset_key: event.target.value || null }))}>
            <option value="">Procedural PBR material</option>
            {assetKeys.map((key) => <option value={key} key={key}>{key.replace('/', ' · ').replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        {referenceUrl ? <div className="interior-reference"><img src={referenceUrl} alt="Uploaded furniture reference" /><span><ImageIcon size={13} /> Image mapped onto the procedural furniture surface</span></div> : null}

        <div className="interior-grid three">
          <label>X (m)<input type="number" step="0.05" value={draft.x} onChange={(event) => setDraft((current) => ({ ...current, x: Number(event.target.value) }))} /></label>
          <label>Z (m)<input type="number" step="0.05" value={draft.z} onChange={(event) => setDraft((current) => ({ ...current, z: Number(event.target.value) }))} /></label>
          <label>Rotation<input type="number" step="5" value={draft.rotation_deg} onChange={(event) => setDraft((current) => ({ ...current, rotation_deg: Number(event.target.value) }))} /></label>
          <label>Width<input type="number" min="0.15" step="0.05" value={draft.width} onChange={(event) => setDraft((current) => ({ ...current, width: Number(event.target.value) }))} /></label>
          <label>Height<input type="number" min="0.1" step="0.05" value={draft.height} onChange={(event) => setDraft((current) => ({ ...current, height: Number(event.target.value) }))} /></label>
          <label>Depth<input type="number" min="0.15" step="0.05" value={draft.depth} onChange={(event) => setDraft((current) => ({ ...current, depth: Number(event.target.value) }))} /></label>
        </div>

        <div className="interior-actions">
          <button className="primary" disabled={busy} onClick={() => void add()}><Plus size={16} /> Add furniture</button>
          <button className="secondary" disabled={busy || !selected} onClick={() => void save()}><Save size={16} /> Replace / save selected</button>
          <button className="danger-icon" disabled={busy || !selected} onClick={() => void remove()}><Trash2 size={16} /> Delete</button>
        </div>
        <small className="interior-note">Floor-plan detections are proposals. Replace any result with a model, material, image reference and exact dimensions without re-running detection.</small>
      </aside>
    </div>
  );
}
