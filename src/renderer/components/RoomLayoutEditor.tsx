import { useEffect, useMemo, useRef, useState } from 'react';
import { Move, Plus, Scaling, Trash2 } from 'lucide-react';
import type { RoomShape, SceneManifest } from '../types';

type Point = [number, number];
type Handle = 'nw' | 'ne' | 'se' | 'sw';

type DragState = {
  pointerId: number;
  roomId: string;
  mode: 'move' | 'scale';
  start: Point;
  original: Point[];
  handle?: Handle;
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

function roomPoints(room: RoomShape, draft: { roomId: string; polygon: Point[] } | null): Point[] {
  return draft?.roomId === room.id ? draft.polygon : room.polygon;
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

  useEffect(() => {
    if (!scene.rooms.some((room) => room.id === selectedId)) {
      setSelectedId(scene.rooms[0]?.id ?? '');
    }
  }, [scene.rooms, selectedId]);

  const selected = scene.rooms.find((room) => room.id === selectedId) ?? null;
  const selectedPolygon = selected ? roomPoints(selected, draft) : null;
  const selectedBounds = useMemo(
    () => selectedPolygon?.length ? bounds(selectedPolygon) : null,
    [selectedPolygon],
  );

  useEffect(() => {
    setNameDraft(selected?.name ?? '');
  }, [selected?.id, selected?.name]);

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

  const beginMove = (event: React.PointerEvent<SVGPolygonElement>, room: RoomShape) => {
    if (busy) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(room.id);
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
    if (busy || !selected || !selectedPolygon) return;
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

  const movePointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const current = toWorld(event);
    const originalBounds = bounds(drag.original);

    if (drag.mode === 'move') {
      let dx = current[0] - drag.start[0];
      let dz = current[1] - drag.start[1];
      dx = clamp(dx, -originalBounds.minX, scene.width_m - originalBounds.maxX);
      dz = clamp(dz, -originalBounds.minZ, scene.depth_m - originalBounds.maxZ);
      setDraft({
        roomId: drag.roomId,
        polygon: drag.original.map(([x, z]) => [
          Math.round((x + dx) * 1000) / 1000,
          Math.round((z + dz) * 1000) / 1000,
        ]),
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
      polygon: drag.original.map(([x, z]) => [
        Math.round((minX + ((x - originalBounds.minX) / oldWidth) * newWidth) * 1000) / 1000,
        Math.round((minZ + ((z - originalBounds.minZ) / oldDepth) * newDepth) * 1000) / 1000,
      ]),
    });
  };

  const finishPointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    dragRef.current = null;
    if (svgRef.current?.hasPointerCapture(event.pointerId)) {
      svgRef.current.releasePointerCapture(event.pointerId);
    }
    if (draft?.roomId === drag.roomId) {
      const polygon = draft.polygon;
      setDraft(null);
      void onUpdateRoom(drag.roomId, polygon);
    }
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

  const handleRadius = Math.max(scene.width_m, scene.depth_m) * 0.012;
  const activePoints = selectedPolygon?.map(([x, z]) => `${x},${z}`).join(' ') ?? '';

  return (
    <div className="room-layout-editor">
      <div className="room-editor-toolbar">
        <div>
          <strong>Room layout editor</strong>
          <span>Drag a room to move it. Drag a corner handle to resize it.</span>
        </div>
        <div className="room-editor-actions">
          <button disabled={busy} onClick={() => void onAddRoom()}><Plus size={16} /> Add room</button>
          <button className="danger-icon" disabled={busy || !selected} onClick={deleteSelected}><Trash2 size={16} /> Remove</button>
        </div>
      </div>

      <div className="room-editor-stage" style={{ aspectRatio: `${scene.width_m} / ${scene.depth_m}` }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${scene.width_m} ${scene.depth_m}`}
          preserveAspectRatio="none"
          onPointerMove={movePointer}
          onPointerUp={finishPointer}
          onPointerCancel={finishPointer}
        >
          <rect width={scene.width_m} height={scene.depth_m} fill="#08140f" />
          {referenceUrl ? (
            <image
              href={referenceUrl}
              x="0"
              y="0"
              width={scene.width_m}
              height={scene.depth_m}
              preserveAspectRatio="none"
              opacity="0.72"
            />
          ) : null}
          {scene.rooms.map((room, index) => {
            const polygon = roomPoints(room, draft);
            const isSelected = room.id === selectedId;
            return (
              <g key={room.id}>
                <polygon
                  points={polygon.map(([x, z]) => `${x},${z}`).join(' ')}
                  className={isSelected ? 'editable-room selected' : 'editable-room'}
                  style={{ '--room-index': index } as React.CSSProperties}
                  onPointerDown={(event) => beginMove(event, room)}
                />
                <text
                  x={room.centroid[0]}
                  y={room.centroid[1]}
                  className="room-label"
                  vectorEffect="non-scaling-stroke"
                >
                  {room.name}
                </text>
              </g>
            );
          })}
          {selectedBounds && selected ? (
            <g className="selection-box">
              <polygon points={activePoints} fill="none" vectorEffect="non-scaling-stroke" />
              {([
                ['nw', selectedBounds.minX, selectedBounds.minZ],
                ['ne', selectedBounds.maxX, selectedBounds.minZ],
                ['se', selectedBounds.maxX, selectedBounds.maxZ],
                ['sw', selectedBounds.minX, selectedBounds.maxZ],
              ] as [Handle, number, number][]).map(([handle, x, z]) => (
                <circle
                  key={handle}
                  cx={x}
                  cy={z}
                  r={handleRadius}
                  vectorEffect="non-scaling-stroke"
                  onPointerDown={(event) => beginScale(event, handle)}
                />
              ))}
            </g>
          ) : null}
        </svg>
        {scene.rooms.length === 0 ? (
          <div className="empty-room-layout">
            <Plus size={28} />
            <strong>Add the first room</strong>
            <span>Trace the plan room by room. Shared edges become one wall.</span>
          </div>
        ) : null}
      </div>

      <div className="room-editor-footer">
        <div className="editor-help"><Move size={15} /> Move room <Scaling size={15} /> Resize from corners</div>
        {selected && selectedBounds ? (
          <div className="selected-room-fields">
            <label>Room name
              <input
                value={nameDraft}
                maxLength={80}
                onChange={(event) => setNameDraft(event.target.value)}
                onBlur={saveName}
                onKeyDown={(event) => { if (event.key === 'Enter') saveName(); }}
              />
            </label>
            <span>{(selectedBounds.maxX - selectedBounds.minX).toFixed(2)} m × {(selectedBounds.maxZ - selectedBounds.minZ).toFixed(2)} m</span>
            <span>{selected.area_m2.toFixed(2)} m²</span>
          </div>
        ) : <span>Select a room to edit it.</span>}
      </div>
    </div>
  );
}
