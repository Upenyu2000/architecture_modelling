import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Armchair, Hand, Image as ImageIcon, LocateFixed, Move, Pencil, Plus,
  RotateCw, Save, Trash2, ZoomIn, ZoomOut,
} from 'lucide-react';
import * as THREE from 'three';
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

type ToolMode = 'pan' | 'add' | 'move-scale' | 'edit';
type Point = [number, number];
type Bounds = { minX: number; minZ: number; maxX: number; maxZ: number; width: number; depth: number; centreX: number; centreZ: number };
type DragState =
  | { kind: 'pan'; pointerId: number; lastClientX: number; lastClientY: number }
  | { kind: 'move'; pointerId: number; objectId: string; offsetX: number; offsetZ: number }
  | { kind: 'scale'; pointerId: number; objectId: string }
  | { kind: 'rotate'; pointerId: number; objectId: string };

const MIN_ZOOM = 0.45;
const MAX_ZOOM = 5;
const PAN_STEP = 0.12;

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

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function normaliseDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

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

function pointInPolygon(point: Point, polygon: Point[]): boolean {
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

function fullPlanBounds(scene: SceneManifest): Bounds {
  const points: Point[] = [[0, 0], [scene.width_m, scene.depth_m]];
  scene.rooms.forEach((room) => points.push(...room.polygon));
  scene.walls.forEach((wall) => points.push(wall.start, wall.end));
  scene.fixtures_and_furniture.forEach((item) => {
    const halfWidth = Math.max(item.size[0], 0.2) / 2;
    const halfDepth = Math.max(item.size[2], 0.2) / 2;
    points.push(
      [item.coordinates[0] - halfWidth, item.coordinates[2] - halfDepth],
      [item.coordinates[0] + halfWidth, item.coordinates[2] + halfDepth],
    );
  });
  const xs = points.map(([x]) => x);
  const zs = points.map(([, z]) => z);
  const rawMinX = Math.min(...xs);
  const rawMaxX = Math.max(...xs);
  const rawMinZ = Math.min(...zs);
  const rawMaxZ = Math.max(...zs);
  const rawWidth = Math.max(rawMaxX - rawMinX, 1);
  const rawDepth = Math.max(rawMaxZ - rawMinZ, 1);
  const padding = Math.max(rawWidth, rawDepth) * 0.07;
  const minX = rawMinX - padding;
  const maxX = rawMaxX + padding;
  const minZ = rawMinZ - padding;
  const maxZ = rawMaxZ + padding;
  return {
    minX,
    maxX,
    minZ,
    maxZ,
    width: maxX - minX,
    depth: maxZ - minZ,
    centreX: (minX + maxX) / 2,
    centreZ: (minZ + maxZ) / 2,
  };
}

export function InteriorDesignEditor({ project, scene, busy, onAddFurniture, onUpdateFurniture, onDeleteFurniture }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const draftRef = useRef<FurniturePayload>(defaultPayload(scene));
  const [tool, setTool] = useState<ToolMode>('add');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraftState] = useState<FurniturePayload>(() => defaultPayload(scene));
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>([0, 0]);
  const selected = scene.fixtures_and_furniture.find((item) => item.id === selectedId) ?? null;
  const bounds = useMemo(() => fullPlanBounds(scene), [scene]);
  const assetKeys = useMemo(() => Object.keys(project.assets).filter((key) => !key.startsWith('flooring/') && !key.startsWith('walls/')), [project.assets]);
  const referenceUrl = draft.reference_asset_key ? absoluteUrl(project.assets[draft.reference_asset_key]?.url) : undefined;
  const viewport = useMemo(() => {
    const width = bounds.width / zoom;
    const depth = bounds.depth / zoom;
    const centreX = bounds.centreX + pan[0];
    const centreZ = bounds.centreZ + pan[1];
    return { x: centreX - width / 2, z: centreZ - depth / 2, width, depth };
  }, [bounds, pan, zoom]);

  const setDraft = (value: FurniturePayload | ((current: FurniturePayload) => FurniturePayload)) => {
    setDraftState((current) => {
      const next = typeof value === 'function' ? value(current) : value;
      draftRef.current = next;
      return next;
    });
  };

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    if (selected) setDraft(payloadFromObject(selected));
  }, [selected?.id]);

  useEffect(() => {
    if (selectedId && !scene.fixtures_and_furniture.some((item) => item.id === selectedId)) setSelectedId(null);
  }, [scene.fixtures_and_furniture, selectedId]);

  useEffect(() => {
    setZoom(1);
    setPan([0, 0]);
  }, [scene.width_m, scene.depth_m]);

  const chooseType = (type: string) => {
    const size = LIBRARY[type] ?? [1, 1, 1];
    setDraft((current) => ({ ...current, object_type: type, width: size[0], height: size[1], depth: size[2] }));
  };

  const scenePoint = (event: { clientX: number; clientY: number }): Point | null => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [point.x, point.y];
  };

  const roomAt = (point: Point) => scene.rooms.find((candidate) => pointInPolygon(point, candidate.polygon)) ?? null;

  const beginPan = (event: React.PointerEvent<SVGElement>) => {
    dragRef.current = { kind: 'pan', pointerId: event.pointerId, lastClientX: event.clientX, lastClientY: event.clientY };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const beginFurnitureMove = (event: React.PointerEvent<SVGGElement>, item: ArchitecturalObject) => {
    event.stopPropagation();
    const payload = item.id === selectedId ? draftRef.current : payloadFromObject(item);
    setSelectedId(item.id);
    setDraft(payload);
    if (tool === 'pan' || event.button === 1 || (event.button === 0 && event.shiftKey)) {
      beginPan(event);
      return;
    }
    if (tool !== 'move-scale' && tool !== 'edit') return;
    const point = scenePoint(event);
    if (!point) return;
    dragRef.current = {
      kind: 'move',
      pointerId: event.pointerId,
      objectId: item.id,
      offsetX: point[0] - payload.x,
      offsetZ: point[1] - payload.z,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const beginScale = (event: React.PointerEvent<SVGCircleElement>, item: ArchitecturalObject) => {
    event.stopPropagation();
    const payload = item.id === selectedId ? draftRef.current : payloadFromObject(item);
    setSelectedId(item.id);
    setDraft(payload);
    dragRef.current = { kind: 'scale', pointerId: event.pointerId, objectId: item.id };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const beginRotate = (event: React.PointerEvent<SVGCircleElement>, item: ArchitecturalObject) => {
    event.stopPropagation();
    const payload = item.id === selectedId ? draftRef.current : payloadFromObject(item);
    setSelectedId(item.id);
    setDraft(payload);
    dragRef.current = { kind: 'rotate', pointerId: event.pointerId, objectId: item.id };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const handleStagePointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (busy) return;
    if (tool === 'pan' || event.button === 1 || (event.button === 0 && event.shiftKey)) {
      beginPan(event);
      return;
    }
    const point = scenePoint(event);
    if (!point) return;
    if (tool === 'add') {
      const room = roomAt(point);
      setSelectedId(null);
      setDraft((current) => ({
        ...current,
        x: clamp(point[0], bounds.minX, bounds.maxX),
        z: clamp(point[1], bounds.minZ, bounds.maxZ),
        room_id: room?.id ?? current.room_id ?? null,
      }));
      return;
    }
    setSelectedId(null);
  };

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.kind === 'pan') {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const dx = ((event.clientX - drag.lastClientX) / Math.max(rect.width, 1)) * viewport.width;
      const dz = ((event.clientY - drag.lastClientY) / Math.max(rect.height, 1)) * viewport.depth;
      setPan(([x, z]) => [x - dx, z - dz]);
      drag.lastClientX = event.clientX;
      drag.lastClientY = event.clientY;
      return;
    }
    const point = scenePoint(event);
    if (!point || drag.objectId !== selectedId) return;
    if (drag.kind === 'move') {
      const x = clamp(point[0] - drag.offsetX, bounds.minX, bounds.maxX);
      const z = clamp(point[1] - drag.offsetZ, bounds.minZ, bounds.maxZ);
      const room = roomAt([x, z]);
      setDraft((current) => ({ ...current, x, z, room_id: room?.id ?? current.room_id ?? null }));
      return;
    }
    if (drag.kind === 'scale') {
      const current = draftRef.current;
      const radians = THREE.MathUtils.degToRad(current.rotation_deg);
      const dx = point[0] - current.x;
      const dz = point[1] - current.z;
      const localX = Math.cos(radians) * dx + Math.sin(radians) * dz;
      const localZ = -Math.sin(radians) * dx + Math.cos(radians) * dz;
      setDraft((value) => ({
        ...value,
        width: clamp(Math.abs(localX) * 2, 0.15, Math.max(bounds.width, 0.15)),
        depth: clamp(Math.abs(localZ) * 2, 0.15, Math.max(bounds.depth, 0.15)),
      }));
      return;
    }
    if (drag.kind === 'rotate') {
      const current = draftRef.current;
      const raw = normaliseDegrees((Math.atan2(point[1] - current.z, point[0] - current.x) * 180) / Math.PI + 90);
      const rotation = event.altKey ? raw : Math.round(raw / 5) * 5;
      setDraft((value) => ({ ...value, rotation_deg: normaliseDegrees(rotation) }));
    }
  };

  const finishDrag = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
    if (drag.kind !== 'pan' && selectedId && !busy) {
      void onUpdateFurniture(selectedId, draftRef.current);
    }
  };

  const handleWheel = (event: React.WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    setZoom((current) => clamp(current * factor, MIN_ZOOM, MAX_ZOOM));
  };

  const fitFullPlan = () => {
    setZoom(1);
    setPan([0, 0]);
  };

  const panView = (dx: number, dz: number) => {
    setPan(([x, z]) => [x + dx * bounds.width * PAN_STEP / zoom, z + dz * bounds.depth * PAN_STEP / zoom]);
  };

  const add = async () => {
    await onAddFurniture(draftRef.current);
  };

  const save = async () => {
    if (selectedId) await onUpdateFurniture(selectedId, draftRef.current);
  };

  const remove = async () => {
    if (!selected || !window.confirm(`Remove ${selected.object_type.replaceAll('_', ' ')}?`)) return;
    await onDeleteFurniture(selected.id);
    setSelectedId(null);
  };

  return (
    <div className="interior-editor">
      <div className={`interior-stage tool-${tool}`}>
        <div className="interior-canvas-toolbar" onPointerDown={(event) => event.stopPropagation()}>
          <div className="interior-tool-group" role="group" aria-label="Interior canvas tools">
            <button className={tool === 'pan' ? 'active' : ''} onClick={() => setTool('pan')}><Hand size={15} /> Pan view</button>
            <button className={tool === 'move-scale' ? 'active' : ''} onClick={() => setTool('move-scale')}><Move size={15} /> Move / scale</button>
            <button className={tool === 'add' ? 'active' : ''} onClick={() => setTool('add')}><Plus size={15} /> Add furniture</button>
            <button className={tool === 'edit' ? 'active' : ''} onClick={() => setTool('edit')}><Pencil size={15} /> Edit furniture</button>
          </div>
          <div className="interior-zoom-group" role="group" aria-label="Interior plan zoom controls">
            <button title="Zoom out" onClick={() => setZoom((current) => clamp(current / 1.2, MIN_ZOOM, MAX_ZOOM))}><ZoomOut size={16} /></button>
            <output>{Math.round(zoom * 100)}%</output>
            <button title="Zoom in" onClick={() => setZoom((current) => clamp(current * 1.2, MIN_ZOOM, MAX_ZOOM))}><ZoomIn size={16} /></button>
            <button title="Fit the complete floor plan" onClick={fitFullPlan}><LocateFixed size={16} /> Full plan</button>
          </div>
          <div className="interior-pan-pad" role="group" aria-label="Pan full floor plan">
            <button className="pan-up" title="Pan up" onClick={() => panView(0, -1)}>↑</button>
            <button className="pan-left" title="Pan left" onClick={() => panView(-1, 0)}>←</button>
            <button className="pan-centre" title="Centre full plan" onClick={fitFullPlan}>●</button>
            <button className="pan-right" title="Pan right" onClick={() => panView(1, 0)}>→</button>
            <button className="pan-down" title="Pan down" onClick={() => panView(0, 1)}>↓</button>
          </div>
        </div>

        <svg
          ref={svgRef}
          viewBox={`${viewport.x} ${viewport.z} ${viewport.width} ${viewport.depth}`}
          preserveAspectRatio="xMidYMid meet"
          onPointerDown={handleStagePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
          onWheel={handleWheel}
        >
          <rect x={bounds.minX} y={bounds.minZ} width={bounds.width} height={bounds.depth} className="interior-plan-background" />
          {scene.reference_image_url ? <image href={absoluteUrl(scene.reference_image_url)} x="0" y="0" width={scene.width_m} height={scene.depth_m} opacity="0.48" preserveAspectRatio="xMidYMid meet" /> : null}
          {scene.rooms.map((room) => (
            <g key={room.id}>
              <polygon points={room.polygon.map(([x, z]) => `${x},${z}`).join(' ')} className="interior-room" />
              <text x={room.centroid[0]} y={room.centroid[1]} className="interior-room-label">{room.name}</text>
            </g>
          ))}
          <g className="interior-wall-network">
            {scene.walls.map((wall) => <line key={wall.id} x1={wall.start[0]} y1={wall.start[1]} x2={wall.end[0]} y2={wall.end[1]} style={{ strokeWidth: Math.max(wall.render_thickness ?? wall.thickness, 0.06) }} />)}
          </g>
          {scene.fixtures_and_furniture.map((item) => {
            const isSelected = item.id === selectedId;
            const width = Math.max(0.18, isSelected ? draft.width : item.size[0]);
            const depth = Math.max(0.18, isSelected ? draft.depth : item.size[2]);
            const x = isSelected ? draft.x : item.coordinates[0];
            const z = isSelected ? draft.z : item.coordinates[2];
            const rotation = isSelected ? draft.rotation_deg : item.rotation_deg;
            const label = isSelected ? draft.object_type : item.object_type;
            const handleRadius = Math.max(0.08, Math.min(width, depth) * 0.09);
            return (
              <g
                key={item.id}
                className={isSelected ? 'interior-footprint selected' : 'interior-footprint'}
                transform={`translate(${x} ${z}) rotate(${rotation})`}
                onPointerDown={(event) => beginFurnitureMove(event, item)}
              >
                <rect x={-width / 2} y={-depth / 2} width={width} height={depth} rx={Math.min(width, depth) * 0.12} />
                <line className="interior-facing-line" x1="0" y1="0" x2="0" y2={-depth / 2} />
                <text x="0" y="0">{label.replaceAll('_', ' ')}</text>
                {isSelected ? (
                  <>
                    <line className="interior-rotation-stem" x1="0" y1={-depth / 2} x2="0" y2={-depth / 2 - Math.max(0.25, depth * 0.22)} />
                    <circle className="interior-rotation-handle" cx="0" cy={-depth / 2 - Math.max(0.25, depth * 0.22)} r={handleRadius} onPointerDown={(event) => beginRotate(event, item)} />
                    <circle className="interior-scale-handle" cx={width / 2} cy={depth / 2} r={handleRadius} onPointerDown={(event) => beginScale(event, item)} />
                  </>
                ) : null}
              </g>
            );
          })}
          {tool === 'add' ? (
            <g className="interior-crosshair" transform={`translate(${draft.x} ${draft.z})`}>
              <circle r={Math.max(0.09, Math.min(scene.width_m, scene.depth_m) * 0.008)} />
              <line x1="-0.3" x2="0.3" y1="0" y2="0" />
              <line x1="0" x2="0" y1="-0.3" y2="0.3" />
            </g>
          ) : null}
        </svg>
        <div className="interior-stage-help">
          {tool === 'pan' ? 'Drag the plan to move left, right, up or down. Use the wheel to zoom.'
            : tool === 'move-scale' ? 'Drag furniture to move it. Drag the corner handle to resize and the round top handle to rotate.'
              : tool === 'edit' ? 'Select furniture on the full plan, then edit, rotate, replace or delete it.'
                : 'Click anywhere on the complete floor plan to position new furniture.'}
        </div>
      </div>

      <aside className="interior-controls">
        <div className="interior-heading"><Armchair size={20} /><div><strong>Interior design studio</strong><span>Full-plan furniture placement and editing.</span></div></div>
        <div className="interior-selection-status">
          <strong>{selected ? selected.object_type.replaceAll('_', ' ') : 'No furniture selected'}</strong>
          <span>{selected ? 'Move, resize, rotate, restyle, replace or remove this item.' : 'Choose Edit furniture or Move / scale, then select an item on the canvas.'}</span>
        </div>

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
          <label>Rotation<input type="number" step="5" value={draft.rotation_deg} onChange={(event) => setDraft((current) => ({ ...current, rotation_deg: normaliseDegrees(Number(event.target.value)) }))} /></label>
          <label>Width<input type="number" min="0.15" step="0.05" value={draft.width} onChange={(event) => setDraft((current) => ({ ...current, width: Number(event.target.value) }))} /></label>
          <label>Height<input type="number" min="0.1" step="0.05" value={draft.height} onChange={(event) => setDraft((current) => ({ ...current, height: Number(event.target.value) }))} /></label>
          <label>Depth<input type="number" min="0.15" step="0.05" value={draft.depth} onChange={(event) => setDraft((current) => ({ ...current, depth: Number(event.target.value) }))} /></label>
        </div>

        <div className="interior-rotation-row">
          <button disabled={!selected || busy} onClick={() => setDraft((current) => ({ ...current, rotation_deg: normaliseDegrees(current.rotation_deg - 15) }))}><RotateCw size={15} className="rotate-left-icon" /> −15°</button>
          <button disabled={!selected || busy} onClick={() => setDraft((current) => ({ ...current, rotation_deg: normaliseDegrees(current.rotation_deg + 15) }))}><RotateCw size={15} /> +15°</button>
        </div>

        <div className="interior-actions">
          <button className="primary" disabled={busy} onClick={() => void add()}><Plus size={16} /> Add furniture</button>
          <button className="secondary" disabled={busy || !selected} onClick={() => void save()}><Save size={16} /> Save selected changes</button>
          <button className="danger-icon" disabled={busy || !selected} onClick={() => void remove()}><Trash2 size={16} /> Remove furniture</button>
        </div>
        <small className="interior-note">The canvas always fits the complete building first. Furniture changes made by dragging are saved when the pointer is released; numeric and material changes are saved with “Save selected changes”.</small>
      </aside>
    </div>
  );
}
