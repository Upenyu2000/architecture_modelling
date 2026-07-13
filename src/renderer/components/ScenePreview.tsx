import { useEffect, useState } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import {
  Grid, OrbitControls, OrthographicCamera, PerspectiveCamera, useTexture,
} from '@react-three/drei';
import { Box, Edit3, Map, ScanLine } from 'lucide-react';
import * as THREE from 'three';
import { absoluteUrl } from '../lib/api';
import type { Project, SceneManifest, WallSegment } from '../types';
import { RoomLayoutEditor } from './RoomLayoutEditor';

type Point = [number, number];
type ViewMode = 'top' | '3d' | 'edit' | 'structure';

interface Props {
  project: Project | null;
  busy: boolean;
  onAddRoom: () => Promise<void>;
  onUpdateRoom: (roomId: string, polygon: Point[]) => Promise<void>;
  onDeleteRoom: (roomId: string) => Promise<void>;
  onRenameRoom: (roomId: string, name: string) => Promise<void>;
}

function Wall({ wall }: { wall: WallSegment }) {
  const [x1, z1] = wall.start;
  const [x2, z2] = wall.end;
  const dx = x2 - x1;
  const dz = z2 - z1;
  const length = Math.hypot(dx, dz);
  const angle = Math.atan2(dz, dx);
  return (
    <mesh
      position={[(x1 + x2) / 2, wall.height / 2, (z1 + z2) / 2]}
      rotation={[0, -angle, 0]}
      castShadow
      receiveShadow
    >
      <boxGeometry args={[length, wall.height, wall.thickness]} />
      <meshStandardMaterial color="#e6e8e5" roughness={0.8} />
    </mesh>
  );
}

function RoomFloor({ polygon }: { polygon: Point[] }) {
  const shape = new THREE.Shape();
  polygon.forEach(([x, z], index) => (index === 0 ? shape.moveTo(x, z) : shape.lineTo(x, z)));
  shape.closePath();
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <meshStandardMaterial color="#8b765f" roughness={0.72} side={THREE.DoubleSide} />
    </mesh>
  );
}

function ReferenceFloor({ url, scene }: { url: string; scene: SceneManifest }) {
  const texture = useTexture(url);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return (
    <mesh
      position={[scene.width_m / 2, -0.015, scene.depth_m / 2]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
    >
      <planeGeometry args={[scene.width_m, scene.depth_m]} />
      <meshBasicMaterial map={texture} transparent opacity={0.72} side={THREE.DoubleSide} />
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

function SceneContent({ scene, referenceUrl, view }: {
  scene: SceneManifest;
  referenceUrl?: string;
  view: 'top' | '3d';
}) {
  const centreX = scene.width_m / 2;
  const centreZ = scene.depth_m / 2;
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  return (
    <>
      <ambientLight intensity={0.85} />
      <directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow />
      {referenceUrl ? <ReferenceFloor url={referenceUrl} scene={scene} /> : null}
      {scene.rooms.map((room) => <RoomFloor key={room.id} polygon={room.polygon} />)}
      {scene.walls.map((wall) => <Wall key={wall.id} wall={wall} />)}
      {scene.assets.map((asset) => (
        <mesh key={asset.id} position={asset.position} rotation={[0, asset.rotation_y, 0]} castShadow receiveShadow>
          <boxGeometry args={asset.size} />
          <meshStandardMaterial
            color="#4f7f65"
            roughness={0.55}
            metalness={asset.slot.includes('fridge') ? 0.7 : 0.05}
          />
        </mesh>
      ))}
      <Grid
        args={[Math.max(scene.width_m, 20), Math.max(scene.depth_m, 20)]}
        position={[centreX, -0.03, centreZ]}
        cellColor="#31513f"
        sectionColor="#5b8d6e"
        fadeDistance={largest * 4}
      />
      {view === 'top' ? (
        <>
          <ResponsiveTopCamera scene={scene} />
          <OrbitControls
            makeDefault
            target={[centreX, 0, centreZ]}
            enableRotate={false}
            enableDamping
          />
        </>
      ) : (
        <>
          <PerspectiveCamera
            makeDefault
            position={[
              centreX + Math.max(scene.width_m * 0.75, 7),
              Math.max(8, largest * 0.72),
              centreZ + Math.max(scene.depth_m * 0.75, 7),
            ]}
            fov={42}
          />
          <OrbitControls makeDefault target={[centreX, 1, centreZ]} enableDamping />
        </>
      )}
    </>
  );
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
  const [view, setView] = useState<ViewMode>('top');
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
          <span className="eyebrow">3. Layout and live scene</span>
          <h2>{scene ? `${scene.rooms.length} rooms · ${scene.walls.length} structural walls` : 'Waiting for a layout'}</h2>
        </div>
        <div className="viewer-actions">
          {scene ? (
            <div className="view-switch">
              <button className={view === 'top' ? 'active' : ''} onClick={() => setView('top')}><ScanLine size={15} /> Top plan</button>
              <button className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')}><Box size={15} /> 3D</button>
              <button className={view === 'edit' ? 'active' : ''} onClick={() => setView('edit')}><Edit3 size={15} /> Edit rooms</button>
              {structureUrl ? (
                <button className={view === 'structure' ? 'active' : ''} onClick={() => setView('structure')}><Map size={15} /> Detection</button>
              ) : null}
            </div>
          ) : null}
          <span className="status-dot">{scene?.layout_mode ?? 'No'} layout</span>
        </div>
      </div>
      <div className={view === 'edit' ? 'canvas-wrap editor-canvas' : 'canvas-wrap'}>
        {scene ? (
          view === 'structure' && structureUrl ? (
            <div className="structure-preview">
              <img src={structureUrl} alt="Detected structural wall centre lines and room boundaries" />
              <div><span className="green-key" /> Structural wall centre lines <span className="orange-key" /> Room boundaries</div>
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
          ) : (
            <Canvas shadows dpr={[1, 2]} gl={{ preserveDrawingBuffer: true }}>
              <color attach="background" args={['#0a1711']} />
              {view === '3d' ? <fog attach="fog" args={['#0a1711', 25, 90]} /> : null}
              <SceneContent scene={scene} referenceUrl={referenceUrl} view={view === '3d' ? '3d' : 'top'} />
            </Canvas>
          )
        ) : (
          <div className="empty-view">
            <div className="wireframe-house" />
            <strong>Your building layout appears here</strong>
            <span>Upload a plan, then analyze it or start a manual room layout.</span>
          </div>
        )}
      </div>
      {scene?.warnings?.length ? (
        <div className="warning-strip">{scene.warnings.join(' · ')}</div>
      ) : null}
    </section>
  );
}
