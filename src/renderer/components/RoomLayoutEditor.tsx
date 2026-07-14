import { useEffect, useMemo, useRef, useState } from 'react';
import { Maximize2, Move, Plus, Trash2, ZoomIn, ZoomOut } from 'lucide-react';
import type { RoomShape, SceneManifest } from '../types';

type Point = [number, number];
type Handle = 'nw' | 'ne' | 'se' | 'sw';
type EditMode = 'move' | 'vertices' | 'add-point' | 'remove-point';

type DragState = {
  pointerId: number;
  roomId: string;
  mode: 'move' | 'scale' | 'vertex';
  start: Point;
  original: Point[];
  handle?: Handle;
  vertexIndex?: number;
};

interface Props {
  scene: SceneManifest;
  referenceUrl?: string;
  busy: boolean;
  onAddRoom: () => Promise<void>;
  onUpdateRoom: (roomId: string, polygon: Point[]) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
  onRenameRoom: (roomId: string, name: string) => Promise<void>;
}

const MIN_ZOOM = 0.45;
const MAX_ZOOM = 3;
const DEFAULT_ZOOM = 0.8;

function bounds(points: Point[]) {
  const xs = points.map(([x]) => x);
  const zs = points.map(([, z]) => z);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minZ: Math.min(...zs),
    maxZ: Math.max(...zs),
  };
}

function clamp(value: number, lower: number, upper: number) {
  return Math.max(lower, Math.min(upper, value));
}

function round(value: number) {
  return Math.round(value * 1000) / 1000;
}

function roomPoints(room: RoomShape, draft: { roomId: string; polygon: Point[] } | null): Point[] {
  return draft?.roomId === room.id ? draft.polygon : room.polygon;
}

function polygonCentroid(points: Point[]): Point {
  if (points.length < 3) return points[0] ?? [0, 0];
  let twiceArea = 0;
  let x = 0;
  let z = 0;
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[(index + 1) % points.length];
    const cross = current[0] * next[1] - next[0] * current[1];
    twiceArea += cross;
    x += (current[0] + next[0]) * cross;
    z += (current[1] + next[1]) * cross;
  }
  if (Math.abs(twiceArea) < 0.000001) {
    return [
      points.reduce((sum, point) => sum + point[0], 0) / points.length,
      points.reduce((sum, point) => sum + point[1], 0) / points.length,
    ];
  }
  return [x / (3 * twiceArea), z / (3 * twiceArea)];
}

function projectToSegment(point: Point, start: Point, end: Point): { point: Point; distance: number } {
  const dx = end[0] - start[0];
  const dz = end[1] - start[1];
  const lengthSquared = dx * dx + dz * dz;
  if (lengthSquared <= 0.000001) {
    return { point: start, distance: Math.hypot(point[0] - start[0], point[1] - start[1]) };
  }
  const t = clamp(((point[0] - start[0]) * dx + (point[1] - start[1]) * dz) / lengthSquared, 0, 1);
  const projected: Point = [start[0] + dx * t, start[1] + dz * t];
  return { point: projected, distance: Math.hypot(point[0] - projected[0], point[1] - projected[1]) };
}

function presetPolygon(kind: 'rhombus' | 'l-shape' | 'octagon', current: Point[]): Point[] {
  const box = bounds(current);
  const width = Math.max(0.8, box.maxX - box.minX);
  const depth = Math.max(0.8, box.maxZ - box.minZ);
  const cx = (box.minX + box.maxX) / 2;
  const cz = (box.minZ + box.maxZ) / 2;
  if (kind === 'rhombus') return [[cx, box.minZ], [box.maxX, cz], [cx, box.maxZ], [box.minX, cz]];
  if (kind === 'l-shape') {
    return [
      [box.minX, box.minZ], [box.maxX, box.minZ], [box.maxX, box.minZ + depth * 0.48],
      [box.minX + width * 0.52, box.minZ + depth * 0.48], [box.minX + width * 0.52, box.maxZ],
      [box.minX, box.maxZ],
    ];
  }
  const insetX = width * 0.22;
  const insetZ = depth * 0.22;
  return [
    [box.minX + insetX, box.minZ], [box.maxX - insetX, box.minZ], [box.maxX, box.minZ + insetZ],
    [box.maxX, box.maxZ - insetZ], [box.maxX - insetX, box.maxZ], [box.minX + insetX, box.maxZ],
    [box.minX, box.maxZ - insetZ], [box.minX, box.minZ + insetZ],
  ];
}

