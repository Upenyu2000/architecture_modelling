import {
  Suspense, useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import type { MutableRefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  Grid, OrbitControls, OrthographicCamera, PerspectiveCamera, PointerLockControls, useTexture,
} from '@react-three/drei';
import { Armchair, Braces, Box, DoorOpen, Edit3, Footprints, Map, ScanLine } from 'lucide-react';
import * as THREE from 'three';
import { absoluteUrl } from '../lib/api';
import type { FurniturePayload } from '../interior-types';
import type {
  MaterialSpec, Opening, OpeningPayload, OpeningType, Project, RoomShape, SceneManifest, WallSegment,
} from '../types';
import { InteriorDesignEditor } from './InteriorDesignEditor';
import { OpeningEditor } from './OpeningEditor';
import { FurnitureModel, decodeFurnitureAssetId } from './ProceduralFurniture';
import { RoomLayoutEditor } from './RoomLayoutEditor';

type Point = [number, number];
type ViewMode = 'isometric' | 'top' | 'walkthrough' | 'edit' | 'openings' | 'interior' | 'structure' | 'data';
type RenderedViewMode = 'isometric' | 'top' | 'walkthrough';

interface Props {
  project: Project | null;
  busy: boolean;
  onAddRoom: () => Promise<void>;
  onUpdateRoom: (roomId: string, polygon: Point[]) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
  onRenameRoom: (roomId: string, name: string) => Promise<void>;
  onAddOpening: (payload: OpeningPayload) => Promise<void>;
  onUpdateOpening: (openingId: string, payload: Partial<OpeningPayload>) => Promise<void>;
  onDeleteOpening: (openingId: string) => Promise<void>;
  onAddFurniture: (payload: FurniturePayload) => Promise<void>;
  onUpdateFurniture: (objectId: string, payload: Partial<FurniturePayload>) => Promise<void>;
  onDeleteFurniture: (objectId: string) => Promise<void>;
}

type ProjectedOpening = {
  opening: Opening;
  centre: number;
  start: number;
  end: number;
};

const EYE_HEIGHT = 1.7;
const DEFAULT_FOV = 88;
const DEFAULT_PLAYER_RADIUS = 0.16;
const MAX_MOVEMENT_STEP = 0.055;

const WINDOW_TYPES = new Set<OpeningType>([
  'window', 'fixed_window', 'casement_window', 'double_casement_window', 'glider_window',
  'garden_window', 'bay_window', 'bow_window', 'double_hung_window',
  'vertical_sliding_window', 'horizontal_sliding_window',
]);
const DOOR_TYPES = new Set<OpeningType>([
  'door', 'double_door', 'pocket_door', 'double_pocket_door', 'bypass_door', 'sliding_door',
  'double_sliding_door', 'sliding_glass_door', 'bifold_door', 'double_bifold_door',
  'folding_door', 'overhead_door', 'revolving_door',
]);
const SLIDING_TYPES = new Set<OpeningType>([
  'pocket_door', 'double_pocket_door', 'bypass_door', 'sliding_door', 'double_sliding_door', 'sliding_glass_door',
]);

function isWindow(opening: Opening): boolean {
  return WINDOW_TYPES.has(opening.opening_type);
}

function isDoor(opening: Opening): boolean {
  return DOOR_TYPES.has(opening.opening_type);
}

function distanceToSegment(point: THREE.Vector2, start: Point, end: Point): number {
  const a = new THREE.Vector2(start[0], start[1]);
  const b = new THREE.Vector2(end[0], end[1]);
  const segment = b.clone().sub(a);
  const lengthSquared = segment.lengthSq();
  if (lengthSquared === 0) return point.distanceTo(a);
  const t = THREE.MathUtils.clamp(point.clone().sub(a).dot(segment) / lengthSquared, 0, 1);
  return point.distanceTo(a.add(segment.multiplyScalar(t)));
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

function roomAt(scene: SceneManifest, point: Point): RoomShape | null {
  return scene.rooms.find((room) => pointInPolygon(point, room.polygon)) ?? null;
}

function boundaryDistance(point: Point, polygon: Point[]): number {
  const target = new THREE.Vector2(point[0], point[1]);
  let minimum = Number.POSITIVE_INFINITY;
  polygon.forEach((start, index) => {
    const end = polygon[(index + 1) % polygon.length];
    minimum = Math.min(minimum, distanceToSegment(target, start, end));
  });
  return minimum;
}

function roomsForOpening(scene: SceneManifest, opening: Opening): RoomShape[] {
  if (opening.room_ids?.length) {
    const linked = opening.room_ids
      .map((roomId) => scene.rooms.find((room) => room.id === roomId))
      .filter((room): room is RoomShape => Boolean(room));
    if (linked.length) return linked;
  }
  const linkedWallId = opening.wall_id ?? opening.wall_ids?.[0];
  const wall = linkedWallId ? scene.walls.find((candidate) => candidate.id === linkedWallId) : null;
  const tolerance = Math.max(0.28, (wall?.thickness ?? 0.16) * 2.8);
  return scene.rooms
    .map((room) => ({ room, distance: boundaryDistance(opening.position, room.polygon) }))
    .filter((candidate) => candidate.distance <= tolerance)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 2)
    .map((candidate) => candidate.room);
}

function openingWallIds(opening: Opening): Set<string> {
  const ids = new Set(opening.wall_ids ?? []);
  if (opening.wall_id) ids.add(opening.wall_id);
  return ids;
}

function projectOpening(wall: WallSegment, opening: Opening): ProjectedOpening | null {
  const linkedWallIds = openingWallIds(opening);
  if (linkedWallIds.size > 0 && !linkedWallIds.has(wall.id)) return null;
  const start = new THREE.Vector2(wall.start[0], wall.start[1]);
  const end = new THREE.Vector2(wall.end[0], wall.end[1]);
  const point = new THREE.Vector2(opening.position[0], opening.position[1]);
  const vector = end.clone().sub(start);
  const length = vector.length();
  if (length < 0.05) return null;
  const direction = vector.clone().divideScalar(length);
  const centre = point.clone().sub(start).dot(direction);
  const closest = start.clone().add(direction.clone().multiplyScalar(THREE.MathUtils.clamp(centre, 0, length)));
  const tolerance = Math.max(0.28, wall.thickness * 2.5);
  if (point.distanceTo(closest) > tolerance || centre < -opening.width || centre > length + opening.width) return null;
  const clearance = Math.min(Math.max(opening.width, 0.25), length);
  return {
    opening,
    centre: THREE.MathUtils.clamp(centre, 0, length),
    start: THREE.MathUtils.clamp(centre - clearance / 2, 0, length),
    end: THREE.MathUtils.clamp(centre + clearance / 2, 0, length),
  };
}

function openingsForWall(wall: WallSegment, openings: Opening[]): ProjectedOpening[] {
  return openings
    .map((opening) => projectOpening(wall, opening))
    .filter((item): item is ProjectedOpening => Boolean(item))
    .sort((a, b) => a.start - b.start);
}

function MappedMaterial({ spec, textureUrl, normalUrl }: { spec: MaterialSpec; textureUrl: string; normalUrl?: string }) {
  const diffuse = useTexture(textureUrl);
  const normal = normalUrl ? useTexture(normalUrl) : null;
  diffuse.colorSpace = THREE.SRGBColorSpace;
  diffuse.wrapS = diffuse.wrapT = THREE.RepeatWrapping;
  diffuse.repeat.set(spec.texture_scale, spec.texture_scale);
  diffuse.anisotropy = 8;
  if (normal) {
    normal.wrapS = normal.wrapT = THREE.RepeatWrapping;
    normal.repeat.set(spec.texture_scale, spec.texture_scale);
  }
  return <meshStandardMaterial map={diffuse} normalMap={normal ?? undefined} color={spec.hex_color} roughness={spec.roughness} metalness={spec.metallic} side={THREE.DoubleSide} />;
}

function PbrMaterial({ spec }: { spec: MaterialSpec }) {
  const textureUrl = absoluteUrl(spec.texture_url);
  const normalUrl = absoluteUrl(spec.normal_url);
  if (textureUrl) return <MappedMaterial spec={spec} textureUrl={textureUrl} normalUrl={normalUrl} />;
  return <meshStandardMaterial color={spec.hex_color} roughness={spec.roughness} metalness={spec.metallic} side={THREE.DoubleSide} />;
}

function WallBox({ wall, startOffset, endOffset, bottom, height, spec }: {
  wall: WallSegment;
  startOffset: number;
  endOffset: number;
  bottom: number;
  height: number;
  spec: MaterialSpec;
}) {
  const [x1, z1] = wall.start;
  const [x2, z2] = wall.end;
  const dx = x2 - x1;
  const dz = z2 - z1;
  const fullLength = Math.hypot(dx, dz);
  const length = endOffset - startOffset;
  if (fullLength < 0.01 || length < 0.025 || height < 0.025) return null;
  const ux = dx / fullLength;
  const uz = dz / fullLength;
  const middle = (startOffset + endOffset) / 2;
  const angle = Math.atan2(dz, dx);
  const offset = wall.render_offset ?? [0, 0];
  const thickness = wall.render_thickness ?? wall.thickness;
  return (
    <mesh
      position={[x1 + ux * middle + offset[0], bottom + height / 2, z1 + uz * middle + offset[1]]}
      rotation={[0, -angle, 0]}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[length, height, thickness]} />
      <PbrMaterial spec={spec} />
    </mesh>
  );
}

