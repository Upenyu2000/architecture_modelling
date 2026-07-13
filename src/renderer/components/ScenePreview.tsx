import { Canvas } from '@react-three/fiber';
import { Grid, OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import type { SceneManifest, WallSegment } from '../types';

function Wall({ wall }: { wall: WallSegment }) {
  const [x1, z1] = wall.start;
  const [x2, z2] = wall.end;
  const dx = x2 - x1;
  const dz = z2 - z1;
  const length = Math.hypot(dx, dz);
  const angle = Math.atan2(dz, dx);
  return (
    <mesh position={[(x1 + x2) / 2, wall.height / 2, (z1 + z2) / 2]} rotation={[0, -angle, 0]} castShadow receiveShadow>
      <boxGeometry args={[length, wall.height, wall.thickness]} />
      <meshStandardMaterial color="#e6e8e5" roughness={0.8} />
    </mesh>
  );
}

function RoomFloor({ polygon }: { polygon: [number, number][] }) {
  const shape = new THREE.Shape();
  polygon.forEach(([x, z], index) => (index === 0 ? shape.moveTo(x, z) : shape.lineTo(x, z)));
  shape.closePath();
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial color="#8b765f" roughness={0.72} side={THREE.DoubleSide} />
    </mesh>
  );
}

function SceneContent({ scene }: { scene: SceneManifest }) {
  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[8, 14, 10]} intensity={2.1} castShadow />
      {scene.rooms.map((room) => <RoomFloor key={room.id} polygon={room.polygon} />)}
      {scene.walls.map((wall) => <Wall key={wall.id} wall={wall} />)}
      {scene.assets.map((asset) => (
        <mesh key={asset.id} position={asset.position} rotation={[0, asset.rotation_y, 0]} castShadow receiveShadow>
          <boxGeometry args={asset.size} />
          <meshStandardMaterial color="#4f7f65" roughness={0.55} metalness={asset.slot.includes('fridge') ? 0.7 : 0.05} />
        </mesh>
      ))}
      <Grid args={[Math.max(scene.width_m, 20), Math.max(scene.depth_m, 20)]} cellColor="#31513f" sectionColor="#5b8d6e" fadeDistance={80} />
      <OrbitControls makeDefault target={[scene.width_m / 2, 1, scene.depth_m / 2]} />
      <PerspectiveCamera makeDefault position={[scene.width_m * 0.9, Math.max(8, scene.width_m * 0.7), scene.depth_m * 1.05]} fov={45} />
    </>
  );
}

export function ScenePreview({ scene }: { scene?: SceneManifest | null }) {
  return (
    <section className="viewer-panel">
      <div className="viewer-header">
        <div>
          <span className="eyebrow">3. Live scene</span>
          <h2>{scene ? `${scene.rooms.length} rooms · ${scene.walls.length} walls` : 'Waiting for analysis'}</h2>
        </div>
        <span className="status-dot">Deterministic geometry</span>
      </div>
      <div className="canvas-wrap">
        {scene ? (
          <Canvas shadows dpr={[1, 2]} gl={{ preserveDrawingBuffer: true }}>
            <color attach="background" args={['#0a1711']} />
            <fog attach="fog" args={['#0a1711', 25, 90]} />
            <SceneContent scene={scene} />
          </Canvas>
        ) : (
          <div className="empty-view">
            <div className="wireframe-house" />
            <strong>Your extracted 3D home appears here</strong>
            <span>Upload a plan, set its width, then run structural analysis.</span>
          </div>
        )}
      </div>
      {scene?.warnings?.length ? (
        <div className="warning-strip">{scene.warnings.join(' · ')}</div>
      ) : null}
    </section>
  );
}
