import { useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, DoorOpen, Magnet, Plus, Save, Trash2 } from 'lucide-react';
import type { Opening, OpeningPayload, OpeningType, SceneManifest, WallSegment } from '../types';

interface Props {
  scene: SceneManifest;
  referenceUrl?: string;
  busy: boolean;
  onAddOpening: (payload: OpeningPayload) => Promise<void>;
  onUpdateOpening: (openingId: string, payload: Partial<OpeningPayload>) => Promise<void>;
  onDeleteOpening: (openingId: string) => Promise<void>;
}

interface LibraryItem {
  value: OpeningType;
  label: string;
  group: 'Doors' | 'Windows' | 'Openings';
  width: number;
  height: number;
}

type DirectDraft = OpeningPayload & {
  position: [number, number];
  rotation_deg: number;
  snap_to_wall: boolean;
  plan_width_m: number;
  wall_height_m: number;
};

export const OPENING_LIBRARY: LibraryItem[] = [
  { value: 'door', label: 'Single hinged door', group: 'Doors', width: 0.9, height: 2.1 },
  { value: 'double_door', label: 'Double door', group: 'Doors', width: 1.8, height: 2.1 },
  { value: 'pocket_door', label: 'Pocket door', group: 'Doors', width: 0.9, height: 2.1 },
  { value: 'double_pocket_door', label: 'Double pocket door', group: 'Doors', width: 1.8, height: 2.1 },
  { value: 'bypass_door', label: 'Bypass sliding door', group: 'Doors', width: 1.5, height: 2.1 },
  { value: 'sliding_door', label: 'Sliding door', group: 'Doors', width: 1.5, height: 2.2 },
  { value: 'double_sliding_door', label: 'Double sliding door', group: 'Doors', width: 2.4, height: 2.2 },
  { value: 'sliding_glass_door', label: 'Sliding glass door', group: 'Doors', width: 2.2, height: 2.2 },
  { value: 'bifold_door', label: 'Bi-fold door', group: 'Doors', width: 0.9, height: 2.1 },
  { value: 'double_bifold_door', label: 'Double bi-fold door', group: 'Doors', width: 1.8, height: 2.1 },
  { value: 'folding_door', label: 'Folding / accordion door', group: 'Doors', width: 1.5, height: 2.1 },
  { value: 'overhead_door', label: 'Overhead / garage door', group: 'Doors', width: 2.4, height: 2.3 },
  { value: 'revolving_door', label: 'Revolving door', group: 'Doors', width: 2.1, height: 2.3 },
  { value: 'open_passage', label: 'Archway / wall opening', group: 'Openings', width: 1.2, height: 2.2 },
  { value: 'fixed_window', label: 'Fixed window', group: 'Windows', width: 1.2, height: 1.2 },
  { value: 'casement_window', label: 'Single casement window', group: 'Windows', width: 0.9, height: 1.2 },
  { value: 'double_casement_window', label: 'Double casement window', group: 'Windows', width: 1.6, height: 1.2 },
  { value: 'glider_window', label: 'Glider window', group: 'Windows', width: 1.4, height: 1.2 },
  { value: 'garden_window', label: 'Garden window', group: 'Windows', width: 1.6, height: 1.2 },
  { value: 'bay_window', label: 'Bay window', group: 'Windows', width: 2.0, height: 1.35 },
  { value: 'bow_window', label: 'Bow window', group: 'Windows', width: 2.4, height: 1.35 },
  { value: 'double_hung_window', label: 'Double-hung window', group: 'Windows', width: 1.0, height: 1.3 },
  { value: 'vertical_sliding_window', label: 'Vertical sliding window', group: 'Windows', width: 0.9, height: 1.3 },
  { value: 'horizontal_sliding_window', label: 'Horizontal sliding window', group: 'Windows', width: 1.5, height: 1.1 },
];

const WINDOW_TYPES = new Set<OpeningType>(OPENING_LIBRARY.filter((item) => item.group === 'Windows').map((item) => item.value));
const PASSIVE_TYPES = new Set<OpeningType>([...WINDOW_TYPES, 'open_passage']);

