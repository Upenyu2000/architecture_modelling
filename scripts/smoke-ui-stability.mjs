import { readFileSync } from 'node:fs';

const scene = readFileSync(new URL('../src/renderer/components/ScenePreview.v153.tsx', import.meta.url), 'utf8');
const editor = readFileSync(new URL('../src/renderer/components/RoomLayoutEditor.tsx', import.meta.url), 'utf8');
const stabilityStyles = readFileSync(new URL('../src/renderer/stability-1.5.2.css', import.meta.url), 'utf8');
const viewportStyles = readFileSync(new URL('../src/renderer/viewport-1.5.3.css', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(!/<PerspectiveCamera[^>]*\bposition=/.test(scene), 'Walkthrough camera must not receive a spawn position prop.');
assert(scene.includes('playerPositionRef'), 'Walkthrough must persist the live player position.');
assert(scene.includes('WalkthroughCamera'), 'Dynamic FOV camera component is missing.');
assert(scene.includes('updateProjectionMatrix()'), 'FOV changes must update the projection matrix.');
assert(scene.includes('DEFAULT_FOV = 100'), 'The wider 100-degree default FOV is missing.');
assert(scene.includes('max="120"'), 'The 120-degree FOV range is missing.');
assert(scene.includes('DEFAULT_PLAYER_RADIUS = 0.16'), 'The reduced default collision radius is missing.');
assert(scene.includes('MAX_MOVEMENT_STEP'), 'Sub-stepped collision movement is missing.');
assert(scene.includes('pointIsBlocked'), 'Exterior and wall collision boundary logic is missing.');
assert(scene.includes('WALKTHROUGH_HORIZONTAL_SCALE = 2'), 'The two-times horizontal walkthrough scale is missing.');
assert(scene.includes('scaleWalkthroughScene'), 'Walkthrough coordinate scaling is missing.');
assert(scene.includes('viewportPan'), 'Synchronized viewport pan state is missing.');
assert(scene.includes('THREE.MOUSE.PAN'), 'Mouse-driven viewport panning is missing.');
assert(scene.includes('viewport-pan-controls'), 'Directional viewport pan buttons are missing.');
assert(editor.includes('onWheel={handleWheel}'), 'Mouse-wheel plan zoom is missing.');
assert(editor.includes('viewBox={viewport.value}'), 'Centred zoomable SVG viewport is missing.');
assert(editor.includes('DEFAULT_ZOOM = 0.8'), 'Zoomed-out default floor-plan scale is missing.');
assert(stabilityStyles.includes('.right-column'), 'The original synchronized viewport guard is missing.');
assert(viewportStyles.includes('grid-template-columns: 420px minmax(840px, 1fr)'), 'The separated left/right 1.5.3 workspace is missing.');
assert(viewportStyles.includes('min-width: 840px'), 'The synchronized viewport minimum width is missing.');
assert(viewportStyles.includes('.viewport-pan-controls'), 'Viewport pan control styling is missing.');

console.log('UI stability smoke test passed: panning, 100-degree FOV, 2x walkthrough spacing and separated right-hand viewport');
