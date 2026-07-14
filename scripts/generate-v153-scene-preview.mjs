import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.tsx');
const generatedPath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v153.tsx');
let source = await readFile(sourcePath, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.5.3 viewport patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /import \{ Armchair, Braces, Box, DoorOpen, Edit3, Footprints, Map, ScanLine \} from 'lucide-react';/,
  "import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Armchair, Braces, Box, DoorOpen, Edit3, Footprints, LocateFixed, Map, ScanLine } from 'lucide-react';",
  'Lucide icon import',
);

replaceOne(
  /const EYE_HEIGHT = 1\.7;\nconst DEFAULT_FOV = 88;\nconst DEFAULT_PLAYER_RADIUS = 0\.16;\nconst MAX_MOVEMENT_STEP = 0\.055;/,
  `const EYE_HEIGHT = 1.7;
const DEFAULT_FOV = 100;
const DEFAULT_PLAYER_RADIUS = 0.16;
const MAX_MOVEMENT_STEP = 0.055;
const WALKTHROUGH_HORIZONTAL_SCALE = 2;
const VIEWPORT_PAN_STEP = 1.25;

function scaleWalkthroughScene(scene: SceneManifest, scale: number): SceneManifest {
  if (Math.abs(scale - 1) < 1e-6) return scene;
  const point2 = ([x, z]: Point): Point => [x * scale, z * scale];
  const point3 = ([x, y, z]: [number, number, number]): [number, number, number] => [x * scale, y, z * scale];
  return {
    ...scene,
    width_m: scene.width_m * scale,
    depth_m: scene.depth_m * scale,
    rooms: scene.rooms.map((room) => ({
      ...room,
      polygon: room.polygon.map(point2),
      centroid: point2(room.centroid),
      area_m2: room.area_m2 * scale * scale,
      width_m: room.width_m == null ? room.width_m : room.width_m * scale,
      depth_m: room.depth_m == null ? room.depth_m : room.depth_m * scale,
    })),
    walls: scene.walls.map((wall) => ({ ...wall, start: point2(wall.start), end: point2(wall.end) })),
    openings: scene.openings.map((opening) => ({ ...opening, position: point2(opening.position) })),
    fixtures_and_furniture: scene.fixtures_and_furniture.map((item) => ({ ...item, coordinates: point3(item.coordinates) })),
    assets: scene.assets.map((asset) => ({ ...asset, position: point3(asset.position) })),
    camera_path: scene.camera_path.map(point3),
    first_person_start: scene.first_person_start ? point3(scene.first_person_start) : null,
    collision_segments: scene.collision_segments.map(([start, end]) => [point2(start), point2(end)]),
  };
}`,
  'walkthrough constants',
);

replaceOne(
  /function ResponsiveTopCamera\(\{ scene \}: \{ scene: SceneManifest \}\) \{[\s\S]*?\n\}\n\nfunction ResponsiveIsometricCamera\(\{ scene \}: \{ scene: SceneManifest \}\) \{[\s\S]*?\n\}/,
  `function ResponsiveTopCamera({ scene, panOffset }: { scene: SceneManifest; panOffset: Point }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const halfHeight = Math.max(scene.depth_m * 0.58, (scene.width_m / Math.max(aspect, 0.1)) * 0.58, 2.4);
  const halfWidth = halfHeight * aspect;
  const height = Math.max(scene.width_m, scene.depth_m, 4) * 2.2;
  return <OrthographicCamera makeDefault position={[scene.width_m / 2 + panOffset[0], height, scene.depth_m / 2 + panOffset[1]]} rotation={[-Math.PI / 2, 0, 0]} left={-halfWidth} right={halfWidth} top={halfHeight} bottom={-halfHeight} near={0.1} far={height * 3} />;
}

function ResponsiveIsometricCamera({ scene, panOffset }: { scene: SceneManifest; panOffset: Point }) {
  const { size } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  const largest = Math.max(scene.width_m, scene.depth_m, 4);
  const halfHeight = Math.max(scene.depth_m * 0.65, scene.width_m / Math.max(aspect, 0.1) * 0.65, 3);
  const target: [number, number, number] = [scene.width_m / 2 + panOffset[0], 0.55, scene.depth_m / 2 + panOffset[1]];
  return <OrthographicCamera makeDefault position={[target[0] + largest, largest * 0.95, target[2] + largest]} left={-halfHeight * aspect} right={halfHeight * aspect} top={halfHeight} bottom={-halfHeight} near={0.1} far={largest * 8} onUpdate={(camera) => camera.lookAt(...target)} />;
}`,
  'responsive camera functions',
);