function Wall({ wall, scene, cutaway }: { wall: WallSegment; scene: SceneManifest; cutaway: boolean }) {
  const fullLength = Math.hypot(wall.end[0] - wall.start[0], wall.end[1] - wall.start[1]);
  const visibleHeight = cutaway ? Math.min(scene.cutaway_height_m, wall.height) : wall.height;
  const spec = wall.wall_type === 'exterior' ? scene.materials.exterior_walls : scene.materials.walls_global;
  const projected = openingsForWall(wall, scene.openings);
  const bodyIntervals: [number, number][] = [];
  let cursor = 0;
  for (const item of projected) {
    if (item.start > cursor + 0.02) bodyIntervals.push([cursor, item.start]);
    cursor = Math.max(cursor, item.end);
  }
  if (cursor < fullLength - 0.02) bodyIntervals.push([cursor, fullLength]);
  if (!projected.length) bodyIntervals.push([0, fullLength]);

  return (
    <group>
      {bodyIntervals.map(([start, end], index) => (
        <WallBox key={`body-${index}`} wall={wall} startOffset={start} endOffset={end} bottom={0} height={visibleHeight} spec={spec} />
      ))}
      {projected.map(({ opening, start, end }) => {
        if (opening.opening_type === 'open_passage') return null;
        if (isWindow(opening)) {
          const sill = Math.min(opening.sill_height ?? 0.9, visibleHeight);
          const openingTop = Math.min(sill + opening.height, visibleHeight);
          return (
            <group key={opening.id}>
              <WallBox wall={wall} startOffset={start} endOffset={end} bottom={0} height={sill} spec={spec} />
              {visibleHeight > openingTop ? (
                <WallBox wall={wall} startOffset={start} endOffset={end} bottom={openingTop} height={visibleHeight - openingTop} spec={spec} />
              ) : null}
            </group>
          );
        }
        const top = Math.min(opening.height, visibleHeight);
        return visibleHeight > top ? (
          <WallBox key={opening.id} wall={wall} startOffset={start} endOffset={end} bottom={top} height={visibleHeight - top} spec={spec} />
        ) : null;
      })}
    </group>
  );
}

