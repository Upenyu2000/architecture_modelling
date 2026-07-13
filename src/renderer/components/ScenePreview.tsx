import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  Grid, OrbitControls, OrthographicCamera, PerspectiveCamera, PointerLockControls, useTexture,
} from '@react-three/drei';
import { Braces, Box, Edit3, Footprints, Map, ScanLine } from 'lucide-react';
import * as THREE from 'three';
import { absoluteUrl } from '../lib/api';
import type {
  ArchitecturalObject, MaterialSpec, Opening, Project, SceneManifest, WallSegment,
} from '../types';
import { RoomLayoutEditor } from './RoomLayoutEditor';

type Point = [number, number];
type ViewMode = 'isometric' | 'top' | 'walkthrough' | 'edit' | 'structure' | 'data';
type RenderedViewMode = 'isometric' | 'top' | 'walkthrough';

interface Props {
  project: Project | null;
  busy: boolean;
  onAddRoom: () => Promise<void>;
  onUpdateRoom: (roomId: string, polygon: Point[]) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
  onRenameRoom: (roomId: string, name: string) => Promise<void>;
}

type ProjectedOpening = {
  opening: Opening;
  centre: number;
  start: number;
  end: number;
};

function distanceToSegment(point: THREE.Vector2, start: Point, end: Point): number {
  const a = new THREE.Vector2(start[0], start[1]);
  const b = new THREE.Vector2(end[0], end[1]);
  const segment = b.clone().sub(a);
  const lengthSquared = segment.lengthSq();
  if (lengthSquared === 0) return point.distanceTo(a);
  const t = THREE.MathUtils.clamp(point.clone().sub(a).dot(segment) / lengthSquared, 0, 1);
  return point.distanceTo(a.add(segment.multiplyScalar(t)));
}

