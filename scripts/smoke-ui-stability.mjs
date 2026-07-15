import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/renderer/App.tsx', import.meta.url), 'utf8');
const main = readFileSync(new URL('../src/renderer/main.tsx', import.meta.url), 'utf8');
const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const scene = readFileSync(new URL('../src/renderer/components/ScenePreview.v161.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('../src/renderer/components/RoomLayoutEditor.v154.tsx', import.meta.url), 'utf8');
const openingEditor = readFileSync(new URL('../src/renderer/components/OpeningEditor.v160.tsx', import.meta.url), 'utf8');
const runtimeStyles = readFileSync(new URL('../src/renderer/runtime-1.5.4.css', import.meta.url), 'utf8');
const spawnStyles = readFileSync(new URL('../src/renderer/runtime-1.6.1.css', import.meta.url), 'utf8');
const standaloneStyles = readFileSync(new URL('../src/renderer/standalone-layout-1.5.5.css', import.meta.url), 'utf8');
const openingService = readFileSync(new URL('../backend/app/services/openings.py', import.meta.url), 'utf8');
const sharedPortalService = readFileSync(new URL('../backend/app/services/shared_portals.py', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(packageJson.version === '1.6.1', 'Package and installer version must be 1.6.1.');
assert(app.includes('<span>Arch-AI Convert 1.6.1</span>'), 'The visible application release label must be 1.6.1.');
assert(app.includes("./components/ScenePreview.v161"), 'The application must import the generated 1.6.1 viewport at runtime.');
assert(app.includes('guarded opening mutations'), 'Opening requests must use the application busy/error guard.');
assert(main.includes("./runtime-1.6.1.css"), 'The first-person spawn control stylesheet must be loaded.');
assert(main.includes("./standalone-layout-1.5.5.css"), 'The protected standalone layout guard must load after earlier viewport styles.');
assert(!/<PerspectiveCamera[^>]*\bposition=/.test(scene), 'Walkthrough camera must not receive a spawn position prop.');
assert(scene.includes('playerPositionRef={playerPositionRef}'), 'Walkthrough position must live above the rendered scene so view changes cannot reset it.');
assert(scene.includes('spawnAppliedRevisionRef={spawnAppliedRevisionRef}'), 'Applied spawn requests must persist across first-person remounts.');
assert(scene.includes('Spawn here'), 'First-person spawn selection controls are missing.');
assert(scene.includes('Custom coordinates'), 'Exact X/Z spawn selection is missing.');
assert(scene.includes('chooseSpawnRoom'), 'Room-centre spawn selection is missing.');
assert(scene.includes('pointIsBlocked(activeScene, point'), 'Spawn points must be collision checked before teleporting.');
assert(scene.includes('CutawayGround'), 'The cutaway ground surface is missing.');
assert(scene.includes('<extrudeGeometry args={[shape, { depth: 0.08'), 'Room floors must render as solid slabs rather than zero-thickness faces.');
assert(scene.includes('WalkthroughCamera'), 'Dynamic FOV camera component is missing.');
assert(scene.includes('updateProjectionMatrix()'), 'FOV changes must update the projection matrix.');
assert(scene.includes('DEFAULT_FOV = 100'), 'The wider 100-degree default FOV is missing.');
assert(scene.includes('DEFAULT_PLAYER_RADIUS = 0.14'), 'The reduced narrow-corridor player radius is missing.');
assert(scene.includes('max="120"'), 'The 120-degree FOV range is missing.');
assert(scene.includes('WALKTHROUGH_HORIZONTAL_SCALE = 2'), 'The two-times horizontal walkthrough scale is missing.');
assert(scene.includes('const portalDepth = wall.thickness / 2 + playerRadius + 0.06'), 'Portal collision must include a perpendicular depth test.');
assert(scene.includes('viewport-pan-controls'), 'Directional synchronized viewport pan buttons are missing.');
assert(scene.includes('FirstPersonInputGuard'), 'First-person mouse/window input isolation is missing.');
assert(scene.includes('ACESFilmicToneMapping'), 'Filmic tone mapping is missing.');
assert(scene.includes('ImportedCharacter'), 'Normalised realistic character model support is missing.');
assert(openingEditor.includes('function openingWallIds'), 'Shared wall ownership helper is missing.');
assert(openingEditor.includes("opening.wall_id ?? opening.wall_ids?.[0] ?? ''"), 'Shared portals must remain editable through a primary linked wall.');
assert(openingEditor.includes('submissionRef.current'), 'Door creation must suppress repeated submissions.');
assert(openingEditor.includes('Boolean(selectedOpening)'), 'The add action must be disabled while editing an existing portal.');
assert(openingEditor.includes('shared portal'), 'Shared portal status must be visible in the opening editor.');
assert(openingService.includes('_deduplicate_portals'), 'Backend canonical portal deduplication is missing.');
assert(openingService.includes('duplicate = _equivalent_portal'), 'Opposite-wall placements must resolve to an existing portal.');
assert(sharedPortalService.includes('shared_wall_cluster'), 'Touching independent walls must be grouped for one portal cut.');
assert(editor.includes("type EditMode = 'pan'"), 'Edit Rooms pan mode is missing.');
assert(editor.includes('room-pan-controls'), 'Edit Rooms directional pan buttons are missing.');
assert(editor.includes('panDragRef'), 'Edit Rooms mouse panning is missing.');
assert(editor.includes('onWheel={handleWheel}'), 'Mouse-wheel plan zoom is missing.');
assert(editor.includes('viewBox={viewport.value}'), 'Pannable zoomable SVG viewport is missing.');
assert(runtimeStyles.includes('grid-template-columns: clamp(330px, 27vw, 420px) minmax(0, 1fr)'), 'Adaptive base workspace is missing.');
assert(runtimeStyles.includes('.walkthrough-active canvas'), 'First-person canvas input containment styles are missing.');
assert(spawnStyles.includes('.walkthrough-spawn-controls'), 'First-person spawn controls styling is missing.');
assert(runtimeStyles.includes('.room-pan-controls'), 'Edit Rooms pan styling is missing.');
assert(standaloneStyles.includes('--workspace-column-gap: clamp(34px, 3.6vw, 64px)'), 'The protected renderer gutter is missing.');
assert(standaloneStyles.includes('.left-column::after'), 'The visual separator between controls and rendering is missing.');
assert(standaloneStyles.includes('contain: layout paint style'), 'Independent paint containment is missing.');
assert(/background:\s*linear-gradient/.test(standaloneStyles), 'The opaque standalone control-rail background is missing.');
assert(standaloneStyles.includes('@media (max-width: 1060px)'), 'The early non-overlap stacking breakpoint is missing.');
assert(standaloneStyles.includes('.three-view-wrap canvas'), 'WebGL canvas width containment is missing.');

console.log('UI stability smoke test passed: version 1.6.1, selectable first-person spawning, solid cutaway ground, canonical shared portals, persistent navigation, strict exterior collision, panning, PBR and protected layout');