function RoomFloor({ room, scene }: { room: RoomShape; scene: SceneManifest }) {
  const shape = useMemo(() => {
    const result = new THREE.Shape();
    room.polygon.forEach(([x, z], index) => (index === 0 ? result.moveTo(x, z) : result.lineTo(x, z)));
    result.closePath();
    return result;
  }, [room.polygon]);
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <PbrMaterial spec={scene.materials.floor_global} />
    </mesh>
  );
}

function ReferenceFloor({ url, scene }: { url: string; scene: SceneManifest }) {
  const texture = useTexture(url);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return (
    <mesh position={[scene.width_m / 2, -0.018, scene.depth_m / 2]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[scene.width_m, scene.depth_m]} />
      <meshBasicMaterial map={texture} transparent opacity={0.66} side={THREE.DoubleSide} />
    </mesh>
  );
}

function WindowMarker({ opening, scene }: { opening: Opening; scene: SceneManifest }) {
  const [x, z] = opening.position;
  const rotation = THREE.MathUtils.degToRad(opening.rotation_deg);
  const sill = opening.sill_height ?? 0.9;
  const height = Math.min(opening.height, scene.wall_height_m - sill);
  const bay = opening.opening_type === 'bay_window' || opening.opening_type === 'bow_window';
  return (
    <group position={[x, sill, z]} rotation={[0, rotation, 0]}>
      <mesh position={[0, height / 2, bay ? 0.12 : 0]} castShadow>
        <boxGeometry args={[opening.width, height, 0.035]} />
        <meshPhysicalMaterial color="#72b7df" transparent opacity={0.34} roughness={0.08} transmission={0.65} thickness={0.02} />
      </mesh>
      {bay ? [-1, 1].map((sign) => (
        <mesh key={sign} position={[sign * opening.width * 0.42, height / 2, 0.12]} rotation={[0, -sign * Math.PI / 7, 0]}>
          <boxGeometry args={[opening.width * 0.24, height, 0.025]} />
          <meshPhysicalMaterial color="#72b7df" transparent opacity={0.3} />
        </mesh>
      )) : null}
    </group>
  );
}

function DoorFrame({ opening, scene }: { opening: Opening; scene: SceneManifest }) {
  const [x, z] = opening.position;
  const rotation = THREE.MathUtils.degToRad(opening.rotation_deg);
  const height = Math.min(opening.height, scene.wall_height_m);
  const frame = Math.max(0.055, Math.min(0.1, opening.width * 0.07));
  const linkedIds = openingWallIds(opening);
  const linkedThicknesses = scene.walls.filter((wall) => linkedIds.has(wall.id)).map((wall) => wall.thickness);
  const depth = Math.max(0.12, ...linkedThicknesses, 0.16) + 0.035;
  return (
    <group position={[x, 0, z]} rotation={[0, rotation, 0]}>
      {[-1, 1].map((sign) => (
        <mesh key={sign} position={[sign * (opening.width / 2 + frame / 2), height / 2, 0]} castShadow>
          <boxGeometry args={[frame, height, depth]} />
          <meshStandardMaterial color="#5F4430" roughness={0.42} />
        </mesh>
      ))}
      <mesh position={[0, height + frame / 2, 0]} castShadow>
        <boxGeometry args={[opening.width + frame * 2, frame, depth]} />
        <meshStandardMaterial color="#5F4430" roughness={0.42} />
      </mesh>
      <mesh position={[0, 0.025, 0]}>
        <boxGeometry args={[opening.width + frame * 2, 0.05, depth]} />
        <meshStandardMaterial color="#77563D" roughness={0.5} />
      </mesh>
    </group>
  );
}