replaceOne(
  /function SceneContent\(\{ project, scene, referenceUrl, view, walkthroughFov, playerRadius \}: \{\n  project: Project;\n  scene: SceneManifest;\n  referenceUrl\?: string;\n  view: RenderedViewMode;\n  walkthroughFov: number;\n  playerRadius: number;\n\}\) \{/,
  `function SceneContent({ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset }: {
  project: Project;
  scene: SceneManifest;
  referenceUrl?: string;
  view: RenderedViewMode;
  walkthroughFov: number;
  playerRadius: number;
  panOffset: Point;
}) {`,
  'SceneContent props',
);

replaceOne(
  /\{view === 'top' \? \(\n        <>\<ResponsiveTopCamera scene=\{scene\} \/><OrbitControls makeDefault target=\{\[centreX, 0, centreZ\]\} enableRotate=\{false\} enableDamping \/><\/>\n      \) : view === 'isometric' \? \(\n        <>\<ResponsiveIsometricCamera scene=\{scene\} \/><OrbitControls makeDefault target=\{\[centreX, 0\.7, centreZ\]\} enableDamping \/><\/>/,
  `{view === 'top' ? (
        <>
          <ResponsiveTopCamera scene={scene} panOffset={panOffset} />
          <OrbitControls
            makeDefault
            target={[centreX + panOffset[0], 0, centreZ + panOffset[1]]}
            enableRotate={false}
            enablePan
            screenSpacePanning
            enableDamping
            mouseButtons={{ LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN }}
          />
        </>
      ) : view === 'isometric' ? (
        <>
          <ResponsiveIsometricCamera scene={scene} panOffset={panOffset} />
          <OrbitControls
            makeDefault
            target={[centreX + panOffset[0], 0.7, centreZ + panOffset[1]]}
            enablePan
            screenSpacePanning
            enableDamping
            mouseButtons={{ LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN }}
          />
        </>`,
  'OrbitControls camera branch',
);

replaceOne(
  /const \[walkthroughFov, setWalkthroughFov\] = useState\(DEFAULT_FOV\);\n  const \[playerRadius, setPlayerRadius\] = useState\(DEFAULT_PLAYER_RADIUS\);/,
  `const [walkthroughFov, setWalkthroughFov] = useState(DEFAULT_FOV);
  const [playerRadius, setPlayerRadius] = useState(DEFAULT_PLAYER_RADIUS);
  const [viewportPan, setViewportPan] = useState<Point>([0, 0]);`,
  'ScenePreview viewport states',
);

replaceOne(
  /const referenceUrl = absoluteUrl\(scene\?\.reference_image_url \?\? project\?\.floorplan\?\.preview_url\);/,
  `const referenceUrl = absoluteUrl(scene?.reference_image_url ?? project?.floorplan?.preview_url);
  const walkthroughScene = useMemo(
    () => scene ? scaleWalkthroughScene(scene, WALKTHROUGH_HORIZONTAL_SCALE) : null,
    [scene],
  );
  const panViewport = useCallback((dx: number, dz: number) => {
    setViewportPan(([x, z]) => [x + dx, z + dz]);
  }, []);`,
  'walkthrough scene and pan helpers',
);

replaceOne(
  /<div className="three-view-wrap">\n              <Canvas/,
  `<div className="three-view-wrap">
              {view !== 'walkthrough' ? (
                <div className="viewport-pan-controls" onPointerDown={(event) => event.stopPropagation()}>
                  <strong>Pan viewport</strong>
                  <div className="viewport-pan-pad">
                    <button className="pan-up" title="Move view up" onClick={() => panViewport(0, -VIEWPORT_PAN_STEP)}><ArrowUp size={16} /></button>
                    <button className="pan-left" title="Move view left" onClick={() => panViewport(-VIEWPORT_PAN_STEP, 0)}><ArrowLeft size={16} /></button>
                    <button className="pan-reset" title="Centre view" onClick={() => setViewportPan([0, 0])}><LocateFixed size={16} /></button>
                    <button className="pan-right" title="Move view right" onClick={() => panViewport(VIEWPORT_PAN_STEP, 0)}><ArrowRight size={16} /></button>
                    <button className="pan-down" title="Move view down" onClick={() => panViewport(0, VIEWPORT_PAN_STEP)}><ArrowDown size={16} /></button>
                  </div>
                  <small>Right-drag to pan · wheel to zoom</small>
                </div>
              ) : null}
              <Canvas`,
  'viewport pan controls',
);

replaceOne(
  /scene=\{scene\}\n                    referenceUrl=\{referenceUrl\}\n                    view=\{renderedView\}\n                    walkthroughFov=\{walkthroughFov\}\n                    playerRadius=\{playerRadius\}/,
  `scene={view === 'walkthrough' && walkthroughScene ? walkthroughScene : scene}
                    referenceUrl={referenceUrl}
                    view={renderedView}
                    walkthroughFov={walkthroughFov}
                    playerRadius={playerRadius}
                    panOffset={viewportPan}`,
  'SceneContent invocation',
);

replaceOne(
  /<input type="range" min="60" max="110" step="1" value=\{walkthroughFov\}/,
  '<input type="range" min="70" max="120" step="1" value={walkthroughFov}',
  'FOV slider range',
);

replaceOne(
  /<label>Player radius <output>\{playerRadius\.toFixed\(2\)\} m<\/output>[\s\S]*?<\/label>\n                    <small>/,
  `<label>Player radius <output>{playerRadius.toFixed(2)} m</output>
                      <input type="range" min="0.12" max="0.24" step="0.01" value={playerRadius} onChange={(event) => setPlayerRadius(Number(event.target.value))} />
                    </label>
                    <div className="walkthrough-scale-readout"><span>Horizontal room spacing</span><output>{WALKTHROUGH_HORIZONTAL_SCALE.toFixed(1)}×</output></div>
                    <small>`,
  'walkthrough scale readout',
);

replaceOne(
  /WASD \/ arrows move · Shift runs · E or click opens doors · closed portals cull adjoining rooms · Esc releases mouse/,
  'WASD / arrows move · Shift runs · E or click opens doors · rooms use 2× horizontal spacing · Esc releases mouse',
  'walkthrough help copy',
);

source = `// Generated by scripts/generate-v153-scene-preview.mjs. Do not edit directly.\n${source}`;
await writeFile(generatedPath, source, 'utf8');
console.log(`Generated ${path.relative(root, generatedPath)} with panning, 100° FOV and 2× walkthrough spacing.`);
