import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scenePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v154.tsx');
let source = await readFile(scenePath, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.5.6 stability patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /function RoomFloor\(\{ room, scene \}: \{ room: RoomShape; scene: SceneManifest \}\) \{[\s\S]*?\n\}\n\nfunction ReferenceFloor\(\{ url, scene \}: \{ url: string; scene: SceneManifest \}\) \{[\s\S]*?\n\}/,
  `function RoomFloor({ room, scene }: { room: RoomShape; scene: SceneManifest }) {
  const shape = useMemo(() => {
    const result = new THREE.Shape();
    room.polygon.forEach(([x, z], index) => (index === 0 ? result.moveTo(x, z) : result.lineTo(x, z)));
    result.closePath();
    return result;
  }, [room.polygon]);
  return (
    <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.002, 0]} receiveShadow>
      <shapeGeometry args={[shape]} />
      <PbrMaterial spec={scene.materials.floor_global} />
    </mesh>
  );
}

function useSafeTexture(url?: string) {
  const [texture, setTexture] = useState<THREE.Texture | null>(null);
  useEffect(() => {
    if (!url) {
      setTexture(null);
      return undefined;
    }
    let active = true;
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin('anonymous');
    loader.load(
      url,
      (loaded) => {
        if (!active) { loaded.dispose(); return; }
        loaded.colorSpace = THREE.SRGBColorSpace;
        loaded.anisotropy = 8;
        loaded.needsUpdate = true;
        setTexture((previous) => { if (previous && previous !== loaded) previous.dispose(); return loaded; });
      },
      undefined,
      () => { if (active) setTexture(null); },
    );
    return () => { active = false; };
  }, [url]);
  return texture;
}

function ReferenceFloor({ url, scene, opacity }: { url: string; scene: SceneManifest; opacity: number }) {
  const texture = useSafeTexture(url);
  if (!texture) return null;
  return (
    <mesh position={[scene.width_m / 2, 0.016, scene.depth_m / 2]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={4}>
      <planeGeometry args={[scene.width_m, scene.depth_m]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={opacity}
        side={THREE.DoubleSide}
        depthWrite={false}
        polygonOffset
        polygonOffsetFactor={-2}
      />
    </mesh>
  );
}

function ContinuousBuildingFloor({ scene, maskUrl }: { scene: SceneManifest; maskUrl?: string }) {
  const mask = useSafeTexture(maskUrl);
  const mappedFloor = useSafeTexture(absoluteUrl(scene.materials.floor_global.texture_url));
  if (!mask) {
    return <>{scene.rooms.map((room) => <RoomFloor key={room.id} room={room} scene={scene} />)}</>;
  }
  if (mappedFloor) {
    mappedFloor.wrapS = mappedFloor.wrapT = THREE.RepeatWrapping;
    mappedFloor.repeat.set(scene.materials.floor_global.texture_scale, scene.materials.floor_global.texture_scale);
  }
  return (
    <mesh position={[scene.width_m / 2, 0.004, scene.depth_m / 2]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[scene.width_m, scene.depth_m]} />
      <meshStandardMaterial
        color={scene.materials.floor_global.hex_color}
        map={mappedFloor ?? undefined}
        alphaMap={mask}
        alphaTest={0.08}
        transparent
        roughness={scene.materials.floor_global.roughness}
        metalness={scene.materials.floor_global.metallic}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}`,
  'room and reference floor components',
);