function InteractiveDoor({ opening, scene, isOpen, onToggle }: {
  opening: Opening;
  scene: SceneManifest;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const left = useRef<THREE.Group>(null);
  const right = useRef<THREE.Group>(null);
  const slider = useRef<THREE.Group>(null);
  const revolving = useRef<THREE.Group>(null);
  const overhead = useRef<THREE.Group>(null);
  const progress = useRef(isOpen ? 1 : 0);
  const [x, z] = opening.position;
  const rotation = THREE.MathUtils.degToRad(opening.rotation_deg);
  const width = Math.max(0.2, opening.width * 0.94);
  const height = Math.min(opening.height, scene.wall_height_m);
  const targetAngle = THREE.MathUtils.degToRad(opening.swing_angle_deg ?? 90);
  const direction = opening.swing_direction === 'counterclockwise' ? -1 : 1;
  const rightHinged = opening.hinge_side === 'right';

  useFrame((_, delta) => {
    progress.current = THREE.MathUtils.damp(progress.current, isOpen ? 1 : 0, 8, delta);
    const value = progress.current;
    if (left.current) left.current.rotation.y = direction * targetAngle * value;
    if (right.current) right.current.rotation.y = -direction * targetAngle * value;
    if (slider.current) slider.current.position.x = width * 0.48 * value;
    if (revolving.current) revolving.current.rotation.y = Math.PI * 0.75 * value;
    if (overhead.current) {
      overhead.current.rotation.x = -Math.PI / 2 * value;
      overhead.current.position.y = height * 0.48 * value;
    }
  });

  if (opening.opening_type === 'open_passage') return null;
  const material = <meshPhysicalMaterial color={scene.materials.accent.hex_color} roughness={0.42} metalness={0.05} clearcoat={0.18} />;
  const click = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
    if (opening.interactive !== false) onToggle();
  };
  let leaves: React.ReactNode;

  if (opening.opening_type === 'revolving_door') {
    leaves = (
      <>
        <mesh position={[0, height / 2, 0]}>
          <cylinderGeometry args={[width / 2, width / 2, height, 32, 1, true]} />
          <meshPhysicalMaterial color="#91c4db" transparent opacity={0.18} side={THREE.DoubleSide} />
        </mesh>
        <group ref={revolving} position={[0, height / 2, 0]}>
          <mesh><boxGeometry args={[width, height, 0.045]} />{material}</mesh>
          <mesh rotation={[0, Math.PI / 2, 0]}><boxGeometry args={[width, height, 0.045]} />{material}</mesh>
        </group>
      </>
    );
  } else if (opening.opening_type === 'overhead_door') {
    leaves = <group ref={overhead} position={[0, height / 2, 0]}><mesh castShadow><boxGeometry args={[width, height, 0.055]} />{material}</mesh></group>;
  } else if (SLIDING_TYPES.has(opening.opening_type)) {
    const double = ['double_pocket_door', 'double_sliding_door', 'bypass_door'].includes(opening.opening_type);
    leaves = (
      <group ref={slider}>
        <mesh position={[double ? -width * 0.25 : 0, height / 2, 0]} castShadow>
          <boxGeometry args={[double ? width / 2 : width, height, 0.045]} />
          {opening.opening_type === 'sliding_glass_door'
            ? <meshPhysicalMaterial color="#72b7df" transparent opacity={0.35} transmission={0.6} />
            : material}
        </mesh>
        {double ? <mesh position={[width * 0.25, height / 2, 0.04]} castShadow><boxGeometry args={[width / 2, height, 0.045]} />{material}</mesh> : null}
      </group>
    );
  } else {
    const double = opening.opening_type === 'double_door' || opening.opening_type === 'double_bifold_door';
    const leafWidth = double ? width / 2 : width;
    leaves = double ? (
      <>
        <group ref={left} position={[-width / 2, 0, 0]}><mesh position={[leafWidth / 2, height / 2, 0]} castShadow><boxGeometry args={[leafWidth, height, 0.045]} />{material}</mesh></group>
        <group ref={right} position={[width / 2, 0, 0]}><mesh position={[-leafWidth / 2, height / 2, 0]} castShadow><boxGeometry args={[leafWidth, height, 0.045]} />{material}</mesh></group>
      </>
    ) : (
      <group ref={left} position={[rightHinged ? width / 2 : -width / 2, 0, 0]}>
        <mesh position={[rightHinged ? -width / 2 : width / 2, height / 2, 0]} castShadow>
          <boxGeometry args={[width, height, 0.045]} />{material}
        </mesh>
      </group>
    );
  }

  return (
    <>
      <DoorFrame opening={opening} scene={scene} />
      <group position={[x, 0, z]} rotation={[0, rotation, 0]} onClick={click}>{leaves}</group>
    </>
  );
}

function ResponsiveTopCamera({ scene }: { scene: SceneManifest }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const halfHeight = Math.max(scene.depth_m * 0.58, (scene.width_m / Math.max(aspect, 0.1)) * 0.58, 2.4);
  const halfWidth = halfHeight * aspect;
  const height = Math.max(scene.width_m, scene.depth_m, 4) * 2.2;
  return <OrthographicCamera key={`${size.width}-${size.height}`} makeDefault position={[scene.width_m / 2, height, scene.depth_m / 2]} rotation={[-Math.PI / 2, 0, 0]} left={-halfWidth} right={halfWidth} top={halfHeight} bottom={-halfHeight} near={0.1} far={height * 3} />;
}

function ResponsiveIsometricCamera({ scene }: { scene: SceneManifest }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const halfHeight = Math.max(scene.depth_m * 0.65, scene.width_m / Math.max(aspect, 0.1) * 0.65, 3);
  return <OrthographicCamera makeDefault position={[scene.width_m / 2 + largest, largest * 0.95, scene.depth_m / 2 + largest]} left={-halfHeight * aspect} right={halfHeight * aspect} top={halfHeight} bottom={-halfHeight} near={0.1} far={largest * 8} onUpdate={(camera) => camera.lookAt(scene.width_m / 2, 0.55, scene.depth_m / 2)} />;
}

function WalkthroughCamera({ fov, far }: { fov: number; far: number }) {
  const cameraRef = useRef<THREE.PerspectiveCamera>(null);
  useEffect(() => {
    if (!cameraRef.current) return;
    cameraRef.current.fov = fov;
    cameraRef.current.updateProjectionMatrix();
  }, [fov]);
  return <PerspectiveCamera ref={cameraRef} makeDefault fov={fov} near={0.04} far={far} />;
}

