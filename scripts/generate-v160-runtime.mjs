import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function replaceOne(source, pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.6.0 runtime patch could not find: ${label}`);
  return source.replace(pattern, replacement);
}

const openingSourcePath = path.join(root, 'src', 'renderer', 'components', 'OpeningEditor.tsx');
const openingGeneratedPath = path.join(root, 'src', 'renderer', 'components', 'OpeningEditor.v160.tsx');
let openingSource = await readFile(openingSourcePath, 'utf8');

openingSource = replaceOne(
  openingSource,
  /wall_id: opening\.wall_id \?\? '',/,
  "wall_id: opening.wall_id ?? opening.wall_ids?.[0] ?? '',",
  'shared opening primary-wall fallback',
);

openingSource = replaceOne(
  openingSource,
  /function openingColour\(opening: Opening\): string \{\n  if \(opening\.wall_id == null\) return '#ea6f74';\n  if \(WINDOW_TYPES\.has\(opening\.opening_type\)\) return '#78c8ef';\n  if \(opening\.opening_type === 'open_passage'\) return '#d7a861';\n  return opening\.source === 'manual' \? '#77e19d' : '#f0c66a';\n\}/,
  `function openingWallIds(opening: Opening): string[] {
  const ids = new Set(opening.wall_ids ?? []);
  if (opening.wall_id) ids.add(opening.wall_id);
  return [...ids];
}

function openingColour(opening: Opening): string {
  if (openingWallIds(opening).length === 0) return '#ea6f74';
  if (WINDOW_TYPES.has(opening.opening_type)) return '#78c8ef';
  if (opening.opening_type === 'open_passage') return '#d7a861';
  return opening.source === 'manual' ? '#77e19d' : '#f0c66a';
}`,
  'shared portal attachment colour',
);

openingSource = replaceOne(
  openingSource,
  /const \[draft, setDraft\] = useState<DirectDraft>\(\(\) => initialPayload\(scene\)\);/,
  `const [draft, setDraft] = useState<DirectDraft>(() => initialPayload(scene));
  const [submitting, setSubmitting] = useState(false);
  const submissionRef = useRef(false);`,
  'opening submission guard state',
);

openingSource = replaceOne(
  openingSource,
  /const grouped = useMemo\(\(\) => \['Doors', 'Windows', 'Openings'\] as const, \[\]\);/,
  `const grouped = useMemo(() => ['Doors', 'Windows', 'Openings'] as const, []);
  const selectedWallIds = useMemo(
    () => new Set(selectedOpening ? openingWallIds(selectedOpening) : draft.wall_id ? [draft.wall_id] : []),
    [selectedOpening, draft.wall_id],
  );`,
  'shared portal wall highlighting',
);

openingSource = replaceOne(
  openingSource,
  /  const add = async \(\) => onAddOpening\(draft\);\n  const save = async \(\) => \{\n    if \(selectedOpening\) await onUpdateOpening\(selectedOpening\.id, draft\);\n  \};\n  const remove = async \(\) => \{\n    if \(!selectedOpening \|\| !window\.confirm\(`Delete \$\{itemFor\(selectedOpening\.opening_type\)\.label\}\?`\)\) return;\n    await onDeleteOpening\(selectedOpening\.id\);\n    setSelectedOpeningId\(null\);\n  \};/,
  `  const execute = async (task: () => Promise<void>) => {
    if (busy || submissionRef.current) return;
    submissionRef.current = true;
    setSubmitting(true);
    try {
      await task();
    } finally {
      submissionRef.current = false;
      setSubmitting(false);
    }
  };
  const add = async () => execute(async () => {
    await onAddOpening(draft);
  });
  const save = async () => execute(async () => {
    if (selectedOpening) await onUpdateOpening(selectedOpening.id, draft);
  });
  const remove = async () => {
    if (!selectedOpening || !window.confirm(\`Delete \${itemFor(selectedOpening.opening_type).label}?\`)) return;
    await execute(async () => {
      await onDeleteOpening(selectedOpening.id);
      setSelectedOpeningId(null);
    });
  };`,
  'opening mutation guard',
);

openingSource = replaceOne(
  openingSource,
  /const draftDz = Math\.sin\(draftRotation\) \* \(draft\.width \?\? 0\.9\) \/ 2;/,
  `const draftDz = Math.sin(draftRotation) * (draft.width ?? 0.9) / 2;
  const controlsLocked = busy || submitting;`,
  'opening control lock',
);

openingSource = replaceOne(
  openingSource,
  /className=\{wall\.id === draft\.wall_id \? 'opening-wall selected' : 'opening-wall'\}/,
  "className={selectedWallIds.has(wall.id) ? 'opening-wall selected' : 'opening-wall'}",
  'all shared walls highlighted',
);

openingSource = replaceOne(
  openingSource,
  /\{itemFor\(opening\.opening_type\)\.label\}<\/text>/,
  "{itemFor(opening.opening_type).label}{openingWallIds(opening).length > 1 ? ' · shared portal' : ''}</text>",
  'shared portal label',
);

openingSource = replaceOne(
  openingSource,
  /<div><strong>Direct door and window placement<\/strong><span>Works before rooms or walls are detected\. Nearby walls are optional snap targets\.<\/span><\/div>/,
  `<div><strong>Direct door and window placement</strong><span>{selectedOpening && openingWallIds(selectedOpening).length > 1
            ? \`Shared portal: one opening cuts \${openingWallIds(selectedOpening).length} independent touching walls.\`
            : 'Works before rooms or walls are detected. Nearby walls are optional snap targets.'}</span></div>`,
  'shared portal status copy',
);

openingSource = replaceOne(
  openingSource,
  /<button className="primary" disabled=\{busy\} onClick=\{\(\) => void add\(\)\}><Plus size=\{16\} \/> Add at clicked position<\/button>\n          <button className="secondary" disabled=\{busy \|\| !selectedOpening\} onClick=\{\(\) => void save\(\)\}><Save size=\{16\} \/> Save selected<\/button>\n          <button className="danger-icon" disabled=\{busy \|\| !selectedOpening\} onClick=\{\(\) => void remove\(\)\}><Trash2 size=\{16\} \/> Delete<\/button>/,
  `<button className="primary" disabled={controlsLocked || Boolean(selectedOpening)} onClick={() => void add()}><Plus size={16} /> Add at clicked position</button>
          <button className="secondary" disabled={controlsLocked || !selectedOpening} onClick={() => void save()}><Save size={16} /> Save selected</button>
          <button className="danger-icon" disabled={controlsLocked || !selectedOpening} onClick={() => void remove()}><Trash2 size={16} /> Delete</button>`,
  'opening action lock',
);

openingSource = `// Generated by scripts/generate-v160-runtime.mjs. Do not edit directly.\n${openingSource}`;
await writeFile(openingGeneratedPath, openingSource, 'utf8');

const sceneSourcePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v154.tsx');
const sceneGeneratedPath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.v160.tsx');
let sceneSource = await readFile(sceneSourcePath, 'utf8');

sceneSource = replaceOne(
  sceneSource,
  /import \{ OpeningEditor \} from '\.\/OpeningEditor';/,
  "import { OpeningEditor } from './OpeningEditor.v160';",
  'generated opening editor import',
);

sceneSource = replaceOne(
  sceneSource,
  /const DEFAULT_PLAYER_RADIUS = 0\.16;/,
  'const DEFAULT_PLAYER_RADIUS = 0.14;',
  'narrow-corridor player radius',
);

sceneSource = replaceOne(
  sceneSource,
  /const along = point\.clone\(\)\.sub\(start\)\.dot\(vector\.divideScalar\(length\)\);\n    const usableHalfWidth = Math\.max\(0\.06, opening\.width \/ 2 - playerRadius \* 0\.72\);\n    return Math\.abs\(along - centre\) <= usableHalfWidth;/,
  `const direction = vector.divideScalar(length);
    const relative = point.clone().sub(start);
    const along = relative.dot(direction);
    const perpendicular = Math.abs(relative.x * -direction.y + relative.y * direction.x);
    const portalDepth = wall.thickness / 2 + playerRadius + 0.06;
    if (perpendicular > portalDepth) return false;
    const usableHalfWidth = Math.max(0.06, opening.width / 2 - playerRadius * 0.72);
    return Math.abs(along - centre) <= usableHalfWidth;`,
  'strict portal depth collision',
);

sceneSource = replaceOne(
  sceneSource,
  /function SceneContent\(\{ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset \}: \{\n  project: Project;\n  scene: SceneManifest;\n  referenceUrl\?: string;\n  view: RenderedViewMode;\n  walkthroughFov: number;\n  playerRadius: number;\n  panOffset: Point;\n\}\) \{/,
  `function SceneContent({ project, scene, referenceUrl, view, walkthroughFov, playerRadius, panOffset, playerPositionRef }: {
  project: Project;
  scene: SceneManifest;
  referenceUrl?: string;
  view: RenderedViewMode;
  walkthroughFov: number;
  playerRadius: number;
  panOffset: Point;
  playerPositionRef: MutableRefObject<THREE.Vector3 | null>;
}) {`,
  'persistent walkthrough position prop',
);

sceneSource = replaceOne(
  sceneSource,
  /  const playerPositionRef = useRef<THREE\.Vector3 \| null>\(null\);\n/,
  '',
  'remove scene-local player position',
);

sceneSource = replaceOne(
  sceneSource,
  /const \[playerRadius, setPlayerRadius\] = useState\(DEFAULT_PLAYER_RADIUS\);\n  const \[viewportPan, setViewportPan\] = useState<Point>\(\[0, 0\]\);/,
  `const [playerRadius, setPlayerRadius] = useState(DEFAULT_PLAYER_RADIUS);
  const [viewportPan, setViewportPan] = useState<Point>([0, 0]);
  const playerPositionRef = useRef<THREE.Vector3 | null>(null);`,
  'viewport-level player position state',
);

sceneSource = replaceOne(
  sceneSource,
  /panOffset=\{viewportPan\}/,
  `panOffset={viewportPan}
                    playerPositionRef={playerPositionRef}`,
  'walkthrough position prop wiring',
);

sceneSource = replaceOne(
  sceneSource,
  /Click the scene to lock the mouse to the character camera\. While locked, mouse, arrows and wheel cannot scroll or move the application window\. Press Esc to release\./,
  'Click the scene to lock the camera. Door interaction, room transitions and FOV changes preserve the live player position. Press Esc to release.',
  'walkthrough persistence help',
);

sceneSource = `// Generated by scripts/generate-v160-runtime.mjs. Do not edit directly.\n${sceneSource}`;
await writeFile(sceneGeneratedPath, sceneSource, 'utf8');

console.log(`Generated ${path.relative(root, openingGeneratedPath)} and ${path.relative(root, sceneGeneratedPath)} with canonical shared portals, guarded mutations and persistent walkthrough position.`);
