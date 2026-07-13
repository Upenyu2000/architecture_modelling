import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  Grid, OrbitControls, OrthographicCamera, PerspectiveCamera, PointerLockControls, useTexture,
} from '@react-three/drei';
import { Braces, Box, Edit3, Footprints, Map, ScanLine } from 'lucide-react';
import * as THREE from 'three';
import { absoluteUrl } from '../lib/api';
import type {
  ArchitecturalObject, Opening, Project, SceneManifest, WallSegment,
} from '../types';
import { RoomLayoutEditor } from './RoomLayoutEditor';

type Point = [number, number];
type ViewMode = 'isometric' | 'top' | 'walkthrough' | 'edit' | 'structure' | 'data';

interface Props {
  project: Project | null;
  busy: boolean;
  onAddRoom: () => Promise<void>;
  onUpdateRoom: (roomId: string, polygon: Point[]) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
  onRenameRoom: (roomId: string, name: string) => Promise<void>;
}

function Wall({ wall, scene, cutaway }: { wall: WallSegment; scene: SceneManifest; cutaway: boolean }) {
  const [x1, z1] = wall.start;
  const [x2, z2] = wall.end;
  const dx = x2 - x1;
  const dz = z2 - z1;
  const length = Math.hypot(dx, dz);
  const angle = Math.atan2(dz, dx);
  const height = cutaway ? Math.min(scene.cutaway_height_m, wall.height) : wall.height;
  const spec = wall.wall_type === 'exterior' ? scene.materials.exterior_walls : scene.materials.walls_global;
  return (
    <mesh
      position={[(x1 + x2) / 2, height / 2, (z1 + z2) / 2]}
      rotation={[0, -angle, 0]}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[length, height, wall.thickness]} />
      <meshStandardMaterial
        color={spec.hex_color}
        roughness={spec.roughness}
        metalness={spec.metallic}
      />
    </mesh>
  );
}

function RoomFloor({ polygon, scene }: { polygon: Point[]; scene: SceneManifest }) {
  const shape = useMemo(() => {
    const result = new THREE.Shape();
    polygon.forEach(([x, z], index) => (index === 0 ? result.moveTo(x, z) : result.lineTo(x, z)));
    result.closePath();
    return result;
  }, [polygon]);
  const floor = scene.materials.floor_global;
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial
        color={floor.hex_color}
        roughness={floor.roughness}
        metalness={floor.metallic}
        side={THREE.DoubleSide}
      />
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
        <boxGeometry args={[opening.width, 1.05, 0.045]} />
        <meshPhysicalMaterial color="#72b7df" transparent opacity={0.42} roughness={0.12} transmission={0.42} />
      </mesh>
    );
  }
  if (opening.opening_type === 'open_passage') return null;
  return (
    <mesh position={[x, Math.min(opening.height, scene.wall_height_m) / 2, z]} rotation={[0, rotation, 0]}>
      <boxGeometry args={[Math.max(0.08, opening.width * 0.94), Math.min(opening.height, scene.wall_height_m), 0.045]} />
      <meshStandardMaterial color={accent.hex_color} roughness={accent.roughness} metalness={accent.metallic} />
    </mesh>
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
            <meshStandardMaterial color={scene.materials.floor_global.hex_color} roughness={0.62} />
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
    <OrthographicCamera
      key={`${size.width}-${size.height}`}
      makeDefault
      position={[centreX, height, centreZ]}
      rotation={[-Math.PI / 2, 0, 0]}
      left={-halfWidth}
      right={halfWidth}
      top={halfHeight}
      bottom={-halfHeight}
      near={0.1}
      far={height * 3}
    />
  );
}

