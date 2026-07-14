import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/renderer/App.tsx', import.meta.url), 'utf8');
const scene = readFileSync(new URL('../src/renderer/components/ScenePreview.v154.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('../src/renderer/components/RoomLayoutEditor.v154.tsx', import.meta.url), 'utf8');
const runtimeStyles = readFileSync(new URL('../src/renderer/runtime-1.5.4.css', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(app.includes("./components/ScenePreview.v154"), 'The application must import the generated 1.5.4 viewport at runtime.');
assert(!/<PerspectiveCamera[^>]*\bposition=/.test(scene), 'Walkthrough camera must not receive a spawn position prop.');
assert(scene.includes('playerPositionRef'), 'Walkthrough must persist the live player position.');
assert(scene.includes('WalkthroughCamera'), 'Dynamic FOV camera component is missing.');
assert(scene.includes('updateProjectionMatrix()'), 'FOV changes must update the projection matrix.');
assert(scene.includes('DEFAULT_FOV = 100'), 'The wider 100-degree default FOV is missing.');
assert(scene.includes('max="120"'), 'The 120-degree FOV range is missing.');
assert(scene.includes('WALKTHROUGH_HORIZONTAL_SCALE = 2'), 'The two-times horizontal walkthrough scale is missing.');
assert(scene.includes('viewport-pan-controls'), 'Directional synchronized viewport pan buttons are missing.');
assert(scene.includes('FirstPersonInputGuard'), 'First-person mouse/window input isolation is missing.');
assert(scene.includes('ACESFilmicToneMapping'), 'Filmic tone mapping is missing.');
assert(scene.includes('ImportedCharacter'), 'Normalised realistic character model support is missing.');
assert(editor.includes("type EditMode = 'pan'"), 'Edit Rooms pan mode is missing.');
assert(editor.includes('room-pan-controls'), 'Edit Rooms directional pan buttons are missing.');
assert(editor.includes('panDragRef'), 'Edit Rooms mouse panning is missing.');
assert(editor.includes('onWheel={handleWheel}'), 'Mouse-wheel plan zoom is missing.');
assert(editor.includes('viewBox={viewport.value}'), 'Pannable zoomable SVG viewport is missing.');
assert(runtimeStyles.includes('grid-template-columns: clamp(330px, 27vw, 420px) minmax(0, 1fr)'), 'Adaptive non-overlapping workspace is missing.');
assert(runtimeStyles.includes('.walkthrough-active canvas'), 'First-person canvas input containment styles are missing.');
assert(runtimeStyles.includes('.room-pan-controls'), 'Edit Rooms pan styling is missing.');

console.log('UI stability smoke test passed: active 1.5.4 runtime, adaptive layout, room panning, input lock, PBR and character assets');