export function RoomLayoutEditor({
  scene,
  referenceUrl,
  busy,
  onAddRoom,
  onUpdateRoom,
  onDeleteRoom,
  onRenameRoom,
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [selectedId, setSelectedId] = useState(scene.rooms[0]?.id ?? '');
  const [draft, setDraft] = useState<{ roomId: string; polygon: Point[] } | null>(null);
  const [nameDraft, setNameDraft] = useState('');
  const [editMode, setEditMode] = useState<EditMode>('vertices');
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [snapSize, setSnapSize] = useState(0.1);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);

  useEffect(() => {
    if (!scene.rooms.some((room) => room.id === selectedId)) setSelectedId(scene.rooms[0]?.id ?? '');
  }, [scene.rooms, selectedId]);

  const selected = scene.rooms.find((room) => room.id === selectedId) ?? null;
  const selectedPolygon = selected ? roomPoints(selected, draft) : null;
  const selectedBounds = useMemo(
    () => selectedPolygon?.length ? bounds(selectedPolygon) : null,
    [selectedPolygon],
  );
  const selectedCentroid = useMemo(
    () => selectedPolygon?.length ? polygonCentroid(selectedPolygon) : null,
    [selectedPolygon],
  );

  useEffect(() => { setNameDraft(selected?.name ?? ''); }, [selected?.id, selected?.name]);

  const snapPoint = (point: Point): Point => {
    if (!snapEnabled || snapSize <= 0) return [round(point[0]), round(point[1])];
    return [
      round(clamp(Math.round(point[0] / snapSize) * snapSize, 0, scene.width_m)),
      round(clamp(Math.round(point[1] / snapSize) * snapSize, 0, scene.depth_m)),
    ];
  };

  const toWorld = (event: React.PointerEvent<SVGSVGElement | SVGElement>): Point => {
    const svg = svgRef.current;
    if (!svg) return [0, 0];
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const matrix = svg.getScreenCTM()?.inverse();
    if (!matrix) return [0, 0];
    const transformed = point.matrixTransform(matrix);
    return [
      clamp(transformed.x, 0, scene.width_m),
      clamp(transformed.y, 0, scene.depth_m),
    ];
  };

  const commitPolygon = (roomId: string, polygon: Point[]) => {
    const cleaned = polygon.map(snapPoint);
    setDraft(null);
    void onUpdateRoom(roomId, cleaned);
  };

  const beginMove = (event: React.PointerEvent<SVGPolygonElement>, room: RoomShape) => {
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(room.id);
    if (busy || editMode !== 'move') return;
    const original = roomPoints(room, draft).map(([x, z]) => [x, z] as Point);
    setDraft({ roomId: room.id, polygon: original });
    dragRef.current = {
      pointerId: event.pointerId,
      roomId: room.id,
      mode: 'move',
      start: toWorld(event),
      original,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const beginScale = (event: React.PointerEvent<SVGCircleElement>, handle: Handle) => {
    if (busy || !selected || !selectedPolygon || editMode !== 'move') return;
    event.preventDefault();
    event.stopPropagation();
    const original = selectedPolygon.map(([x, z]) => [x, z] as Point);
    setDraft({ roomId: selected.id, polygon: original });
    dragRef.current = {
      pointerId: event.pointerId,
      roomId: selected.id,
      mode: 'scale',
      start: toWorld(event),
      original,
      handle,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const beginVertex = (event: React.PointerEvent<SVGCircleElement>, index: number) => {
    if (busy || !selected || !selectedPolygon) return;
    event.preventDefault();
    event.stopPropagation();
    if (editMode === 'remove-point') {
      if (selectedPolygon.length <= 3) {
        window.alert('A room must keep at least three points.');
        return;
      }
      commitPolygon(selected.id, selectedPolygon.filter((_point, pointIndex) => pointIndex !== index));
      return;
    }
    if (editMode !== 'vertices') return;
    const original = selectedPolygon.map(([x, z]) => [x, z] as Point);
    setDraft({ roomId: selected.id, polygon: original });
    dragRef.current = {
      pointerId: event.pointerId,
      roomId: selected.id,
      mode: 'vertex',
      start: toWorld(event),
      original,
      vertexIndex: index,
    };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const addPointToEdge = (event: React.PointerEvent<SVGLineElement>, edgeIndex: number) => {
    if (busy || !selected || !selectedPolygon || editMode !== 'add-point') return;
    event.preventDefault();
    event.stopPropagation();
    const start = selectedPolygon[edgeIndex];
    const end = selectedPolygon[(edgeIndex + 1) % selectedPolygon.length];
    const projected = snapPoint(projectToSegment(toWorld(event), start, end).point);
    const polygon = [...selectedPolygon];
    polygon.splice(edgeIndex + 1, 0, projected);
    commitPolygon(selected.id, polygon);
    setEditMode('vertices');
  };

  const movePointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const current = toWorld(event);
    const originalBounds = bounds(drag.original);

    if (drag.mode === 'vertex') {
      const index = drag.vertexIndex ?? 0;
      const polygon = drag.original.map(([x, z]) => [x, z] as Point);
      polygon[index] = snapPoint(current);
      setDraft({ roomId: drag.roomId, polygon });
      return;
    }

    if (drag.mode === 'move') {
      let dx = current[0] - drag.start[0];
      let dz = current[1] - drag.start[1];
      dx = clamp(dx, -originalBounds.minX, scene.width_m - originalBounds.maxX);
      dz = clamp(dz, -originalBounds.minZ, scene.depth_m - originalBounds.maxZ);
      setDraft({
        roomId: drag.roomId,
        polygon: drag.original.map(([x, z]) => snapPoint([x + dx, z + dz])),
      });
      return;
    }

    const minimum = 0.4;
    let { minX, maxX, minZ, maxZ } = originalBounds;
    const handle = drag.handle ?? 'se';
    if (handle.includes('w')) minX = clamp(current[0], 0, maxX - minimum);
    if (handle.includes('e')) maxX = clamp(current[0], minX + minimum, scene.width_m);
    if (handle.includes('n')) minZ = clamp(current[1], 0, maxZ - minimum);
    if (handle.includes('s')) maxZ = clamp(current[1], minZ + minimum, scene.depth_m);

    const oldWidth = Math.max(originalBounds.maxX - originalBounds.minX, 0.001);
    const oldDepth = Math.max(originalBounds.maxZ - originalBounds.minZ, 0.001);
    const newWidth = maxX - minX;
    const newDepth = maxZ - minZ;
    setDraft({
      roomId: drag.roomId,
      polygon: drag.original.map(([x, z]) => snapPoint([
        minX + ((x - originalBounds.minX) / oldWidth) * newWidth,
        minZ + ((z - originalBounds.minZ) / oldDepth) * newDepth,
      ])),
    });
  };

  const finishPointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
    if (draft?.roomId === drag.roomId) commitPolygon(drag.roomId, draft.polygon);
  };

  const deleteSelected = () => {
    if (!selected) return;
    if (!window.confirm(`Remove “${selected.name}” from the active layout?`)) return;
    setSelectedId('');
    void onDeleteRoom(selected.id);
  };

  const saveName = () => {
    if (!selected) return;
    const name = nameDraft.trim();
    if (!name || name === selected.name) return;
    void onRenameRoom(selected.id, name);
  };

  const applyPreset = (kind: 'rhombus' | 'l-shape' | 'octagon') => {
    if (!selected || !selectedPolygon) return;
    commitPolygon(selected.id, presetPolygon(kind, selectedPolygon));
    setEditMode('vertices');
  };

  const setClampedZoom = (value: number) => setZoom(clamp(value, MIN_ZOOM, MAX_ZOOM));
  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const multiplier = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    setZoom((current) => clamp(current * multiplier, MIN_ZOOM, MAX_ZOOM));
  };

  const viewport = useMemo(() => {
    const width = scene.width_m / zoom;
    const height = scene.depth_m / zoom;
    return {
      x: (scene.width_m - width) / 2,
      y: (scene.depth_m - height) / 2,
      width,
      height,
      value: `${(scene.width_m - width) / 2} ${(scene.depth_m - height) / 2} ${width} ${height}`,
    };
  }, [scene.width_m, scene.depth_m, zoom]);

  const handleRadius = Math.max(scene.width_m, scene.depth_m) * 0.011 / zoom;
  const vertexRadius = Math.max(scene.width_m, scene.depth_m) * 0.009 / zoom;
  const activePoints = selectedPolygon?.map(([x, z]) => `${x},${z}`).join(' ') ?? '';
  const gridStep = Math.max(0.1, snapSize || 0.1);

  return (
    <div className="room-layout-editor">
      <div className="room-editor-toolbar">
        <div>
          <strong>Free-form room editor</strong>
          <span>Move rooms, drag vertices, insert edge points and zoom out to inspect the complete building footprint.</span>
        </div>
        <div className="room-editor-actions">
          <button disabled={busy} onClick={() => void onAddRoom()}><Plus size={16} /> Add room</button>
          <button className="danger-icon" disabled={busy || !selected} onClick={deleteSelected}><Trash2 size={16} /> Remove room</button>
        </div>
      </div>

      <div className="room-editor-modebar">
        <button className={editMode === 'move' ? 'active' : ''} onClick={() => setEditMode('move')}><Move size={15} /> Move / scale</button>
        <button className={editMode === 'vertices' ? 'active' : ''} onClick={() => setEditMode('vertices')}>Edit vertices</button>
        <button className={editMode === 'add-point' ? 'active' : ''} disabled={!selected || (selectedPolygon?.length ?? 0) >= 64} onClick={() => setEditMode('add-point')}><Plus size={15} /> Add point</button>
        <button className={editMode === 'remove-point' ? 'active' : ''} disabled={!selected || (selectedPolygon?.length ?? 0) <= 3} onClick={() => setEditMode('remove-point')}><Trash2 size={15} /> Remove point</button>
        <span className="mode-divider" />
        <button disabled={!selected} onClick={() => applyPreset('rhombus')}>Rhombus</button>
        <button disabled={!selected} onClick={() => applyPreset('l-shape')}>L-shape</button>
        <button disabled={!selected} onClick={() => applyPreset('octagon')}>Octagon</button>
        <label className="snap-control"><input type="checkbox" checked={snapEnabled} onChange={(event) => setSnapEnabled(event.target.checked)} /> Snap</label>
        <label className="snap-size">Grid <input type="number" min="0.02" max="2" step="0.05" value={snapSize} onChange={(event) => setSnapSize(Math.max(0.02, Number(event.target.value) || 0.1))} /> m</label>
        <div className="plan-zoom-controls" aria-label="Floor plan zoom controls">
          <button type="button" title="Zoom out" onClick={() => setClampedZoom(zoom / 1.2)}><ZoomOut size={15} /></button>
          <input aria-label="Floor plan zoom" type="range" min={MIN_ZOOM} max={MAX_ZOOM} step="0.05" value={zoom} onChange={(event) => setClampedZoom(Number(event.target.value))} />
          <button type="button" title="Zoom in" onClick={() => setClampedZoom(zoom * 1.2)}><ZoomIn size={15} /></button>
          <button type="button" title="Fit complete plan" onClick={() => setZoom(DEFAULT_ZOOM)}><Maximize2 size={15} /></button>
          <output>{Math.round(zoom * 100)}%</output>
        </div>
      </div>

      <div className="room-editor-stage" style={{ aspectRatio: `${scene.width_m} / ${scene.depth_m}` }} onWheel={handleWheel}>
        <svg
          ref={svgRef}
          viewBox={viewport.value}
          preserveAspectRatio="xMidYMid meet"
          onPointerMove={movePointer}
          onPointerUp={finishPointer}
          onPointerCancel={finishPointer}
        >
          <defs>
            <pattern id="room-grid" width={gridStep} height={gridStep} patternUnits="userSpaceOnUse">
              <path d={`M ${gridStep} 0 L 0 0 0 ${gridStep}`} fill="none" stroke="rgba(91,151,112,.18)" strokeWidth="0.015" />
            </pattern>
          </defs>
          <rect x={viewport.x} y={viewport.y} width={viewport.width} height={viewport.height} fill="#020704" />
          <rect width={scene.width_m} height={scene.depth_m} fill="#08140f" />
          {referenceUrl ? <image href={referenceUrl} x="0" y="0" width={scene.width_m} height={scene.depth_m} preserveAspectRatio="none" opacity="0.72" /> : null}
          <rect width={scene.width_m} height={scene.depth_m} fill="url(#room-grid)" pointerEvents="none" />
          {scene.rooms.map((room, index) => {
            const polygon = roomPoints(room, draft);
            const isSelected = room.id === selectedId;
            const centroid = isSelected && selectedCentroid ? selectedCentroid : room.centroid;
            return (
              <g key={room.id}>
                <polygon
                  points={polygon.map(([x, z]) => `${x},${z}`).join(' ')}
                  className={isSelected ? 'editable-room selected' : 'editable-room'}
                  style={{ '--room-index': index } as React.CSSProperties}
                  onPointerDown={(event) => beginMove(event, room)}
                />
                <text x={centroid[0]} y={centroid[1]} className="room-label" vectorEffect="non-scaling-stroke">{room.name}</text>
              </g>
            );
          })}
          {selectedPolygon && selected ? (
            <g className={`freeform-controls mode-${editMode}`}>
              {selectedPolygon.map((point, index) => {
                const next = selectedPolygon[(index + 1) % selectedPolygon.length];
                return (
                  <line
                    key={`edge-${index}`}
                    x1={point[0]} y1={point[1]} x2={next[0]} y2={next[1]}
                    className="edge-hit-target"
                    vectorEffect="non-scaling-stroke"
                    onPointerDown={(event) => addPointToEdge(event, index)}
                  />
                );
              })}
              {(editMode === 'vertices' || editMode === 'remove-point' || editMode === 'add-point') && selectedPolygon.map(([x, z], index) => (
                <g key={`vertex-${index}`} className="vertex-control">
                  <circle cx={x} cy={z} r={vertexRadius} vectorEffect="non-scaling-stroke" onPointerDown={(event) => beginVertex(event, index)} />
                  <text x={x} y={z - vertexRadius * 1.55} vectorEffect="non-scaling-stroke">{index + 1}</text>
                </g>
              ))}
            </g>
          ) : null}
          {selectedBounds && selected && editMode === 'move' ? (
            <g className="selection-box">
              <polygon points={activePoints} fill="none" vectorEffect="non-scaling-stroke" />
              {([
                ['nw', selectedBounds.minX, selectedBounds.minZ],
                ['ne', selectedBounds.maxX, selectedBounds.minZ],
                ['se', selectedBounds.maxX, selectedBounds.maxZ],
                ['sw', selectedBounds.minX, selectedBounds.maxZ],
              ] as [Handle, number, number][]).map(([handle, x, z]) => (
                <circle key={handle} cx={x} cy={z} r={handleRadius} vectorEffect="non-scaling-stroke" onPointerDown={(event) => beginScale(event, handle)} />
              ))}
            </g>
          ) : null}
        </svg>
        {scene.rooms.length === 0 ? (
          <div className="empty-room-layout"><Plus size={28} /><strong>Add the first room</strong><span>Add a rectangle, then insert and drag points to trace any free-form boundary.</span></div>
        ) : null}
      </div>

      <div className="room-editor-footer">
        <div className="editor-help">
          {editMode === 'move' && <><Move size={15} /> Drag room; use corner handles to scale.</>}
          {editMode === 'vertices' && <>Drag any numbered point to reshape the selected room.</>}
          {editMode === 'add-point' && <>Click an edge to insert a new point, then drag it.</>}
          {editMode === 'remove-point' && <>Click a numbered point to remove it. At least three points are required.</>}
        </div>
        {selected && selectedBounds ? (
          <div className="selected-room-fields">
            <label>Room name
              <input value={nameDraft} maxLength={80} onChange={(event) => setNameDraft(event.target.value)} onBlur={saveName} onKeyDown={(event) => { if (event.key === 'Enter') saveName(); }} />
            </label>
            <span>{selectedPolygon?.length ?? 0} points</span>
            <span>{(selectedBounds.maxX - selectedBounds.minX).toFixed(2)} m × {(selectedBounds.maxZ - selectedBounds.minZ).toFixed(2)} m</span>
            <span>{selected.area_m2.toFixed(2)} m²</span>
          </div>
        ) : <span>Select a room to edit it.</span>}
      </div>
    </div>
  );
}