function pointInsidePassage(
  point: THREE.Vector2,
  wall: WallSegment,
  openings: Opening[],
  openDoorIds: Set<string>,
  playerRadius: number,
): boolean {
  return openingsForWall(wall, openings).some(({ opening, centre }) => {
    if (isWindow(opening)) return false;
    if (opening.opening_type !== 'open_passage' && (!isDoor(opening) || !openDoorIds.has(opening.id))) return false;
    const start = new THREE.Vector2(wall.start[0], wall.start[1]);
    const end = new THREE.Vector2(wall.end[0], wall.end[1]);
    const vector = end.clone().sub(start);
    const length = vector.length();
    if (length < 0.01) return false;
    const along = point.clone().sub(start).dot(vector.divideScalar(length));
    const usableHalfWidth = Math.max(0.06, opening.width / 2 - playerRadius * 0.72);
    return Math.abs(along - centre) <= usableHalfWidth;
  });
}

function pointIsBlocked(
  scene: SceneManifest,
  point: THREE.Vector2,
  openDoorIds: Set<string>,
  playerRadius: number,
): boolean {
  if (
    point.x < playerRadius
    || point.y < playerRadius
    || point.x > scene.width_m - playerRadius
    || point.y > scene.depth_m - playerRadius
  ) return true;

  const insidePortal = scene.walls.some((wall) => pointInsidePassage(point, wall, scene.openings, openDoorIds, playerRadius));
  const blockedByWall = scene.walls.some((wall) => (
    distanceToSegment(point, wall.start, wall.end) < wall.thickness / 2 + playerRadius
    && !pointInsidePassage(point, wall, scene.openings, openDoorIds, playerRadius)
  ));
  if (blockedByWall) return true;

  // Coordinates outside every confirmed room are exterior white space unless the
  // player is physically inside an open doorway transition.
  if (scene.rooms.length > 0 && !roomAt(scene, [point.x, point.y]) && !insidePortal) return true;
  return false;
}

function FirstPersonRig({
  scene,
  openDoorIds,
  onToggleDoor,
  onRoomChange,
  playerRadius,
  playerPositionRef,
}: {
  scene: SceneManifest;
  openDoorIds: Set<string>;
  onToggleDoor: (openingId: string) => void;
  onRoomChange: (roomId: string | null) => void;
  playerRadius: number;
  playerPositionRef: MutableRefObject<THREE.Vector3 | null>;
}) {
  const { camera } = useThree();
  const keys = useRef(new Set<string>());
  const velocity = useRef(new THREE.Vector3());
  const elapsed = useRef(0);
  const lastRoomId = useRef<string | null>(null);
  const sceneRef = useRef(scene);
  const openDoorIdsRef = useRef(openDoorIds);
  const toggleDoorRef = useRef(onToggleDoor);
  const roomChangeRef = useRef(onRoomChange);
  const radiusRef = useRef(playerRadius);

  useEffect(() => { sceneRef.current = scene; }, [scene]);
  useEffect(() => { openDoorIdsRef.current = openDoorIds; }, [openDoorIds]);
  useEffect(() => { toggleDoorRef.current = onToggleDoor; }, [onToggleDoor]);
  useEffect(() => { roomChangeRef.current = onRoomChange; }, [onRoomChange]);
  useEffect(() => { radiusRef.current = playerRadius; }, [playerRadius]);

  // This effect is intentionally independent from room visibility and door state.
  // It runs once for a mounted walkthrough session instead of after every React render.
  useEffect(() => {
    const activeScene = sceneRef.current;
    const start = activeScene.first_person_start ?? [activeScene.width_m / 2, EYE_HEIGHT, activeScene.depth_m / 2];
    const stored = playerPositionRef.current;
    const position = stored
      && Number.isFinite(stored.x)
      && stored.x >= 0
      && stored.x <= activeScene.width_m
      && stored.z >= 0
      && stored.z <= activeScene.depth_m
      ? stored.clone()
      : new THREE.Vector3(start[0], EYE_HEIGHT, start[2]);
    position.y = EYE_HEIGHT;
    camera.position.copy(position);
    playerPositionRef.current = position.clone();
    velocity.current.set(0, 0, 0);
    const roomId = roomAt(activeScene, [position.x, position.z])?.id ?? null;
    lastRoomId.current = roomId;
    roomChangeRef.current(roomId);

    return () => {
      playerPositionRef.current = camera.position.clone();
      keys.current.clear();
      velocity.current.set(0, 0, 0);
    };
  }, [camera, playerPositionRef, scene.project_id]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      keys.current.add(event.code);
      if (event.code !== 'KeyE' || event.repeat) return;
      const activeScene = sceneRef.current;
      const forward = new THREE.Vector3();
      camera.getWorldDirection(forward);
      forward.y = 0;
      forward.normalize();
      const candidate = activeScene.openings
        .filter((opening) => isDoor(opening) && opening.interactive !== false)
        .map((opening) => {
          const vector = new THREE.Vector3(opening.position[0] - camera.position.x, 0, opening.position[1] - camera.position.z);
          const distance = vector.length();
          return { opening, distance, facing: distance > 0 ? vector.normalize().dot(forward) : 1 };
        })
        .filter((item) => item.distance <= 2.4 && item.facing >= 0.1)
        .sort((a, b) => a.distance - b.distance)[0];
      if (candidate) toggleDoorRef.current(candidate.opening.id);
    };
    const up = (event: KeyboardEvent) => keys.current.delete(event.code);
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
    };
  }, [camera]);

  useFrame((_, delta) => {
    const activeScene = sceneRef.current;
    const activeDoors = openDoorIdsRef.current;
    const radius = radiusRef.current;
    const safeDelta = Math.min(delta, 0.05);
    const speed = keys.current.has('ShiftLeft') || keys.current.has('ShiftRight') ? 4.4 : 2.5;
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3(forward.z, 0, -forward.x);
    const intent = new THREE.Vector3();
    if (keys.current.has('KeyW') || keys.current.has('ArrowUp')) intent.add(forward);
    if (keys.current.has('KeyS') || keys.current.has('ArrowDown')) intent.sub(forward);
    if (keys.current.has('KeyD') || keys.current.has('ArrowRight')) intent.add(right);
    if (keys.current.has('KeyA') || keys.current.has('ArrowLeft')) intent.sub(right);
    const target = intent.lengthSq() ? intent.normalize().multiplyScalar(speed) : new THREE.Vector3();
    velocity.current.lerp(target, 1 - Math.exp(-safeDelta * 12));
    if (velocity.current.lengthSq() < 0.0001) return;

    const displacement = velocity.current.clone().multiplyScalar(safeDelta);
    const steps = Math.max(1, Math.ceil(displacement.length() / MAX_MOVEMENT_STEP));
    const step = displacement.divideScalar(steps);
    const current = camera.position.clone();
    let moved = false;

    for (let index = 0; index < steps; index += 1) {
      const fullCandidate = current.clone().add(step);
      const fullPoint = new THREE.Vector2(fullCandidate.x, fullCandidate.z);
      if (!pointIsBlocked(activeScene, fullPoint, activeDoors, radius)) {
        current.copy(fullCandidate);
        moved = true;
        continue;
      }

      // Axis-separated fallback lets the capsule slide along walls instead of
      // feeling wedged in narrow corridors.
      const xCandidate = current.clone();
      xCandidate.x += step.x;
      const xPoint = new THREE.Vector2(xCandidate.x, xCandidate.z);
      if (Math.abs(step.x) > 1e-6 && !pointIsBlocked(activeScene, xPoint, activeDoors, radius)) {
        current.copy(xCandidate);
        moved = true;
      }
      const zCandidate = current.clone();
      zCandidate.z += step.z;
      const zPoint = new THREE.Vector2(zCandidate.x, zCandidate.z);
      if (Math.abs(step.z) > 1e-6 && !pointIsBlocked(activeScene, zPoint, activeDoors, radius)) {
        current.copy(zCandidate);
        moved = true;
      }
    }

    if (!moved) {
      velocity.current.multiplyScalar(0.1);
      return;
    }

    elapsed.current += safeDelta * Math.min(velocity.current.length(), 3.2);
    current.y = EYE_HEIGHT + Math.sin(elapsed.current * 7.5) * 0.018;
    camera.position.copy(current);
    playerPositionRef.current = current.clone();
    const roomId = roomAt(activeScene, [current.x, current.z])?.id ?? null;
    if (roomId !== lastRoomId.current) {
      lastRoomId.current = roomId;
      roomChangeRef.current(roomId);
    }
  });

  return <PointerLockControls makeDefault />;
}