function projectOpening(wall: WallSegment, opening: Opening): ProjectedOpening | null {
  if (opening.wall_id && opening.wall_id !== wall.id) return null;
  const start = new THREE.Vector2(wall.start[0], wall.start[1]);
  const end = new THREE.Vector2(wall.end[0], wall.end[1]);
  const point = new THREE.Vector2(opening.position[0], opening.position[1]);
  const vector = end.clone().sub(start);
  const length = vector.length();
  if (length < 0.05) return null;
  const direction = vector.clone().divideScalar(length);
  const centre = point.clone().sub(start).dot(direction);
  const closest = start.clone().add(direction.multiplyScalar(THREE.MathUtils.clamp(centre, 0, length)));
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

function MappedMaterial({ spec, textureUrl, normalUrl }: {
  spec: MaterialSpec;
  textureUrl: string;
  normalUrl?: string;
}) {
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
  return (
    <meshStandardMaterial
      map={diffuse}
      normalMap={normal ?? undefined}
      color={spec.hex_color}
      roughness={spec.roughness}
      metalness={spec.metallic}
      side={THREE.DoubleSide}
    />
  );
}

function PbrMaterial({ spec }: { spec: MaterialSpec }) {
  const textureUrl = absoluteUrl(spec.texture_url);
  const normalUrl = absoluteUrl(spec.normal_url);
  if (textureUrl) return <MappedMaterial spec={spec} textureUrl={textureUrl} normalUrl={normalUrl} />;
  return (
    <meshStandardMaterial
      color={spec.hex_color}
      roughness={spec.roughness}
      metalness={spec.metallic}
      side={THREE.DoubleSide}
    />
  );
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
  return (
    <mesh position={[x1 + ux * middle, bottom + height / 2, z1 + uz * middle]} rotation={[0, -angle, 0]} castShadow receiveShadow>
      <boxGeometry args={[length, height, wall.thickness]} />
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
        if (opening.opening_type === 'window') {
          const sill = Math.min(0.9, visibleHeight);
          const openingTop = Math.min(sill + opening.height, visibleHeight);
          return (
            <group key={opening.id}>
              <WallBox wall={wall} startOffset={start} endOffset={end} bottom={0} height={sill} spec={spec} />
              {visibleHeight > openingTop ? <WallBox wall={wall} startOffset={start} endOffset={end} bottom={openingTop} height={visibleHeight - openingTop} spec={spec} /> : null}
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

function RoomFloor({ polygon, scene }: { polygon: Point[]; scene: SceneManifest }) {
  const shape = useMemo(() => {
    const result = new THREE.Shape();
    polygon.forEach(([x, z], index) => (index === 0 ? result.moveTo(x, z) : result.lineTo(x, z)));
    result.closePath();
    return result;
  }, [polygon]);
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

function OpeningMarker({ opening, scene }: { opening: Opening; scene: SceneManifest }) {
  const [x, z] = opening.position;
  const rotation = THREE.MathUtils.degToRad(opening.rotation_deg);
  const accent = scene.materials.accent;
  if (opening.opening_type === 'window') {
    return (
      <mesh position={[x, 1.45, z]} rotation={[0, rotation, 0]}>
        <boxGeometry args={[opening.width, 1.05, 0.035]} />
        <meshPhysicalMaterial color="#72b7df" transparent opacity={0.38} roughness={0.08} transmission={0.6} thickness={0.02} />
      </mesh>
    );
  }
  if (opening.opening_type === 'open_passage') return null;
  const leafWidth = Math.max(0.08, opening.width * 0.92);
  const leafAngle = opening.swing_direction === 'counterclockwise' ? -Math.PI * 0.42 : Math.PI * 0.42;
  return (
    <group position={[x, 0, z]} rotation={[0, rotation, 0]}>
      <mesh position={[leafWidth * 0.42, Math.min(opening.height, scene.wall_height_m) / 2, leafWidth * 0.38]} rotation={[0, leafAngle, 0]} castShadow>
        <boxGeometry args={[leafWidth, Math.min(opening.height, scene.wall_height_m), 0.045]} />
        <meshStandardMaterial color={accent.hex_color} roughness={accent.roughness} metalness={accent.metallic} />
      </mesh>
    </group>
  );
}

function ObjectMesh({ item, scene }: { item: ArchitecturalObject; scene: SceneManifest }) {
  const [x, y, z] = item.coordinates;
  const [sx, sy, sz] = item.size;
  const rotation = THREE.MathUtils.degToRad(item.rotation_deg);
  const accent = scene.materials.accent;
  const metal = scene.materials.fixture_metal;
  const isMetal = ['fridge', 'stove', 'washing_machine', 'dryer', 'lift'].includes(item.object_type);
  const colour = isMetal ? metal.hex_color : item.category === 'fixture' ? '#ecefed' : accent.hex_color;
  const roughness = isMetal ? metal.roughness : item.category === 'fixture' ? 0.28 : Math.max(0.38, accent.roughness);
  const metalness = isMetal ? metal.metallic : 0.03;

  if (item.object_type === 'toilet' || item.object_type === 'sink') {
    return (
      <group position={[x, 0, z]} rotation={[0, rotation, 0]}>
        <mesh position={[0, Math.max(0.22, sy * 0.35), 0]} castShadow receiveShadow>
          <cylinderGeometry args={[Math.max(0.16, Math.min(sx, sz) * 0.42), Math.max(0.18, Math.min(sx, sz) * 0.35), Math.max(0.2, sy * 0.5), 24]} />
          <meshStandardMaterial color={colour} roughness={roughness} />
        </mesh>
      </group>
    );
  }

  if (item.object_type === 'staircase') {
    const steps = 9;
    return (
      <group position={[x, 0, z]} rotation={[0, rotation, 0]}>
        {Array.from({ length: steps }, (_, index) => (
          <mesh key={index} position={[0, (sy / steps) * (index + 0.5), -sz / 2 + (sz / steps) * (index + 0.5)]} castShadow receiveShadow>
            <boxGeometry args={[sx, sy / steps, sz / steps]} />
            <PbrMaterial spec={scene.materials.floor_global} />
          </mesh>
        ))}
      </group>
    );
  }

  return (
    <mesh position={[x, Math.max(y, sy / 2), z]} rotation={[0, rotation, 0]} castShadow receiveShadow>
      <boxGeometry args={[sx, sy, sz]} />
      <meshStandardMaterial color={colour} roughness={roughness} metalness={metalness} />
    </mesh>
  );
}

function ResponsiveTopCamera({ scene }: { scene: SceneManifest }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const centreX = scene.width_m / 2;
  const centreZ = scene.depth_m / 2;
  const halfHeight = Math.max(scene.depth_m * 0.58, (scene.width_m / Math.max(aspect, 0.1)) * 0.58, 2.4);
  const halfWidth = halfHeight * aspect;
  const height = Math.max(scene.width_m, scene.depth_m, 4) * 2.2;
  return (
    <OrthographicCamera key={`${size.width}-${size.height}`} makeDefault position={[centreX, height, centreZ]} rotation={[-Math.PI / 2, 0, 0]} left={-halfWidth} right={halfWidth} top={halfHeight} bottom={-halfHeight} near={0.1} far={height * 3} />
  );
}

function ResponsiveIsometricCamera({ scene }: { scene: SceneManifest }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const halfHeight = Math.max(scene.depth_m * 0.65, scene.width_m / Math.max(aspect, 0.1) * 0.65, 3);
  return (
    <OrthographicCamera makeDefault position={[scene.width_m / 2 + largest, largest * 0.95, scene.depth_m / 2 + largest]} zoom={1} left={-halfHeight * aspect} right={halfHeight * aspect} top={halfHeight} bottom={-halfHeight} near={0.1} far={largest * 8} onUpdate={(camera) => camera.lookAt(scene.width_m / 2, 0.55, scene.depth_m / 2)} />
  );
}

function pointInsidePassage(point: THREE.Vector2, wall: WallSegment, openings: Opening[]): boolean {
  return openingsForWall(wall, openings).some(({ opening, centre }) => {
    if (!['door', 'sliding_door', 'bifold_door', 'open_passage'].includes(opening.opening_type)) return false;
    const start = new THREE.Vector2(wall.start[0], wall.start[1]);
    const end = new THREE.Vector2(wall.end[0], wall.end[1]);
    const vector = end.clone().sub(start);
    const length = vector.length();
    if (length < 0.01) return false;
    const direction = vector.divideScalar(length);
    const along = point.clone().sub(start).dot(direction);
    return Math.abs(along - centre) <= opening.width / 2 + 0.16;
  });
}

function FirstPersonRig({ scene }: { scene: SceneManifest }) {
  const { camera } = useThree();
  const keys = useRef(new Set<string>());
  const velocity = useRef(new THREE.Vector3());
  const elapsed = useRef(0);
  const start = scene.first_person_start ?? [scene.width_m / 2, 1.7, scene.depth_m / 2];

  useEffect(() => {
    camera.position.set(...start);
    velocity.current.set(0, 0, 0);
    const down = (event: KeyboardEvent) => keys.current.add(event.code);
    const up = (event: KeyboardEvent) => keys.current.delete(event.code);
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
    };
  }, [camera, start[0], start[1], start[2]]);

  useFrame((_, delta) => {
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
    const proposed = camera.position.clone().addScaledVector(velocity.current, safeDelta);
    proposed.x = THREE.MathUtils.clamp(proposed.x, 0.22, scene.width_m - 0.22);
    proposed.z = THREE.MathUtils.clamp(proposed.z, 0.22, scene.depth_m - 0.22);
    const point = new THREE.Vector2(proposed.x, proposed.z);
    const blocked = scene.walls.some((wall) => {
      if (distanceToSegment(point, wall.start, wall.end) >= wall.thickness / 2 + 0.23) return false;
      return !pointInsidePassage(point, wall, scene.openings);
    });
    if (!blocked) {
      elapsed.current += safeDelta * Math.min(velocity.current.length(), 3.2);
      proposed.y = 1.7 + Math.sin(elapsed.current * 7.5) * 0.018;
      camera.position.copy(proposed);
    } else {
      velocity.current.multiplyScalar(0.1);
    }
  });

  return <PointerLockControls makeDefault />;
}

function SceneContent({ scene, referenceUrl, view }: { scene: SceneManifest; referenceUrl?: string; view: RenderedViewMode }) {
  const centreX = scene.width_m / 2;
  const centreZ = scene.depth_m / 2;
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const cutaway = view === 'isometric';
  return (
    <>
      <ambientLight intensity={view === 'walkthrough' ? 1.05 : 0.78} />
      <hemisphereLight intensity={0.48} color="#f8f3e8" groundColor="#405247" />
      <directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
      {referenceUrl && view === 'top' ? <ReferenceFloor url={referenceUrl} scene={scene} /> : null}
      {scene.rooms.map((room) => <RoomFloor key={room.id} polygon={room.polygon} scene={scene} />)}
      {scene.walls.map((wall) => <Wall key={wall.id} wall={wall} scene={scene} cutaway={cutaway} />)}
      {scene.openings.map((opening) => <OpeningMarker key={opening.id} opening={opening} scene={scene} />)}
      {scene.fixtures_and_furniture.map((item) => <ObjectMesh key={item.id} item={item} scene={scene} />)}
      {scene.assets.map((asset) => (
        <mesh key={asset.id} position={asset.position} rotation={[0, asset.rotation_y, 0]} castShadow receiveShadow>
          <boxGeometry args={asset.size} />
          <meshStandardMaterial color={scene.materials.accent.hex_color} roughness={0.55} metalness={asset.slot.includes('fridge') ? 0.7 : 0.05} />
        </mesh>
      ))}
      {view !== 'walkthrough' ? <Grid args={[Math.max(scene.width_m, 20), Math.max(scene.depth_m, 20)]} position={[centreX, -0.03, centreZ]} cellColor="#31513f" sectionColor="#5b8d6e" fadeDistance={largest * 4} /> : null}
      {view === 'top' ? (
        <><ResponsiveTopCamera scene={scene} /><OrbitControls makeDefault target={[centreX, 0, centreZ]} enableRotate={false} enableDamping /></>
      ) : view === 'isometric' ? (
        <><ResponsiveIsometricCamera scene={scene} /><OrbitControls makeDefault target={[centreX, 0.7, centreZ]} enableDamping /></>
      ) : (
        <><PerspectiveCamera makeDefault position={scene.first_person_start ?? [centreX, 1.7, centreZ]} fov={72} near={0.04} far={largest * 12} /><FirstPersonRig scene={scene} /></>
      )}
    </>
  );
}

function DataSummary({ scene }: { scene: SceneManifest }) {
  const summary = {
    project_metadata: scene.project_metadata,
    dimensions_m: { width: scene.width_m, depth: scene.depth_m, ceiling: scene.ceiling_height_m },
    walls: scene.walls,
    rooms: scene.rooms,
    openings: scene.openings,
    fixtures_and_furniture: scene.fixtures_and_furniture,
    materials: scene.materials,
    first_person_start: scene.first_person_start,
    camera_path: scene.camera_path,
  };
  return <pre className="scene-json-preview">{JSON.stringify(summary, null, 2)}</pre>;
}

export function ScenePreview({ project, busy, onAddRoom, onUpdateRoom, onDeleteRoom, onRenameRoom }: Props) {
  const scene = project?.scene;
  const [view, setView] = useState<ViewMode>('isometric');
  const structureUrl = absoluteUrl(scene?.detection_preview_url);
  const referenceUrl = absoluteUrl(scene?.reference_image_url ?? project?.floorplan?.preview_url);

  useEffect(() => {
    if (!scene) return;
    if (scene.layout_mode === 'manual' && scene.rooms.length === 0) setView('edit');
  }, [scene?.layout_mode, scene?.rooms.length]);

  const renderedView: RenderedViewMode = view === 'top' || view === 'walkthrough' ? view : 'isometric';

  return (
    <section className="viewer-panel">
      <div className="viewer-header">
        <div>
          <span className="eyebrow">4. Synchronized viewports</span>
          <h2>{scene ? `${scene.rooms.length} rooms · ${scene.walls.length} walls · ${scene.openings.length} openings` : 'Waiting for a layout'}</h2>
        </div>
        <div className="viewer-actions">
          {scene ? (
            <div className="view-switch">
              <button className={view === 'isometric' ? 'active' : ''} onClick={() => setView('isometric')}><Box size={15} /> Cutaway</button>
              <button className={view === 'top' ? 'active' : ''} onClick={() => setView('top')}><ScanLine size={15} /> Top plan</button>
              <button className={view === 'walkthrough' ? 'active' : ''} onClick={() => setView('walkthrough')}><Footprints size={15} /> First person</button>
              <button className={view === 'edit' ? 'active' : ''} onClick={() => setView('edit')}><Edit3 size={15} /> Edit rooms</button>
              {structureUrl ? <button className={view === 'structure' ? 'active' : ''} onClick={() => setView('structure')}><Map size={15} /> Detection</button> : null}
              <button className={view === 'data' ? 'active' : ''} onClick={() => setView('data')}><Braces size={15} /> Data</button>
            </div>
          ) : null}
          <span className="status-dot">{scene?.project_metadata.parser_version ?? 'No'} scene</span>
        </div>
      </div>
      <div className={view === 'edit' ? 'canvas-wrap editor-canvas' : 'canvas-wrap'}>
        {scene ? (
          view === 'structure' && structureUrl ? (
            <div className="structure-preview"><img src={structureUrl} alt="Detected walls, rooms, doors and windows" /><div><span className="green-key" /> Model/vector structure <span className="orange-key" /> Room boundaries</div></div>
          ) : view === 'edit' ? (
            <RoomLayoutEditor scene={scene} referenceUrl={referenceUrl} busy={busy} onAddRoom={onAddRoom} onUpdateRoom={onUpdateRoom} onDeleteRoom={onDeleteRoom} onRenameRoom={onRenameRoom} />
          ) : view === 'data' ? (
            <DataSummary scene={scene} />
          ) : (
            <div className="three-view-wrap">
              <Canvas shadows dpr={[1, 2]} gl={{ preserveDrawingBuffer: true, antialias: true }}>
                <color attach="background" args={[view === 'walkthrough' ? '#dce8ef' : '#0a1711']} />
                {view === 'isometric' ? <fog attach="fog" args={['#0a1711', 35, 120]} /> : null}
                <Suspense fallback={null}><SceneContent scene={scene} referenceUrl={referenceUrl} view={renderedView} /></Suspense>
              </Canvas>
              {view === 'walkthrough' ? <div className="walkthrough-help"><strong>Click inside to look around</strong><span>WASD / arrows move · Shift runs · doors are traversable · Esc releases mouse</span></div> : null}
            </div>
          )
        ) : (
          <div className="empty-view"><div className="wireframe-house" /><strong>Your building layout appears here</strong><span>Upload a plan, then analyze it or start a manual room layout.</span></div>
        )}
      </div>
      {scene?.warnings?.length ? <div className="warning-strip">{scene.warnings.join(' · ')}</div> : null}
    </section>
  );
}