function itemFor(type: OpeningType): LibraryItem {
  return OPENING_LIBRARY.find((item) => item.value === type)
    ?? { value: type, label: type.replaceAll('_', ' '), group: 'Doors', width: 0.9, height: 2.1 };
}

function initialPayload(scene: SceneManifest): DirectDraft {
  const item = OPENING_LIBRARY[0];
  return {
    opening_type: item.value,
    wall_id: '',
    placement_ratio: 0.5,
    position: [scene.width_m / 2, scene.depth_m / 2],
    rotation_deg: 0,
    snap_to_wall: true,
    plan_width_m: scene.width_m,
    wall_height_m: scene.wall_height_m,
    width: item.width,
    height: item.height,
    swing_direction: 'clockwise',
    hinge_side: 'left',
    swing_angle_deg: 90,
    sill_height: 0.9,
    interactive: true,
    default_open: false,
  };
}

function payloadFromOpening(scene: SceneManifest, opening: Opening): DirectDraft {
  return {
    opening_type: opening.opening_type,
    wall_id: opening.wall_id ?? '',
    placement_ratio: opening.placement_ratio ?? 0.5,
    position: opening.position,
    rotation_deg: opening.rotation_deg,
    snap_to_wall: true,
    plan_width_m: scene.width_m,
    wall_height_m: scene.wall_height_m,
    width: opening.width,
    height: opening.height,
    swing_direction: opening.swing_direction,
    hinge_side: opening.hinge_side,
    swing_angle_deg: opening.swing_angle_deg,
    sill_height: opening.sill_height,
    interactive: opening.interactive,
    default_open: opening.default_open,
  };
}

function projectRatio(wall: WallSegment, point: [number, number]): number {
  const dx = wall.end[0] - wall.start[0];
  const dz = wall.end[1] - wall.start[1];
  const lengthSquared = dx * dx + dz * dz;
  if (lengthSquared < 1e-8) return 0.5;
  return Math.max(0, Math.min(1, ((point[0] - wall.start[0]) * dx + (point[1] - wall.start[1]) * dz) / lengthSquared));
}

function projectedPoint(wall: WallSegment, ratio: number): [number, number] {
  return [
    wall.start[0] + (wall.end[0] - wall.start[0]) * ratio,
    wall.start[1] + (wall.end[1] - wall.start[1]) * ratio,
  ];
}

function nearestWall(scene: SceneManifest, point: [number, number]): { wall: WallSegment; ratio: number; distance: number } | null {
  let best: { wall: WallSegment; ratio: number; distance: number } | null = null;
  for (const wall of scene.walls) {
    const ratio = projectRatio(wall, point);
    const projected = projectedPoint(wall, ratio);
    const distance = Math.hypot(projected[0] - point[0], projected[1] - point[1]);
    if (!best || distance < best.distance) best = { wall, ratio, distance };
  }
  return best;
}

function openingColour(opening: Opening): string {
  if (opening.wall_id == null) return '#ea6f74';
  if (WINDOW_TYPES.has(opening.opening_type)) return '#78c8ef';
  if (opening.opening_type === 'open_passage') return '#d7a861';
  return opening.source === 'manual' ? '#77e19d' : '#f0c66a';
}