function connectedVisibleRooms(scene: SceneManifest, currentRoomId: string | null, openDoorIds: Set<string>): Set<string> {
  if (!currentRoomId) return new Set(scene.rooms.map((room) => room.id));
  const visible = new Set([currentRoomId]);
  let changed = true;
  while (changed) {
    changed = false;
    scene.openings.forEach((opening) => {
      const traversable = opening.opening_type === 'open_passage' || (isDoor(opening) && openDoorIds.has(opening.id));
      if (!traversable) return;
      const rooms = roomsForOpening(scene, opening);
      if (rooms.length < 2) return;
      const [first, second] = rooms;
      if (visible.has(first.id) && !visible.has(second.id)) { visible.add(second.id); changed = true; }
      if (visible.has(second.id) && !visible.has(first.id)) { visible.add(first.id); changed = true; }
    });
  }
  return visible;
}

function SceneContent({ project, scene, referenceUrl, view, walkthroughFov, playerRadius }: {
  project: Project;
  scene: SceneManifest;
  referenceUrl?: string;
  view: RenderedViewMode;
  walkthroughFov: number;
  playerRadius: number;
}) {
  const centreX = scene.width_m / 2;
  const centreZ = scene.depth_m / 2;
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const cutaway = view === 'isometric';
  const [currentRoomId, setCurrentRoomId] = useState<string | null>(null);
  const [openDoorIds, setOpenDoorIds] = useState<Set<string>>(() => new Set(
    scene.openings
      .filter((opening) => opening.default_open || opening.opening_type === 'open_passage')
      .map((opening) => opening.id),
  ));
  const playerPositionRef = useRef<THREE.Vector3 | null>(null);

  useEffect(() => {
    setOpenDoorIds((current) => {
      const next = new Set([...current].filter((id) => scene.openings.some((opening) => opening.id === id)));
      scene.openings.forEach((opening) => {
        if (opening.default_open || opening.opening_type === 'open_passage') next.add(opening.id);
      });
      return next;
    });
  }, [scene.openings]);

  const visibleRooms = useMemo(
    () => view === 'walkthrough'
      ? connectedVisibleRooms(scene, currentRoomId, openDoorIds)
      : new Set(scene.rooms.map((room) => room.id)),
    [scene, currentRoomId, openDoorIds, view],
  );
  const toggleDoor = useCallback((openingId: string) => {
    setOpenDoorIds((current) => {
      const next = new Set(current);
      if (next.has(openingId)) next.delete(openingId);
      else next.add(openingId);
      return next;
    });
  }, []);
  const assetTexture = (assetId: string, objectType: string): string | undefined => {
    const decoded = decodeFurnitureAssetId(assetId);
    if (decoded.referenceAssetKey) return absoluteUrl(project.assets[decoded.referenceAssetKey]?.url);
    const matching = Object.entries(project.assets).find(([key]) => (
      key.endsWith(`/${objectType}`) || key.endsWith(`/${objectType === 'sofa' ? 'couch' : objectType}`)
    ));
    return matching ? absoluteUrl(matching[1].url) : undefined;
  };
  const occupiedTypes = new Set(scene.fixtures_and_furniture.map((item) => item.object_type));

  return (
    <>
      <ambientLight intensity={view === 'walkthrough' ? 1.05 : 0.78} />
      <hemisphereLight intensity={0.48} color="#f8f3e8" groundColor="#405247" />
      <directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
      {referenceUrl && view === 'top' ? <ReferenceFloor url={referenceUrl} scene={scene} /> : null}
      {scene.rooms.filter((room) => visibleRooms.has(room.id)).map((room) => <RoomFloor key={room.id} room={room} scene={scene} />)}
      {scene.walls.map((wall) => <Wall key={wall.id} wall={wall} scene={scene} cutaway={cutaway} />)}
      {scene.openings.map((opening) => (
        isWindow(opening)
          ? <WindowMarker key={opening.id} opening={opening} scene={scene} />
          : <InteractiveDoor key={opening.id} opening={opening} scene={scene} isOpen={openDoorIds.has(opening.id)} onToggle={() => toggleDoor(opening.id)} />
      ))}
      {scene.fixtures_and_furniture.map((item) => {
        const style = decodeFurnitureAssetId(item.asset_id);
        const visible = !item.room_id || visibleRooms.has(item.room_id);
        return <FurnitureModel key={item.id} id={item.id} objectType={item.object_type} position={item.coordinates} size={item.size} rotationDeg={item.rotation_deg} style={style} textureUrl={assetTexture(item.asset_id, item.object_type)} visible={visible} />;
      })}
      {scene.assets
        .filter((asset) => !occupiedTypes.has(asset.slot === 'couch' ? 'sofa' : asset.slot))
        .map((asset) => (
          <FurnitureModel
            key={asset.id}
            id={asset.id}
            objectType={asset.slot}
            position={asset.position}
            size={asset.size}
            rotationDeg={THREE.MathUtils.radToDeg(asset.rotation_y)}
            style={{
              style: 'modern',
              material: asset.slot.includes('fridge') ? 'painted_metal' : 'fabric',
              color: scene.materials.accent.hex_color,
            }}
            textureUrl={absoluteUrl(asset.source_url)}
            visible={!asset.room_id || visibleRooms.has(asset.room_id)}
          />
        ))}
      {view !== 'walkthrough' ? <Grid args={[Math.max(scene.width_m, 20), Math.max(scene.depth_m, 20)]} position={[centreX, -0.03, centreZ]} cellColor="#31513f" sectionColor="#5b8d6e" fadeDistance={largest * 4} /> : null}
      {view === 'top' ? (
        <><ResponsiveTopCamera scene={scene} /><OrbitControls makeDefault target={[centreX, 0, centreZ]} enableRotate={false} enableDamping /></>
      ) : view === 'isometric' ? (
        <><ResponsiveIsometricCamera scene={scene} /><OrbitControls makeDefault target={[centreX, 0.7, centreZ]} enableDamping /></>
      ) : (
        <>
          <WalkthroughCamera fov={walkthroughFov} far={largest * 12} />
          <FirstPersonRig
            scene={scene}
            openDoorIds={openDoorIds}
            onToggleDoor={toggleDoor}
            onRoomChange={setCurrentRoomId}
            playerRadius={playerRadius}
            playerPositionRef={playerPositionRef}
          />
        </>
      )}
    </>
  );
}