function ResponsiveIsometricCamera({ scene }: { scene: SceneManifest }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const halfHeight = Math.max(scene.depth_m * 0.65, scene.width_m / Math.max(aspect, 0.1) * 0.65, 3);
  return (
    <OrthographicCamera
      makeDefault
      position={[scene.width_m / 2 + largest, largest * 0.95, scene.depth_m / 2 + largest]}
      zoom={1}
      left={-halfHeight * aspect}
      right={halfHeight * aspect}
      top={halfHeight}
      bottom={-halfHeight}
      near={0.1}
      far={largest * 8}
      onUpdate={(camera) => camera.lookAt(scene.width_m / 2, 0.55, scene.depth_m / 2)}
    />
  );
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

function FirstPersonRig({ scene }: { scene: SceneManifest }) {
  const { camera } = useThree();
  const keys = useRef(new Set<string>());
  const start = scene.first_person_start ?? [scene.width_m / 2, 1.7, scene.depth_m / 2];

  useEffect(() => {
    camera.position.set(...start);
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
    const speed = keys.current.has('ShiftLeft') ? 4.4 : 2.5;
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3(forward.z, 0, -forward.x);
    const movement = new THREE.Vector3();
    if (keys.current.has('KeyW') || keys.current.has('ArrowUp')) movement.add(forward);
    if (keys.current.has('KeyS') || keys.current.has('ArrowDown')) movement.sub(forward);
    if (keys.current.has('KeyD') || keys.current.has('ArrowRight')) movement.add(right);
    if (keys.current.has('KeyA') || keys.current.has('ArrowLeft')) movement.sub(right);
    if (!movement.lengthSq()) return;
    movement.normalize().multiplyScalar(speed * Math.min(delta, 0.05));
    const proposed = camera.position.clone().add(movement);
    proposed.x = THREE.MathUtils.clamp(proposed.x, 0.25, scene.width_m - 0.25);
    proposed.z = THREE.MathUtils.clamp(proposed.z, 0.25, scene.depth_m - 0.25);
    proposed.y = 1.7;
    const point = new THREE.Vector2(proposed.x, proposed.z);
    const blocked = scene.walls.some((wall) => distanceToSegment(point, wall.start, wall.end) < wall.thickness / 2 + 0.24);
    if (!blocked) camera.position.copy(proposed);
  });

  return <PointerLockControls makeDefault />;
}

function SceneContent({ scene, referenceUrl, view }: {
  scene: SceneManifest;
  referenceUrl?: string;
  view: 'top' | 'isometric' | 'walkthrough';
}) {
  const centreX = scene.width_m / 2;
  const centreZ = scene.depth_m / 2;
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const cutaway = view === 'isometric';
  return (
    <>
      <ambientLight intensity={view === 'walkthrough' ? 1.05 : 0.78} />
      <hemisphereLight intensity={0.48} color="#f8f3e8" groundColor="#405247" />
      <directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow />
      {referenceUrl && view === 'top' ? <ReferenceFloor url={referenceUrl} scene={scene} /> : null}
      {scene.rooms.map((room) => <RoomFloor key={room.id} polygon={room.polygon} scene={scene} />)}
      {scene.walls.map((wall) => <Wall key={wall.id} wall={wall} scene={scene} cutaway={cutaway} />)}
      {scene.openings.map((opening) => <OpeningMarker key={opening.id} opening={opening} scene={scene} />)}
      {scene.fixtures_and_furniture.map((item) => <ObjectMesh key={item.id} item={item} scene={scene} />)}
      {scene.assets.map((asset) => (
        <mesh key={asset.id} position={asset.position} rotation={[0, asset.rotation_y, 0]} castShadow receiveShadow>
          <boxGeometry args={asset.size} />
          <meshStandardMaterial
            color={scene.materials.accent.hex_color}
            roughness={0.55}
            metalness={asset.slot.includes('fridge') ? 0.7 : 0.05}
          />
        </mesh>
      ))}
      {view !== 'walkthrough' ? (
        <Grid
          args={[Math.max(scene.width_m, 20), Math.max(scene.depth_m, 20)]}
          position={[centreX, -0.03, centreZ]}
          cellColor="#31513f"
          sectionColor="#5b8d6e"
          fadeDistance={largest * 4}
        />
      ) : null}
      {view === 'top' ? (
        <>
          <ResponsiveTopCamera scene={scene} />
          <OrbitControls makeDefault target={[centreX, 0, centreZ]} enableRotate={false} enableDamping />
        </>
      ) : view === 'isometric' ? (
        <>
          <ResponsiveIsometricCamera scene={scene} />
          <OrbitControls makeDefault target={[centreX, 0.7, centreZ]} enableDamping />
        </>
      ) : (
        <>
          <PerspectiveCamera makeDefault position={scene.first_person_start ?? [centreX, 1.7, centreZ]} fov={72} near={0.04} far={largest * 12} />
          <FirstPersonRig scene={scene} />
        </>
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

export function ScenePreview({
  project,
  busy,
  onAddRoom,
  onUpdateRoom,
  onDeleteRoom,
  onRenameRoom,
}: Props) {
  const scene = project?.scene;
  const [view, setView] = useState<ViewMode>('isometric');
  const structureUrl = absoluteUrl(scene?.detection_preview_url);
  const referenceUrl = absoluteUrl(scene?.reference_image_url ?? project?.floorplan?.preview_url);

  useEffect(() => {
    if (!scene) return;
    if (scene.layout_mode === 'manual' && scene.rooms.length === 0) setView('edit');
  }, [scene?.layout_mode, scene?.rooms.length]);

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
              {structureUrl ? (
                <button className={view === 'structure' ? 'active' : ''} onClick={() => setView('structure')}><Map size={15} /> Detection</button>
              ) : null}
              <button className={view === 'data' ? 'active' : ''} onClick={() => setView('data')}><Braces size={15} /> Data</button>
            </div>
          ) : null}
          <span className="status-dot">{scene?.project_metadata.parser_version ?? 'No'} scene</span>
        </div>
      </div>
      <div className={view === 'edit' ? 'canvas-wrap editor-canvas' : 'canvas-wrap'}>
        {scene ? (
          view === 'structure' && structureUrl ? (
            <div className="structure-preview">
              <img src={structureUrl} alt="Detected structural wall centre lines and room boundaries" />
              <div><span className="green-key" /> Structural walls <span className="orange-key" /> Room boundaries</div>
            </div>
          ) : view === 'edit' ? (
            <RoomLayoutEditor
              scene={scene}
              referenceUrl={referenceUrl}
              busy={busy}
              onAddRoom={onAddRoom}
              onUpdateRoom={onUpdateRoom}
              onDeleteRoom={onDeleteRoom}
              onRenameRoom={onRenameRoom}
            />
          ) : view === 'data' ? (
            <DataSummary scene={scene} />
          ) : (
            <div className="three-view-wrap">
              <Canvas shadows dpr={[1, 2]} gl={{ preserveDrawingBuffer: true, antialias: true }}>
                <color attach="background" args={[view === 'walkthrough' ? '#dce8ef' : '#0a1711']} />
                {view === 'isometric' ? <fog attach="fog" args={['#0a1711', 35, 120]} /> : null}
                <SceneContent scene={scene} referenceUrl={referenceUrl} view={view} />
              </Canvas>
              {view === 'walkthrough' ? (
                <div className="walkthrough-help"><strong>Click inside to look around</strong><span>WASD / arrows move · Shift runs · Esc releases mouse</span></div>
              ) : null}
            </div>
          )
        ) : (
          <div className="empty-view">
            <div className="wireframe-house" />
            <strong>Your building layout appears here</strong>
            <span>Upload a plan, then analyze it or start a manual room layout.</span>
          </div>
        )}
      </div>
      {scene?.warnings?.length ? <div className="warning-strip">{scene.warnings.join(' · ')}</div> : null}
    </section>
  );
}