export function OpeningEditor({ scene, referenceUrl, busy, onAddOpening, onUpdateOpening, onDeleteOpening }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [selectedOpeningId, setSelectedOpeningId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DirectDraft>(() => initialPayload(scene));
  const selectedOpening = scene.openings.find((item) => item.id === selectedOpeningId) ?? null;
  const grouped = useMemo(() => ['Doors', 'Windows', 'Openings'] as const, []);

  useEffect(() => {
    if (selectedOpening) setDraft(payloadFromOpening(scene, selectedOpening));
  }, [selectedOpening?.id]);

  useEffect(() => {
    setDraft((current) => ({ ...current, plan_width_m: scene.width_m, wall_height_m: scene.wall_height_m }));
    if (selectedOpeningId && !scene.openings.some((opening) => opening.id === selectedOpeningId)) setSelectedOpeningId(null);
  }, [scene.width_m, scene.wall_height_m, scene.openings, selectedOpeningId]);

  const scenePoint = (event: React.PointerEvent<SVGElement>): [number, number] | null => {
    const svg = svgRef.current;
    if (!svg) return null;
    const matrix = svg.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [
      Math.max(0, Math.min(scene.width_m, point.x)),
      Math.max(0, Math.min(scene.depth_m, point.y)),
    ];
  };

  const placeAt = (point: [number, number]) => {
    const candidate = draft.snap_to_wall ? nearestWall(scene, point) : null;
    const snapDistance = Math.max(0.5, Math.min(1.2, (draft.width ?? 0.9) * 0.55));
    const snapped = candidate && candidate.distance <= snapDistance ? candidate : null;
    setSelectedOpeningId(null);
    setDraft((current) => ({
      ...current,
      position: snapped ? projectedPoint(snapped.wall, snapped.ratio) : point,
      wall_id: snapped?.wall.id ?? '',
      placement_ratio: snapped?.ratio ?? 0.5,
      rotation_deg: snapped
        ? Math.atan2(snapped.wall.end[1] - snapped.wall.start[1], snapped.wall.end[0] - snapped.wall.start[0]) * 180 / Math.PI
        : current.rotation_deg,
    }));
  };

  const chooseWall = (wall: WallSegment, event: React.PointerEvent<SVGLineElement>) => {
    event.stopPropagation();
    const point = scenePoint(event) ?? projectedPoint(wall, 0.5);
    const ratio = projectRatio(wall, point);
    setSelectedOpeningId(null);
    setDraft((current) => ({
      ...current,
      wall_id: wall.id,
      placement_ratio: ratio,
      position: projectedPoint(wall, ratio),
      rotation_deg: Math.atan2(wall.end[1] - wall.start[1], wall.end[0] - wall.start[0]) * 180 / Math.PI,
    }));
  };

  const chooseType = (type: OpeningType) => {
    const item = itemFor(type);
    const passive = PASSIVE_TYPES.has(type);
    setDraft((current) => ({
      ...current,
      opening_type: type,
      width: item.width,
      height: item.height,
      swing_direction: passive ? 'none' : current.swing_direction === 'none' ? 'clockwise' : current.swing_direction,
      hinge_side: passive ? 'none' : current.hinge_side === 'none' ? 'left' : current.hinge_side,
      interactive: !passive,
      default_open: type === 'open_passage',
      sill_height: WINDOW_TYPES.has(type) ? Math.max(0.6, current.sill_height) : 0,
    }));
  };

  const add = async () => onAddOpening(draft);
  const save = async () => {
    if (selectedOpening) await onUpdateOpening(selectedOpening.id, draft);
  };
  const remove = async () => {
    if (!selectedOpening || !window.confirm(`Delete ${itemFor(selectedOpening.opening_type).label}?`)) return;
    await onDeleteOpening(selectedOpening.id);
    setSelectedOpeningId(null);
  };

  const draftRotation = draft.rotation_deg * Math.PI / 180;
  const draftDx = Math.cos(draftRotation) * (draft.width ?? 0.9) / 2;
  const draftDz = Math.sin(draftRotation) * (draft.width ?? 0.9) / 2;

  return (
    <div className="opening-editor">
      <div className="opening-stage">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${scene.width_m} ${scene.depth_m}`}
          preserveAspectRatio="xMidYMid meet"
          onPointerDown={(event) => {
            const point = scenePoint(event);
            if (point) placeAt(point);
          }}
        >
          {referenceUrl ? <image href={referenceUrl} x="0" y="0" width={scene.width_m} height={scene.depth_m} opacity="0.72" preserveAspectRatio="none" pointerEvents="none" /> : null}
          {scene.rooms.map((room) => <polygon key={room.id} points={room.polygon.map(([x, z]) => `${x},${z}`).join(' ')} className="opening-room" />)}
          {scene.walls.map((wall, index) => (
            <g key={wall.id}>
              <line x1={wall.start[0]} y1={wall.start[1]} x2={wall.end[0]} y2={wall.end[1]} className={wall.id === draft.wall_id ? 'opening-wall selected' : 'opening-wall'} onPointerDown={(event) => chooseWall(wall, event)} />
              <text x={(wall.start[0] + wall.end[0]) / 2} y={(wall.start[1] + wall.end[1]) / 2} className="wall-index">W{index + 1}</text>
            </g>
          ))}
          {scene.openings.map((opening) => {
            const rotation = opening.rotation_deg * Math.PI / 180;
            const dx = Math.cos(rotation) * opening.width / 2;
            const dz = Math.sin(rotation) * opening.width / 2;
            return (
              <g key={opening.id} className={opening.id === selectedOpeningId ? 'opening-symbol selected' : 'opening-symbol'} onPointerDown={(event) => {
                event.stopPropagation();
                setSelectedOpeningId(opening.id);
                setDraft(payloadFromOpening(scene, opening));
              }}>
                <line x1={opening.position[0] - dx} y1={opening.position[1] - dz} x2={opening.position[0] + dx} y2={opening.position[1] + dz} stroke={openingColour(opening)} />
                <circle cx={opening.position[0]} cy={opening.position[1]} r={Math.max(0.08, Math.min(scene.width_m, scene.depth_m) * 0.009)} fill={openingColour(opening)} />
                <text x={opening.position[0]} y={opening.position[1] - 0.16}>{itemFor(opening.opening_type).label}</text>
              </g>
            );
          })}
          {!selectedOpening ? (
            <g className="opening-draft-marker" pointerEvents="none">
              <line x1={draft.position[0] - draftDx} y1={draft.position[1] - draftDz} x2={draft.position[0] + draftDx} y2={draft.position[1] + draftDz} />
              <circle cx={draft.position[0]} cy={draft.position[1]} r={Math.max(0.1, Math.min(scene.width_m, scene.depth_m) * 0.012)} />
              <line x1={draft.position[0] - 0.22} y1={draft.position[1]} x2={draft.position[0] + 0.22} y2={draft.position[1]} />
              <line x1={draft.position[0]} y1={draft.position[1] - 0.22} x2={draft.position[0]} y2={draft.position[1] + 0.22} />
            </g>
          ) : null}
        </svg>
        <div className="opening-click-hint"><Crosshair size={15} /> Click the exact door or window position on the uploaded plan</div>
      </div>

      <aside className="opening-controls">
        <div className="opening-heading">
          <DoorOpen size={20} />
          <div><strong>Direct door and window placement</strong><span>Works before rooms or walls are detected. Nearby walls are optional snap targets.</span></div>
        </div>

        <label>Feature type
          <select value={draft.opening_type} onChange={(event) => chooseType(event.target.value as OpeningType)}>
            {grouped.map((group) => <optgroup key={group} label={group}>{OPENING_LIBRARY.filter((item) => item.group === group).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</optgroup>)}
          </select>
        </label>

        <label className="checkbox-row"><input type="checkbox" checked={draft.snap_to_wall} onChange={(event) => setDraft((current) => ({ ...current, snap_to_wall: event.target.checked }))} /><span><Magnet size={13} /> Snap click to nearest wall</span></label>

        <label>Attached wall
          <select value={draft.wall_id} onChange={(event) => {
            const wall = scene.walls.find((item) => item.id === event.target.value);
            if (!wall) {
              setDraft((current) => ({ ...current, wall_id: '' }));
              return;
            }
            const ratio = projectRatio(wall, draft.position);
            setDraft((current) => ({ ...current, wall_id: wall.id, placement_ratio: ratio, position: projectedPoint(wall, ratio) }));
          }}>
            <option value="">Free placement — attach later</option>
            {scene.walls.map((wall, index) => <option key={wall.id} value={wall.id}>Wall {index + 1} · {wall.wall_type}</option>)}
          </select>
        </label>

        {draft.wall_id ? <label>Position along wall <span>{Math.round(draft.placement_ratio * 100)}%</span><input type="range" min="0" max="1" step="0.01" value={draft.placement_ratio} onChange={(event) => {
          const ratio = Number(event.target.value);
          const wall = scene.walls.find((item) => item.id === draft.wall_id);
          setDraft((current) => ({ ...current, placement_ratio: ratio, position: wall ? projectedPoint(wall, ratio) : current.position }));
        }} /></label> : null}

        <div className="opening-number-grid">
          <label>X position<input type="number" min="0" max={scene.width_m} step="0.05" value={draft.position[0]} onChange={(event) => setDraft((current) => ({ ...current, position: [Number(event.target.value), current.position[1]], wall_id: '' }))} /></label>
          <label>Y position<input type="number" min="0" max={scene.depth_m} step="0.05" value={draft.position[1]} onChange={(event) => setDraft((current) => ({ ...current, position: [current.position[0], Number(event.target.value)], wall_id: '' }))} /></label>
          <label>Width (m)<input type="number" min="0.2" step="0.05" value={draft.width ?? 0.9} onChange={(event) => setDraft((current) => ({ ...current, width: Number(event.target.value) }))} /></label>
          <label>Height (m)<input type="number" min="0.2" step="0.05" value={draft.height ?? 2.1} onChange={(event) => setDraft((current) => ({ ...current, height: Number(event.target.value) }))} /></label>
          {!draft.wall_id ? <label>Rotation<input type="number" min="-360" max="360" step="5" value={draft.rotation_deg} onChange={(event) => setDraft((current) => ({ ...current, rotation_deg: Number(event.target.value) }))} /></label> : null}
          {WINDOW_TYPES.has(draft.opening_type) ? <label>Sill (m)<input type="number" min="0" step="0.05" value={draft.sill_height} onChange={(event) => setDraft((current) => ({ ...current, sill_height: Number(event.target.value) }))} /></label> : null}
          {!PASSIVE_TYPES.has(draft.opening_type) ? <label>Open angle<input type="number" min="0" max="180" step="5" value={draft.swing_angle_deg} onChange={(event) => setDraft((current) => ({ ...current, swing_angle_deg: Number(event.target.value) }))} /></label> : null}
        </div>

        {!PASSIVE_TYPES.has(draft.opening_type) ? <div className="opening-number-grid">
          <label>Hinge<select value={draft.hinge_side} onChange={(event) => setDraft((current) => ({ ...current, hinge_side: event.target.value as OpeningPayload['hinge_side'] }))}><option value="left">Left</option><option value="right">Right</option><option value="centre">Centre</option></select></label>
          <label>Swing<select value={draft.swing_direction} onChange={(event) => setDraft((current) => ({ ...current, swing_direction: event.target.value as OpeningPayload['swing_direction'] }))}><option value="clockwise">Clockwise</option><option value="counterclockwise">Counterclockwise</option><option value="none">No swing</option></select></label>
        </div> : null}

        {!PASSIVE_TYPES.has(draft.opening_type) ? <>
          <label className="checkbox-row"><input type="checkbox" checked={draft.interactive} onChange={(event) => setDraft((current) => ({ ...current, interactive: event.target.checked }))} /> Interactive in first person</label>
          <label className="checkbox-row"><input type="checkbox" checked={draft.default_open} onChange={(event) => setDraft((current) => ({ ...current, default_open: event.target.checked }))} /> Start open</label>
        </> : null}

        <div className="opening-actions">
          <button className="primary" disabled={busy} onClick={() => void add()}><Plus size={16} /> Add at clicked position</button>
          <button className="secondary" disabled={busy || !selectedOpening} onClick={() => void save()}><Save size={16} /> Save selected</button>
          <button className="danger-icon" disabled={busy || !selectedOpening} onClick={() => void remove()}><Trash2 size={16} /> Delete</button>
        </div>

        <div className="opening-legend">
          <span><i className="manual-opening" /> Attached manual</span><span><i className="free-opening" /> Waiting for wall</span><span><i className="detected-opening" /> AI detected</span><span><i className="window-opening" /> Window</span>
        </div>
      </aside>
    </div>
  );
}
