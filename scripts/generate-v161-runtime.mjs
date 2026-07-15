import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v160.tsx');
const generatedPath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v161.tsx');
let source = await readFile(sourcePath, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.6.1 runtime patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /type RenderedViewMode = 'isometric' \| 'top' \| 'walkthrough';/,
  `type RenderedViewMode = 'isometric' | 'top' | 'walkthrough';
type SpawnRequest = { point: Point; revision: number };`,
  'spawn request type',
);

replaceOne(
  /<mesh rotation=\{\[Math\.PI \/ 2, 0, 0\]\} position=\{\[0, 0\.005, 0\]\} receiveShadow>\n      <shapeGeometry args=\{\[shape\]\} \/>\n      <PbrMaterial spec=\{scene\.materials\.floor_global\} \/>\n    <\/mesh>/,
  `<mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.04, 0]} castShadow receiveShadow>
      <extrudeGeometry args={[shape, { depth: 0.08, bevelEnabled: false, steps: 1 }]} />
      <PbrMaterial spec={scene.materials.floor_global} />
    </mesh>`,
  'solid room floor slab',
);

replaceOne(
  /function ReferenceFloor\(\{ url, scene \}: \{ url: string; scene: SceneManifest \}\) \{/,
  `function CutawayGround({ scene }: { scene: SceneManifest }) {
  const margin = Math.max(1.25, Math.min(4, Math.max(scene.width_m, scene.depth_m) * 0.12));
  return (
    <mesh position={[scene.width_m / 2, -0.1, scene.depth_m / 2]} receiveShadow>
      <boxGeometry args={[scene.width_m + margin * 2, 0.12, scene.depth_m + margin * 2]} />
      <meshStandardMaterial color="#263b30" roughness={0.96} metalness={0} />
    </mesh>
  );
}

function ReferenceFloor({ url, scene }: { url: string; scene: SceneManifest }) {`,
  'cutaway ground surface',
);

replaceOne(
  /function FirstPersonRig\(\{\n  scene,\n  openDoorIds,\n  onToggleDoor,\n  onRoomChange,\n  playerRadius,\n  playerPositionRef,\n\}: \{\n  scene: SceneManifest;\n  openDoorIds: Set<string>;\n  onToggleDoor: \(openingId: string\) => void;\n  onRoomChange: \(roomId: string \| null\) => void;\n  playerRadius: number;\n  playerPositionRef: MutableRefObject<THREE\.Vector3 \| null>;\n\}\) \{/,
  `function FirstPersonRig({
  scene,
  openDoorIds,
  onToggleDoor,
  onRoomChange,
  playerRadius,
  playerPositionRef,
  spawnRequest,
  spawnAppliedRevisionRef,
}: {
  scene: SceneManifest;
  openDoorIds: Set<string>;
  onToggleDoor: (openingId: string) => void;
  onRoomChange: (roomId: string | null) => void;
  playerRadius: number;
  playerPositionRef: MutableRefObject<THREE.Vector3 | null>;
  spawnRequest: SpawnRequest | null;
  spawnAppliedRevisionRef: MutableRefObject<number>;
}) {`,
  'first-person spawn request prop',
);

replaceOne(
  /  useEffect\(\(\) => \{ radiusRef\.current = playerRadius; \}, \[playerRadius\]\);/,
  `  useEffect(() => { radiusRef.current = playerRadius; }, [playerRadius]);

  useEffect(() => {
    if (!spawnRequest || spawnRequest.revision === spawnAppliedRevisionRef.current) return;
    spawnAppliedRevisionRef.current = spawnRequest.revision;
    const activeScene = sceneRef.current;
    const point = new THREE.Vector2(spawnRequest.point[0], spawnRequest.point[1]);
    if (pointIsBlocked(activeScene, point, openDoorIdsRef.current, radiusRef.current)) return;
    const position = new THREE.Vector3(point.x, EYE_HEIGHT, point.y);
    camera.position.copy(position);
    playerPositionRef.current = position.clone();
    velocity.current.set(0, 0, 0);
    elapsed.current = 0;
    const roomId = roomAt(activeScene, [position.x, position.z])?.id ?? null;
    lastRoomId.current = roomId;
    roomChangeRef.current(roomId);
  }, [camera, playerPositionRef, spawnAppliedRevisionRef, spawnRequest]);`,
  'spawn teleport effect',
);

replaceOne(
  /function SceneContent\(\{ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset, playerPositionRef \}: \{\n  project: Project;\n  scene: SceneManifest;\n  referenceUrl\?: string;\n  view: RenderedViewMode;\n  walkthroughFov: number;\n  playerRadius: number;\n  panOffset: Point;\n  playerPositionRef: MutableRefObject<THREE\.Vector3 \| null>;\n\}\) \{/,
  `function SceneContent({ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset, playerPositionRef, spawnRequest, spawnAppliedRevisionRef }: {
  project: Project;
  scene: SceneManifest;
  referenceUrl?: string;
  view: RenderedViewMode;
  walkthroughFov: number;
  playerRadius: number;
  panOffset: Point;
  playerPositionRef: MutableRefObject<THREE.Vector3 | null>;
  spawnRequest: SpawnRequest | null;
  spawnAppliedRevisionRef: MutableRefObject<number>;
}) {`,
  'scene spawn request prop',
);

replaceOne(
  /\{referenceUrl && view === 'top' \? <ReferenceFloor url=\{referenceUrl\} scene=\{scene\} \/> : null\}/,
  `{view === 'isometric' ? <CutawayGround scene={scene} /> : null}
      {referenceUrl && view === 'top' ? <ReferenceFloor url={referenceUrl} scene={scene} /> : null}`,
  'cutaway ground render',
);

replaceOne(
  /onRoomChange=\{setCurrentRoomId\}\n\s+playerRadius=\{playerRadius\}\n\s+playerPositionRef=\{playerPositionRef\}/,
  `onRoomChange={setCurrentRoomId}
            playerRadius={playerRadius}
            playerPositionRef={playerPositionRef}
            spawnRequest={spawnRequest}
            spawnAppliedRevisionRef={spawnAppliedRevisionRef}`,
  'first-person spawn wiring',
);

replaceOne(
  /const \[playerRadius, setPlayerRadius\] = useState\(DEFAULT_PLAYER_RADIUS\);\n  const \[viewportPan, setViewportPan\] = useState<Point>\(\[0, 0\]\);\n  const playerPositionRef = useRef<THREE\.Vector3 \| null>\(null\);/,
  `const [playerRadius, setPlayerRadius] = useState(DEFAULT_PLAYER_RADIUS);
  const [viewportPan, setViewportPan] = useState<Point>([0, 0]);
  const [spawnRoomId, setSpawnRoomId] = useState('__default');
  const [spawnPoint, setSpawnPoint] = useState<Point>([0, 0]);
  const [spawnRevision, setSpawnRevision] = useState(0);
  const playerPositionRef = useRef<THREE.Vector3 | null>(null);
  const spawnAppliedRevisionRef = useRef(0);`,
  'spawn selection state',
);

replaceOne(
  /  const panViewport = useCallback\(\(dx: number, dz: number\) => \{\n    setViewportPan\(\(\[x, z\]\) => \[x \+ dx, z \+ dz\]\);\n  \}, \[\]\);/,
  `  const panViewport = useCallback((dx: number, dz: number) => {
    setViewportPan(([x, z]) => [x + dx, z + dz]);
  }, []);

  useEffect(() => {
    if (!scene) return;
    const start: Point = scene.first_person_start
      ? [scene.first_person_start[0], scene.first_person_start[2]]
      : scene.rooms[0]
        ? [scene.rooms[0].centroid[0], scene.rooms[0].centroid[1]]
        : [scene.width_m / 2, scene.depth_m / 2];
    setSpawnRoomId('__default');
    setSpawnPoint(start);
  }, [scene?.project_id]);

  const chooseSpawnRoom = useCallback((choice: string) => {
    if (!scene) return;
    setSpawnRoomId(choice);
    if (choice === '__custom') return;
    if (choice === '__default') {
      const start: Point = scene.first_person_start
        ? [scene.first_person_start[0], scene.first_person_start[2]]
        : scene.rooms[0]
          ? [scene.rooms[0].centroid[0], scene.rooms[0].centroid[1]]
          : [scene.width_m / 2, scene.depth_m / 2];
      setSpawnPoint(start);
      return;
    }
    const room = scene.rooms.find((candidate) => candidate.id === choice);
    if (room) setSpawnPoint([room.centroid[0], room.centroid[1]]);
  }, [scene]);

  const spawnRoom = scene ? roomAt(scene, spawnPoint) : null;
  const spawnWithinBounds = Boolean(
    scene
    && spawnPoint[0] >= 0
    && spawnPoint[1] >= 0
    && spawnPoint[0] <= scene.width_m
    && spawnPoint[1] <= scene.depth_m
  );
  const spawnClearance = spawnRoom ? boundaryDistance(spawnPoint, spawnRoom.polygon) : Number.POSITIVE_INFINITY;
  const spawnLocationValid = Boolean(
    scene
    && spawnWithinBounds
    && (scene.rooms.length === 0 || spawnRoom)
    && spawnClearance > Math.max(0.04, playerRadius / WALKTHROUGH_HORIZONTAL_SCALE)
  );
  const activeSpawnRequest = useMemo<SpawnRequest | null>(
    () => spawnRevision > 0
      ? {
        point: [
          spawnPoint[0] * WALKTHROUGH_HORIZONTAL_SCALE,
          spawnPoint[1] * WALKTHROUGH_HORIZONTAL_SCALE,
        ],
        revision: spawnRevision,
      }
      : null,
    [spawnPoint, spawnRevision],
  );
  const applySpawn = useCallback(() => {
    if (!spawnLocationValid) return;
    setSpawnRevision((current) => current + 1);
  }, [spawnLocationValid]);`,
  'spawn selection helpers',
);

replaceOne(
  /panOffset=\{viewportPan\}\n\s+playerPositionRef=\{playerPositionRef\}/,
  `panOffset={viewportPan}
                     playerPositionRef={playerPositionRef}
                     spawnRequest={activeSpawnRequest}
                     spawnAppliedRevisionRef={spawnAppliedRevisionRef}`,
  'scene spawn request wiring',
);

replaceOne(
  /<strong>Walkthrough view<\/strong>/,
  `<strong>Walkthrough view</strong>
                    <div className="walkthrough-spawn-controls">
                      <label>Spawn location
                        <select value={spawnRoomId} onChange={(event) => chooseSpawnRoom(event.target.value)}>
                          <option value="__default">Plan default</option>
                          <option value="__custom">Custom coordinates</option>
                          {scene.rooms.map((room, index) => (
                            <option key={room.id} value={room.id}>{room.name || \`Room \${index + 1}\`} centre</option>
                          ))}
                        </select>
                      </label>
                      <div className="spawn-coordinate-grid">
                        <label>X position (m)
                          <input
                            type="number"
                            min="0"
                            max={scene.width_m}
                            step="0.1"
                            value={Number.isFinite(spawnPoint[0]) ? spawnPoint[0] : 0}
                            onChange={(event) => {
                              setSpawnRoomId('__custom');
                              setSpawnPoint(([, z]) => [Number(event.target.value), z]);
                            }}
                          />
                        </label>
                        <label>Z position (m)
                          <input
                            type="number"
                            min="0"
                            max={scene.depth_m}
                            step="0.1"
                            value={Number.isFinite(spawnPoint[1]) ? spawnPoint[1] : 0}
                            onChange={(event) => {
                              setSpawnRoomId('__custom');
                              setSpawnPoint(([x]) => [x, Number(event.target.value)]);
                            }}
                          />
                        </label>
                      </div>
                      <button type="button" className="secondary spawn-here-button" disabled={!spawnLocationValid} onClick={applySpawn}>
                        <LocateFixed size={15} /> Spawn here
                      </button>
                      <small className={spawnLocationValid ? 'spawn-status valid' : 'spawn-status invalid'}>
                        {spawnLocationValid ? 'Valid interior spawn point. Press Spawn here to move immediately.' : 'Choose a point inside a room and clear of its walls.'}
                      </small>
                    </div>`,
  'walkthrough spawn controls',
);

replaceOne(
  /Click the scene to lock the camera\. Door interaction, room transitions and FOV changes preserve the live player position\. Press Esc to release\./,
  'Choose a room centre or exact X/Z position, then press Spawn here. Click the scene to lock the camera; press Esc to release.',
  'walkthrough spawn help',
);

replaceOne(
  /WASD \/ arrows move · Shift runs · E or click opens doors · rooms use 2× horizontal spacing · Esc releases mouse/,
  'Choose spawn room/X/Z · WASD / arrows move · Shift runs · E or click opens doors · rooms use 2× horizontal spacing · Esc releases mouse',
  'walkthrough spawn summary',
);

source = `// Generated by scripts/generate-v161-runtime.mjs. Do not edit directly.\n${source}`;
await writeFile(generatedPath, source, 'utf8');
console.log(`Generated ${path.relative(root, generatedPath)} with selectable first-person spawning and solid cutaway ground.`);