function DataSummary({ scene }: { scene: SceneManifest }) {
  return <pre className="scene-json-preview">{JSON.stringify({ project_metadata: scene.project_metadata, dimensions_m: { width: scene.width_m, depth: scene.depth_m, ceiling: scene.ceiling_height_m }, walls: scene.walls, rooms: scene.rooms, openings: scene.openings, fixtures_and_furniture: scene.fixtures_and_furniture, materials: scene.materials, first_person_start: scene.first_person_start, camera_path: scene.camera_path }, null, 2)}</pre>;
}

export function ScenePreview({
  project, busy, onAddRoom, onUpdateRoom, onDeleteRoom, onRenameRoom,
  onAddOpening, onUpdateOpening, onDeleteOpening,
  onAddFurniture, onUpdateFurniture, onDeleteFurniture,
}: Props) {
  const scene = project?.scene;
  const [view, setView] = useState<ViewMode>('isometric');
  const [walkthroughFov, setWalkthroughFov] = useState(DEFAULT_FOV);
  const [playerRadius, setPlayerRadius] = useState(DEFAULT_PLAYER_RADIUS);
  const structureUrl = absoluteUrl(scene?.detection_preview_url);
  const referenceUrl = absoluteUrl(scene?.reference_image_url ?? project?.floorplan?.preview_url);

  useEffect(() => {
    if (scene?.layout_mode === 'manual' && scene.rooms.length === 0) setView('edit');
  }, [scene?.layout_mode, scene?.rooms.length]);
  const renderedView: RenderedViewMode = view === 'top' || view === 'walkthrough' ? view : 'isometric';

  return (
    <section className="viewer-panel">
      <div className="viewer-header">
        <div>
          <span className="eyebrow">4. Synchronized viewports</span>
          <h2>{scene ? `${scene.rooms.length} rooms · ${scene.walls.length} walls · ${scene.openings.length} openings · ${scene.fixtures_and_furniture.length} interiors` : 'Waiting for a layout'}</h2>
        </div>
        <div className="viewer-actions">
          {scene ? <div className="view-switch">
            <button className={view === 'isometric' ? 'active' : ''} onClick={() => setView('isometric')}><Box size={15} /> Cutaway</button>
            <button className={view === 'top' ? 'active' : ''} onClick={() => setView('top')}><ScanLine size={15} /> Top plan</button>
            <button className={view === 'walkthrough' ? 'active' : ''} onClick={() => setView('walkthrough')}><Footprints size={15} /> First person</button>
            <button className={view === 'interior' ? 'active' : ''} onClick={() => setView('interior')}><Armchair size={15} /> Interior design</button>
            <button className={view === 'edit' ? 'active' : ''} onClick={() => setView('edit')}><Edit3 size={15} /> Edit rooms</button>
            <button className={view === 'openings' ? 'active' : ''} onClick={() => setView('openings')}><DoorOpen size={15} /> Doors & windows</button>
            {structureUrl ? <button className={view === 'structure' ? 'active' : ''} onClick={() => setView('structure')}><Map size={15} /> Detection</button> : null}
            <button className={view === 'data' ? 'active' : ''} onClick={() => setView('data')}><Braces size={15} /> Data</button>
          </div> : null}
          <span className="status-dot">{scene?.project_metadata.parser_version ?? 'No'} scene</span>
        </div>
      </div>
      <div className={view === 'edit' || view === 'openings' || view === 'interior' ? 'canvas-wrap editor-canvas' : 'canvas-wrap'}>
        {scene && project ? (
          view === 'structure' && structureUrl ? (
            <div className="structure-preview"><img src={structureUrl} alt="Detected walls, rooms, doors, windows and furniture" /><div><span className="green-key" /> Model/vector structure <span className="orange-key" /> Room boundaries</div></div>
          ) : view === 'edit' ? (
            <RoomLayoutEditor scene={scene} referenceUrl={referenceUrl} busy={busy} onAddRoom={onAddRoom} onUpdateRoom={onUpdateRoom} onDeleteRoom={onDeleteRoom} onRenameRoom={onRenameRoom} />
          ) : view === 'openings' ? (
            <OpeningEditor scene={scene} referenceUrl={referenceUrl} busy={busy} onAddOpening={onAddOpening} onUpdateOpening={onUpdateOpening} onDeleteOpening={onDeleteOpening} />
          ) : view === 'interior' ? (
            <InteriorDesignEditor project={project} scene={scene} busy={busy} onAddFurniture={onAddFurniture} onUpdateFurniture={onUpdateFurniture} onDeleteFurniture={onDeleteFurniture} />
          ) : view === 'data' ? (
            <DataSummary scene={scene} />
          ) : (
            <div className="three-view-wrap">
              <Canvas shadows dpr={[1, 2]} gl={{ preserveDrawingBuffer: true, antialias: true }}>
                <color attach="background" args={[view === 'walkthrough' ? '#dce8ef' : '#0a1711']} />
                {view === 'isometric' ? <fog attach="fog" args={['#0a1711', 35, 120]} /> : null}
                <Suspense fallback={null}>
                  <SceneContent
                    project={project}
                    scene={scene}
                    referenceUrl={referenceUrl}
                    view={renderedView}
                    walkthroughFov={walkthroughFov}
                    playerRadius={playerRadius}
                  />
                </Suspense>
              </Canvas>
              {view === 'walkthrough' ? (
                <>
                  <div className="walkthrough-settings" onPointerDown={(event) => event.stopPropagation()}>
                    <strong>Walkthrough view</strong>
                    <label>Field of view <output>{walkthroughFov}°</output>
                      <input type="range" min="60" max="110" step="1" value={walkthroughFov} onChange={(event) => setWalkthroughFov(Number(event.target.value))} />
                    </label>
                    <label>Player radius <output>{playerRadius.toFixed(2)} m</output>
                      <input type="range" min="0.12" max="0.24" step="0.01" value={playerRadius} onChange={(event) => setPlayerRadius(Number(event.target.value))} />
                    </label>
                    <small>Press Esc before adjusting controls. Wider FOV changes only the projection matrix and never resets player position.</small>
                  </div>
                  <div className="walkthrough-help"><strong>Click inside to look around</strong><span>WASD / arrows move · Shift runs · E or click opens doors · closed portals cull adjoining rooms · Esc releases mouse</span></div>
                </>
              ) : null}
            </div>
          )
        ) : <div className="empty-view"><div className="wireframe-house" /><strong>Your building layout appears here</strong><span>Upload a plan, then analyze it or start a manual room layout.</span></div>}
      </div>
      {scene?.warnings?.length ? <div className="warning-strip">{scene.warnings.join(' · ')}</div> : null}
    </section>
  );
}