replaceOne(
  /function SceneContent\(\{ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset \}: \{\n  project: Project;\n  scene: SceneManifest;\n  referenceUrl\?: string;\n  view: RenderedViewMode;\n  walkthroughFov: number;\n  playerRadius: number;\n  panOffset: Point;\n\}\) \{/,
  `function SceneContent({ project, scene, referenceUrl, buildingMaskUrl, view, walkthroughFov, playerRadius, panOffset }: {
  project: Project;
  scene: SceneManifest;
  referenceUrl?: string;
  buildingMaskUrl?: string;
  view: RenderedViewMode;
  walkthroughFov: number;
  playerRadius: number;
  panOffset: Point;
}) {`,
  'SceneContent stability props',
);

replaceOne(
  /<directionalLight position=\{\[centreX \+ 8, 16, centreZ \+ 10\]\} intensity=\{2\.1\} castShadow shadow-mapSize-width=\{4096\} shadow-mapSize-height=\{4096\} shadow-bias=\{-0\.00015\} \/>\n      <RealisticEnvironment centreX=\{centreX\} centreZ=\{centreZ\} largest=\{largest\} walkthrough=\{view === 'walkthrough'\} \/>/,
  `<directionalLight position={[centreX + 8, 16, centreZ + 10]} intensity={2.1} castShadow={view !== 'top'} shadow-mapSize-width={view === 'top' ? 1024 : 4096} shadow-mapSize-height={view === 'top' ? 1024 : 4096} shadow-bias={-0.00015} />
      {view !== 'top' ? <RealisticEnvironment centreX={centreX} centreZ={centreZ} largest={largest} walkthrough={view === 'walkthrough'} /> : null}`,
  'top-plan rendering isolation',
);

replaceOne(
  /\{referenceUrl && view === 'top' \? <ReferenceFloor url=\{referenceUrl\} scene=\{scene\} \/> : null\}\n      \{scene\.rooms\.filter\(\(room\) => visibleRooms\.has\(room\.id\)\)\.map\(\(room\) => <RoomFloor key=\{room\.id\} room=\{room\} scene=\{scene\} \/>\)\}/,
  `{view !== 'walkthrough' && referenceUrl ? <ReferenceFloor url={referenceUrl} scene={scene} opacity={view === 'top' ? 0.74 : 0.32} /> : null}
      <ContinuousBuildingFloor scene={scene} maskUrl={buildingMaskUrl} />`,
  'shared underlay and continuous floor',
);

replaceOne(
  /if \(scene\.rooms\.length > 0 && !roomAt\(scene, \[point\.x, point\.y\]\) && !insidePortal\) return true;/,
  `if (scene.rooms.length > 0 && !roomAt(scene, [point.x, point.y]) && !insidePortal) {
    const nearInteriorBoundary = scene.rooms.some((room) => boundaryDistance([point.x, point.y], room.polygon) <= Math.max(0.1, playerRadius * 0.85));
    if (!nearInteriorBoundary) return true;
  }`,
  'walkable threshold tolerance',
);

replaceOne(
  /const referenceUrl = absoluteUrl\(scene\?\.reference_image_url \?\? project\?\.floorplan\?\.preview_url\);/,
  `const referenceUrl = absoluteUrl(project?.floorplan?.preview_url ?? scene?.reference_image_url);
  const buildingMaskUrl = project?.id ? absoluteUrl(\`/api/v1/projects/\${project.id}/building-mask\`) : undefined;`,
  'canonical floor-plan URLs',
);

replaceOne(
  /scene=\{view === 'walkthrough' && walkthroughScene \? walkthroughScene : scene\}\n                    referenceUrl=\{referenceUrl\}/,
  `scene={view === 'walkthrough' && walkthroughScene ? walkthroughScene : scene}
                    referenceUrl={referenceUrl}
                    buildingMaskUrl={buildingMaskUrl}`,
  'building mask SceneContent invocation',
);

replaceOne(
  /<Canvas\n                shadows/,
  `<Canvas
                key={\`viewport-\${view}-\${scene.project_id}\`}
                shadows`,
  'isolated canvas per viewport mode',
);

replaceOne(
  /<div className="structure-preview"><img src=\{structureUrl\} alt="Detected walls, rooms, doors, windows and furniture" \/><div>/,
  `<div className="structure-preview layered-structure-preview">
              {referenceUrl ? <img className="structure-reference" src={referenceUrl} alt="Uploaded floor plan" /> : null}
              <img className="structure-overlay" src={structureUrl} alt="Detected walls, rooms, doors, windows and furniture" />
              <div>`,
  'detection reference image layering',
);

source = `// Patched by scripts/patch-v156-stability.mjs.\n${source}`;
await writeFile(scenePath, source, 'utf8');
console.log(`Patched ${path.relative(root, scenePath)} with stable floor-plan underlays, continuous floors and isolated Top Plan cameras.`);
